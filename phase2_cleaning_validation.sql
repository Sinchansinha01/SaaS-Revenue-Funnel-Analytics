-- ==========================================================================
-- PHASE 2 - DATA CLEANING & VALIDATION
-- GTM Pipeline Analytics | ANSI SQL (SQLite 3.25+ / PostgreSQL compatible)
-- --------------------------------------------------------------------------
-- Assumes the Phase-1 CSVs are loaded as tables:
--   leads, opportunities, closed_deals, dim_date
-- Date-arithmetic note: SQLite uses date(col,'+N days'); the PostgreSQL
-- equivalent (col + (N || ' days')::interval) is given in comments where used.
-- ==========================================================================


-- ##########################################################################
-- STEP 2a - PROFILING QUERIES  (read-only; surface the planted issues)
-- ##########################################################################

-- 2a.1  NULL counts per column -------------------------------------------
-- Business question: where is data missing before we clean?
SELECT 'leads' AS tbl, 'lead_status' AS col, COUNT(*) - COUNT(lead_status) AS n_null FROM leads
UNION ALL SELECT 'opportunities','arr_value',  COUNT(*) - COUNT(arr_value)  FROM opportunities
UNION ALL SELECT 'opportunities','close_date', COUNT(*) - COUNT(close_date) FROM opportunities
UNION ALL SELECT 'closed_deals','cac',         COUNT(*) - COUNT(cac)        FROM closed_deals
UNION ALL SELECT 'closed_deals','customer_segment', COUNT(*) - COUNT(customer_segment) FROM closed_deals;

-- 2a.2  Duplicate lead_ids -----------------------------------------------
-- Business question: which lead_ids appear more than once (data dupes)?
SELECT lead_id, COUNT(*) AS occurrences
FROM leads
GROUP BY lead_id
HAVING COUNT(*) > 1
ORDER BY occurrences DESC, lead_id;

-- 2a.3  Closed Won opps missing a close_date -----------------------------
-- Business question: which won deals lack a close date (breaks velocity)?
SELECT opp_id, stage, created_date, close_date
FROM opportunities
WHERE stage = 'Closed Won' AND close_date IS NULL;

-- 2a.4  ARR outliers (< $5,000 or > $500,000) ----------------------------
-- Business question: any ARR values outside a plausible ACV band?
SELECT opp_id, arr_value
FROM opportunities
WHERE arr_value IS NOT NULL
  AND (arr_value < 5000 OR arr_value > 500000)
ORDER BY arr_value;


-- ##########################################################################
-- STEP 2b - CLEANING QUERIES  (build *_clean tables)
-- ##########################################################################

-- 2b.1  leads_clean ------------------------------------------------------
-- Dedup (keep first occurrence by created_date), standardise lead_source
-- labels (TRIM + canonical casing), default NULL lead_status to 'New'.
DROP TABLE IF EXISTS leads_clean;
CREATE TABLE leads_clean AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY lead_id ORDER BY created_date) AS rn
    FROM leads
)
SELECT
    lead_id,
    created_date,
    -- standardise source labels defensively (handles stray whitespace/case)
    CASE TRIM(LOWER(lead_source))
        WHEN 'organic search' THEN 'Organic Search'
        WHEN 'paid ads'       THEN 'Paid Ads'
        WHEN 'referral'       THEN 'Referral'
        WHEN 'outbound sdr'   THEN 'Outbound SDR'
        WHEN 'event'          THEN 'Event'
        WHEN 'partner'        THEN 'Partner'
        ELSE TRIM(lead_source)
    END AS lead_source,
    industry,
    company_size,
    region,
    COALESCE(NULLIF(TRIM(lead_status), ''), 'New') AS lead_status
FROM ranked
WHERE rn = 1;

