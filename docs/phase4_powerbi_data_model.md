# Phase 4 — Power BI Data Model

> **Input from Phase 3:** the modelled CSVs (`opportunities_modelled.csv`, `closed_deals_segmented.csv`, `forecast_summary.csv`) plus `leads_clean.csv`, `dim_date.csv`, and `dim_rep.csv` are imported here to build the star schema and all DAX measures.

These instructions assume **no prior Power BI knowledge**. Follow them in order in **Power BI Desktop** (free download from Microsoft).

---

## 4a — Import instructions

For **each** of the six CSV files below:

1. Open Power BI Desktop.
2. **Home → Get Data → Text/CSV**.
3. Browse to the file, click **Open**.
4. In the preview window, confirm the delimiter is **Comma** and **Data Type Detection** is set to *Based on first 200 rows*.
5. Click **Transform Data** (not *Load*) — this opens **Power Query Editor**, where we fix data types before loading.
6. After setting types (table below), click **Home → Close & Apply**.

Files to import:

| File | Becomes table |
|---|---|
| `leads_clean.csv` | `leads_clean` (dimension) |
| `opportunities_modelled.csv` | `opportunities_modelled` (fact) |
| `closed_deals_segmented.csv` | `closed_deals_segmented` (fact) |
| `forecast_summary.csv` | `forecast_summary` (aggregate fact) |
| `dim_date.csv` | `dim_date` (dimension) |
| `dim_rep.csv` | `dim_rep` (dimension) |

### Column data types to set manually in Power Query

Power BI usually guesses well, but **explicitly set these** (select the column → **Transform → Data Type**):

**leads_clean**
- `created_date` → **Date**
- `lead_id`, `lead_source`, `industry`, `company_size`, `region`, `lead_status` → **Text**

**opportunities_modelled**
- `created_date`, `close_date` → **Date**
- `arr_value`, `close_probability`, `days_in_stage`, `days_since_created` → **Decimal Number** (use **Whole Number** for `days_in_stage`, `close_probability`)
- `arr_imputed_flag`, `close_date_imputed_flag` → **Whole Number** (0/1)
- `is_stalled` → **True/False**
- `opp_id`, `lead_id`, `stage`, `owner_id`, `industry`, `company_size`, `deal_size_band` → **Text**

**closed_deals_segmented**
- `close_date` → **Date**
- `arr_value`, `cac`, `cac_efficiency` → **Decimal Number**
- `days_in_stage` → **Whole Number**
- `renewal_flag` → **True/False**
- `deal_id`, `opp_id`, `customer_segment`, `cluster_label` → **Text**

**forecast_summary**
- `forecast_arr`, `target`, `variance_abs`, `variance_pct` → **Decimal Number**
- `quarter` → **Text**

**dim_date**
- `date` → **Date**
- `year`, `month_num`, `week_num` → **Whole Number**
- `quarter`, `month_name` → **Text**
- `is_weekday` → **True/False**

**dim_rep**
- `annual_quota` → **Whole Number**
- everything else → **Text**

> **Mark dim_date as the date table:** select `dim_date` in the Data view → **Table tools → Mark as Date Table** → choose the `date` column. This is required for `DATESINPERIOD` / `DATESQTD` to behave correctly.

---

## 4b — Relationships (star schema)

Go to **Model view** (left rail). Create each relationship by dragging the first column onto the second. Set **cardinality** and **cross-filter direction** in the dialog (double-click a relationship to edit).

| # | From (many side) | To (one side) | On column | Cardinality | Cross-filter | Active? |
|---|---|---|---|---|---|---|
| R1 | `opportunities_modelled` | `leads_clean` | `lead_id` | Many-to-1 | Single | ✔ |
| R2 | `opportunities_modelled` | `dim_rep` | `owner_id` | Many-to-1 | Single | ✔ |
| R3 | `opportunities_modelled` | `dim_date` | `close_date` → `date` | Many-to-1 | Single | ✔ (active) |
| R4 | `opportunities_modelled` | `dim_date` | `created_date` → `date` | Many-to-1 | Single | ✖ (inactive) |
| R5 | `closed_deals_segmented` | `opportunities_modelled` | `opp_id` | Many-to-1 | Single | ✔ |
| R6 | `closed_deals_segmented` | `dim_date` | `close_date` → `date` | Many-to-1 | Single | ✔ |