-- 2b.2  opportunities_clean ---------------------------------------------
-- (a) impute missing close_date for Closed Won = created_date + AVG
--     days_in_stage for that stage;
-- (b) fill NULL arr_value with the MEDIAN arr_value for that lead's
--     industry + company_size combination.
DROP TABLE IF EXISTS opportunities_clean;
CREATE TABLE opportunities_clean AS
WITH
-- average cycle length per stage (used to impute close_date)
avg_days AS (
    SELECT stage, AVG(days_in_stage) AS avg_dis
    FROM opportunities
    GROUP BY stage
),
-- attach lead industry + company_size to each opp
opp_dim AS (
    SELECT o.*, l.industry, l.company_size
    FROM opportunities o
    LEFT JOIN (
        SELECT lead_id, industry, company_size,
               ROW_NUMBER() OVER (PARTITION BY lead_id ORDER BY created_date) AS rn
        FROM leads
    ) l ON o.lead_id = l.lead_id AND l.rn = 1
),
-- portable MEDIAN of arr_value per industry+company_size (window pattern)
ranked_arr AS (
    SELECT industry, company_size, arr_value,
           ROW_NUMBER() OVER (PARTITION BY industry, company_size ORDER BY arr_value) AS rn,
           COUNT(*)    OVER (PARTITION BY industry, company_size) AS cnt
    FROM opp_dim
    WHERE arr_value IS NOT NULL
),
median_arr AS (
    SELECT industry, company_size, AVG(arr_value) AS med_arr
    FROM ranked_arr
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)   -- middle 1 (odd) or 2 (even) rows
    GROUP BY industry, company_size
)
SELECT
    od.opp_id,
    od.lead_id,
    od.stage,
    -- arr_value imputation
    COALESCE(od.arr_value, m.med_arr) AS arr_value,
    CASE WHEN od.arr_value IS NULL THEN 1 ELSE 0 END AS arr_imputed_flag,
    od.created_date,
    -- close_date imputation for Closed Won missing a date
    -- SQLite syntax; PostgreSQL: created_date + (ROUND(ad.avg_dis)||' days')::interval
    CASE
        WHEN od.stage = 'Closed Won' AND od.close_date IS NULL
        THEN date(od.created_date, '+' || CAST(ROUND(ad.avg_dis) AS INT) || ' days')
        ELSE od.close_date
    END AS close_date,
    CASE WHEN od.stage = 'Closed Won' AND od.close_date IS NULL THEN 1 ELSE 0 END AS close_date_imputed_flag,
    od.days_in_stage,
    od.owner_id,
    od.close_probability,
    od.industry,
    od.company_size
FROM opp_dim od
LEFT JOIN avg_days   ad ON od.stage = ad.stage
LEFT JOIN median_arr m  ON od.industry = m.industry AND od.company_size = m.company_size;

-- 2b.3  closed_deals_clean ----------------------------------------------
-- Derive customer_segment from arr_value if missing; validate cac > 0.
DROP TABLE IF EXISTS closed_deals_clean;
CREATE TABLE closed_deals_clean AS
SELECT
    deal_id,
    opp_id,
    arr_value,
    close_date,
    COALESCE(customer_segment,
        CASE
            WHEN arr_value < 25000  THEN 'SMB'
            WHEN arr_value < 100000 THEN 'Mid-Market'
            ELSE 'Enterprise'
        END) AS customer_segment,
    cac,
    renewal_flag
FROM closed_deals
WHERE cac IS NOT NULL AND cac > 0;   -- drop/guard against non-positive CAC


-- ##########################################################################
-- STEP 2c - CORE ANALYTICAL QUERIES
-- ##########################################################################

-- --------------------------------------------------------------------------
-- Q1  FUNNEL CONVERSION RATES
-- Business question: what share of leads become Qualified, then an
-- Opportunity, then Closed Won - overall and split by lead_source?
-- Logic: count leads by source; qualified = lead_status='Qualified';
-- opps = rows in opportunities_clean; won = stage='Closed Won'. Rates are
-- each stage divided by total leads for that source.
-- --------------------------------------------------------------------------
WITH base AS (
    SELECT lc.lead_source,
           COUNT(*) AS leads,
           SUM(CASE WHEN lc.lead_status = 'Qualified' THEN 1 ELSE 0 END) AS qualified
    FROM leads_clean lc
    GROUP BY lc.lead_source
),
opp AS (
    SELECT lc.lead_source,
           COUNT(oc.opp_id) AS opps,
           SUM(CASE WHEN oc.stage = 'Closed Won' THEN 1 ELSE 0 END) AS won
    FROM opportunities_clean oc
    JOIN leads_clean lc ON oc.lead_id = lc.lead_id
    GROUP BY lc.lead_source
)
SELECT b.lead_source, b.leads, b.qualified,
       COALESCE(o.opps,0) AS opps, COALESCE(o.won,0) AS won,
       ROUND(100.0 * b.qualified / b.leads, 1)            AS lead_to_qual_pct,
       ROUND(100.0 * COALESCE(o.won,0) / NULLIF(o.opps,0), 1) AS opp_to_won_pct,
       ROUND(100.0 * COALESCE(o.won,0) / b.leads, 1)      AS lead_to_won_pct
FROM base b LEFT JOIN opp o ON b.lead_source = o.lead_source
ORDER BY b.leads DESC;

-- --------------------------------------------------------------------------
-- Q2  STAGE VELOCITY & DROP-OFF
-- Business question: how long do deals sit in each stage, and what share
-- of the pipeline has progressed past each stage?
-- Logic: avg days_in_stage per stage; count per stage ordered by funnel
-- position to expose where volume falls off.
-- --------------------------------------------------------------------------
WITH ordered AS (
    SELECT stage,
           CASE stage WHEN 'Discovery' THEN 1 WHEN 'Evaluation' THEN 2
                      WHEN 'Proposal' THEN 3 WHEN 'Negotiation' THEN 4
                      WHEN 'Closed Won' THEN 5 WHEN 'Closed Lost' THEN 6 END AS ord,
           COUNT(*) AS opp_count,
           ROUND(AVG(days_in_stage),1) AS avg_days_in_stage
    FROM opportunities_clean
    GROUP BY stage
)
SELECT stage, opp_count, avg_days_in_stage,
       ROUND(100.0 * opp_count / SUM(opp_count) OVER (), 1) AS pct_of_pipeline