**Why these choices (flagged design decisions):**
- **Two date roles (R3 active, R4 inactive).** A fact can have only one *active* relationship to a date table. We make `close_date` active (most time-intelligence is about *when revenue closed*) and keep `created_date` inactive, activated on demand with `USERELATIONSHIP` for cohort-by-creation analysis.
- **R5 bridges deals → opportunities (fact-to-fact).** Each closed deal maps to exactly one won opportunity. Filtering `leads_clean` or `dim_rep` flows **leads/rep → opp → deals** through single-direction filters, so we can slice CAC and segment by lead source and rep without duplicating those columns onto the deals fact.
- **`forecast_summary` is left disconnected.** Its key is a text quarter (`2025-Q2`) with no clean date grain, and it is a pre-aggregated snapshot. The *dynamic* forecast is measure #11 below (computed live from `opportunities_modelled`); `forecast_summary` is used only as a static reference table on the forecast page. If you prefer it connected, add a `quarter` text column to `dim_date` and relate on it.

Resulting shape: `dim_date`, `leads_clean`, `dim_rep` (dimensions) radiate into `opportunities_modelled` (central fact), which feeds `closed_deals_segmented`. Classic star with one bridged sub-fact.

---

## 4c — DAX measures

Create each via **Home → New Measure**. Group them in a dedicated measure table if you like (**Enter Data → empty table named `_Measures`**). Each measure below gives (i) plain-English definition, (ii) the DAX, (iii) where to use it.

> Convention: `%`-type measures should have their **Format** set to *Percentage* in the Measure tools ribbon; ARR/CAC measures formatted as *Currency*.

---

**1. Total Leads**
(i) Distinct count of all cleaned leads.
(ii)
```DAX
Total Leads = DISTINCTCOUNT ( leads_clean[lead_id] )
```
(iii) Executive Summary KPI card; funnel page top.

**2. Qualified Leads**
(i) Leads whose status reached *Qualified*.
(ii)
```DAX
Qualified Leads =
CALCULATE ( [Total Leads], leads_clean[lead_status] = "Qualified" )
```
(iii) Funnel page; denominator for downstream rates.

**3. Lead → Qualified Rate (%)**
(i) Share of leads that became qualified.
(ii)
```DAX
Lead → Qualified Rate (%) =
DIVIDE ( [Qualified Leads], [Total Leads] )
```
(iii) Funnel & Conversion page; KPI card.

**4. Total Opportunities Created**
(i) Count of opportunity records.
(ii)
```DAX
Total Opportunities Created = DISTINCTCOUNT ( opportunities_modelled[opp_id] )
```
(iii) Funnel page; pipeline overview.

**5. Closed Won Count**
(i) Number of opportunities in the *Closed Won* stage.
(ii)
```DAX
Closed Won Count =
CALCULATE (
    COUNTROWS ( opportunities_modelled ),
    opportunities_modelled[stage] = "Closed Won"
)
```
(iii) Leaderboard; executive KPI.

**6. Overall Win Rate (%)**
(i) Won deals as a share of all *decided* deals (won + lost).
(ii)
```DAX
Overall Win Rate (%) =
DIVIDE (
    [Closed Won Count],
    CALCULATE (
        COUNTROWS ( opportunities_modelled ),
        opportunities_modelled[stage] IN { "Closed Won", "Closed Lost" }
    )
)
```
(iii) Rep Performance page; executive KPI.

**7. Total Closed Won ARR**
(i) Sum of ARR for won opportunities.
(ii)
```DAX
Total Closed Won ARR =
CALCULATE (
    SUM ( opportunities_modelled[arr_value] ),
    opportunities_modelled[stage] = "Closed Won"
)
```
(iii) Executive KPI; trend line; segment page.

**8. Average Deal Size (ACV)**
(i) Average ARR per won deal.
(ii)
```DAX
Average Deal Size (ACV) =
DIVIDE ( [Total Closed Won ARR], [Closed Won Count] )
```
(iii) Executive Summary; segment comparison.

**9. Avg Days to Close**
(i) Mean days from opportunity creation to close, for won deals with a close date.
(ii)
```DAX
Avg Days to Close =
AVERAGEX (
    FILTER (
        opportunities_modelled,
        opportunities_modelled[stage] = "Closed Won"
            && NOT ISBLANK ( opportunities_modelled[close_date] )
    ),
    DATEDIFF (
        opportunities_modelled[created_date],
        opportunities_modelled[close_date],
        DAY
    )
)
```
(iii) Velocity card; rep page.

**10. Pipeline Coverage Ratio**
(i) Open pipeline ARR divided by the $1.2M quarterly target.
(ii)
```DAX
Open Pipeline ARR =
CALCULATE (
    SUM ( opportunities_modelled[arr_value] ),
    NOT ( opportunities_modelled[stage] IN { "Closed Won", "Closed Lost" } )
)

Pipeline Coverage Ratio =
DIVIDE ( [Open Pipeline ARR], 1200000 )
```
(iii) Forecast page; executive KPI (a ratio ≥ 3× is the usual health bar).

**11. Forecasted ARR (weighted by close probability)**
(i) Probability-weighted value of all open opportunities.
(ii)
```DAX
Forecasted ARR =
SUMX (
    FILTER (
        opportunities_modelled,
        NOT ( opportunities_modelled[stage] IN { "Closed Won", "Closed Lost" } )
    ),
    opportunities_modelled[arr_value] * opportunities_modelled[close_probability] / 100
)
```
(iii) Forecast vs Target page (primary line).