FROM ordered ORDER BY ord;

-- --------------------------------------------------------------------------
-- Q3  PIPELINE COVERAGE RATIO
-- Business question: does open pipeline cover the $1.2M quarterly target?
-- Logic: open = stage not in (Closed Won, Closed Lost). Coverage = open
-- ARR / 1,200,000. >3x is typically healthy.
-- --------------------------------------------------------------------------
SELECT
    ROUND(SUM(arr_value),0) AS open_pipeline_arr,
    1200000 AS quarterly_target,
    ROUND(SUM(arr_value) / 1200000.0, 2) AS coverage_ratio
FROM opportunities_clean
WHERE stage NOT IN ('Closed Won', 'Closed Lost');

-- --------------------------------------------------------------------------
-- Q4  WIN RATE BY SALES REP
-- Business question: which reps convert the most closed deals?
-- Logic: win rate = Closed Won / (Closed Won + Closed Lost) per owner_id.
-- --------------------------------------------------------------------------
SELECT owner_id,
       SUM(CASE WHEN stage='Closed Won'  THEN 1 ELSE 0 END) AS won,
       SUM(CASE WHEN stage='Closed Lost' THEN 1 ELSE 0 END) AS lost,
       ROUND(100.0 * SUM(CASE WHEN stage='Closed Won' THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN stage IN ('Closed Won','Closed Lost') THEN 1 ELSE 0 END),0), 1) AS win_rate_pct
FROM opportunities_clean
GROUP BY owner_id
ORDER BY win_rate_pct DESC;

-- --------------------------------------------------------------------------
-- Q5  AVG ARR & CAC BY SEGMENT AND LEAD SOURCE
-- Business question: which segment/source mixes are most lucrative vs costly?
-- Logic: join closed deals to opp->lead for source; avg arr & cac grouped.
-- --------------------------------------------------------------------------
SELECT cd.customer_segment, lc.lead_source,
       COUNT(*) AS deals,
       ROUND(AVG(cd.arr_value),0) AS avg_arr,
       ROUND(AVG(cd.cac),0)       AS avg_cac
FROM closed_deals_clean cd
JOIN opportunities_clean oc ON cd.opp_id = oc.opp_id
JOIN leads_clean lc ON oc.lead_id = lc.lead_id
GROUP BY cd.customer_segment, lc.lead_source
ORDER BY cd.customer_segment, avg_arr DESC;

-- --------------------------------------------------------------------------
-- Q6  ROLLING 3-MONTH CLOSED WON ARR
-- Business question: what is the smoothed revenue trend over time?
-- Logic: monthly Closed Won ARR, then a 3-month moving sum via window frame.
-- --------------------------------------------------------------------------
WITH monthly AS (
    SELECT strftime('%Y-%m', close_date) AS ym,   -- Postgres: to_char(close_date,'YYYY-MM')
           SUM(arr_value) AS monthly_arr
    FROM closed_deals_clean
    GROUP BY strftime('%Y-%m', close_date)
)
SELECT ym, ROUND(monthly_arr,0) AS monthly_arr,
       ROUND(SUM(monthly_arr) OVER (ORDER BY ym ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),0) AS rolling_3mo_arr
FROM monthly ORDER BY ym;

-- --------------------------------------------------------------------------
-- Q7  WEIGHTED FORECAST BY QUARTER
-- Business question: how much revenue should we expect from open pipeline?
-- Logic: expected = arr_value * close_probability/100 for OPEN opps,
-- bucketed by the quarter of created_date.
-- --------------------------------------------------------------------------
SELECT CAST(strftime('%Y', created_date) AS INT) AS yr,
       'Q' || ((CAST(strftime('%m', created_date) AS INT) - 1) / 3 + 1) AS qtr,
       ROUND(SUM(arr_value * close_probability / 100.0), 0) AS forecast_arr
FROM opportunities_clean
WHERE stage NOT IN ('Closed Won', 'Closed Lost')
GROUP BY yr, qtr ORDER BY yr, qtr;

-- --------------------------------------------------------------------------
-- Q8  TOP 10 OPEN DEALS BY ARR
-- Business question: which biggest live deals need attention, and how long
-- have they been open?
-- Logic: open opps ranked by arr_value; days open = today - created_date.
-- --------------------------------------------------------------------------
SELECT opp_id, owner_id, stage, ROUND(arr_value,0) AS arr_value,
       CAST(julianday('now') - julianday(created_date) AS INT) AS days_open
FROM opportunities_clean
WHERE stage NOT IN ('Closed Won', 'Closed Lost')
ORDER BY arr_value DESC
LIMIT 10;