**12. Forecast vs Target Variance ($)**
(i) Dollar gap between weighted forecast and target.
(ii)
```DAX
Forecast vs Target Variance ($) = [Forecasted ARR] - 1200000
```
(iii) Forecast page KPI; conditional-formatted card.

**13. Forecast vs Target Variance (%)**
(i) The same gap as a percentage of target.
(ii)
```DAX
Forecast vs Target Variance (%) =
DIVIDE ( [Forecast vs Target Variance ($)], 1200000 )
```
(iii) Forecast page; trend indicator.

**14. CAC by Lead Source (average)**
(i) Average customer-acquisition cost; sliceable by lead source via the deals→opp→lead chain.
(ii)
```DAX
CAC by Lead Source (avg) = AVERAGE ( closed_deals_segmented[cac] )
```
(iii) Segment Deep Dive; put `leads_clean[lead_source]` on the axis.

**15. CAC Efficiency Ratio (ARR / CAC)**
(i) ARR generated per dollar of acquisition cost (portfolio-level).
(ii)
```DAX
CAC Efficiency Ratio =
DIVIDE ( [Total Closed Won ARR], SUM ( closed_deals_segmented[cac] ) )
```
(iii) Segment page; efficiency card. (A per-deal `cac_efficiency` column also exists for distribution visuals.)

**16. Stalled Deal Count**
(i) Open opportunities flagged stalled in Phase 3.
(ii)
```DAX
Stalled Deal Count =
CALCULATE (
    COUNTROWS ( opportunities_modelled ),
    opportunities_modelled[is_stalled] = TRUE ()
)
```
(iii) Forecast/pipeline-health page; warning KPI.

**17. Stalled Deal ARR at Risk**
(i) Total ARR sitting in stalled open deals.
(ii)
```DAX
Stalled Deal ARR at Risk =
CALCULATE (
    SUM ( opportunities_modelled[arr_value] ),
    opportunities_modelled[is_stalled] = TRUE ()
)
```
(iii) Risk card; rep accountability table.

**18. Rolling 3-Month Closed ARR**
(i) Trailing-3-month sum of won ARR, using the active `close_date` relationship.
(ii)
```DAX
Rolling 3-Month Closed ARR =
CALCULATE (
    [Total Closed Won ARR],
    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH )
)
```
(iii) Forecast/trend page; smoothed revenue line.

**19. Quarter-to-Date ARR**
(i) Won ARR from the start of the current quarter to the latest date in context.
(ii)
```DAX
Quarter-to-Date ARR =
CALCULATE ( [Total Closed Won ARR], DATESQTD ( dim_date[date] ) )
```
(iii) Executive KPI; QTD vs target gauge.

**20. ARR by Customer Segment (SWITCH)**
(i) Returns won ARR for the segment in the current row/context (SMB / Mid-Market / Enterprise), with a total fallback.
(ii)
```DAX
ARR by Customer Segment =
VAR seg = SELECTEDVALUE ( closed_deals_segmented[customer_segment] )
RETURN
    SWITCH (
        seg,
        "SMB",
            CALCULATE ( SUM ( closed_deals_segmented[arr_value] ),
                closed_deals_segmented[customer_segment] = "SMB" ),
        "Mid-Market",
            CALCULATE ( SUM ( closed_deals_segmented[arr_value] ),
                closed_deals_segmented[customer_segment] = "Mid-Market" ),
        "Enterprise",
            CALCULATE ( SUM ( closed_deals_segmented[arr_value] ),
                closed_deals_segmented[customer_segment] = "Enterprise" ),
        SUM ( closed_deals_segmented[arr_value] )   -- fallback / grand total
    )
```
(iii) Segment Deep Dive; matrix rows = `customer_segment`, value = this measure.

> **Cohort-by-creation variant (uses inactive R4):** to analyse won ARR by the quarter the opp was *created* rather than *closed*, wrap measure #7 in `CALCULATE ( [Total Closed Won ARR], USERELATIONSHIP ( opportunities_modelled[created_date], dim_date[date] ) )`.

---

### ✅ Phase 4 checklist
- ✅ Import steps for all 6 CSVs + explicit data-type corrections
- ✅ Star schema with 6 relationships, cardinality, cross-filter, active/inactive roles defined
- ✅ `dim_rep` defined and generated (`dim_rep.csv`)
- ✅ All 20 DAX measures written with definition, formula, and placement
- ⚠️ Assumption: `forecast_summary` left disconnected (text quarter key); dynamic forecast handled by measure #11
- ⚠️ Assumption: deals→opp fact bridge (R5) used so source/rep context reaches the deals fact without column duplication
