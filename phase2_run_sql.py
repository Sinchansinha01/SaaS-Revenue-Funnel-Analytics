"""
Phase 2 runner: loads Phase-1 CSVs into an in-memory SQLite DB, executes the
cleaning DDL from phase2_cleaning_validation.sql, exports *_clean CSVs, then
runs the 8 analytical queries and prints results. Verifies the SQL is valid.
"""
import sqlite3, pandas as pd

con = sqlite3.connect(":memory:")

# --- load raw CSVs as tables with the names the SQL expects ---------------
for name, path in {
    "leads": "data/leads_raw.csv",
    "opportunities": "data/opportunities_raw.csv",
    "closed_deals": "data/closed_deals_raw.csv",
    "dim_date": "data/dim_date.csv",
}.items():
    pd.read_csv(path).to_sql(name, con, index=False, if_exists="replace")

cur = con.cursor()

def show(title, sql):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)
    df = pd.read_sql_query(sql, con)
    print(df.to_string(index=False))
    return df

# ===================== 2a PROFILING =======================================
show("2a.1 NULL counts per column", """
SELECT 'leads' AS tbl,'lead_status' AS col, COUNT(*)-COUNT(lead_status) AS n_null FROM leads
UNION ALL SELECT 'opportunities','arr_value',  COUNT(*)-COUNT(arr_value)  FROM opportunities
UNION ALL SELECT 'opportunities','close_date', COUNT(*)-COUNT(close_date) FROM opportunities
UNION ALL SELECT 'closed_deals','cac',         COUNT(*)-COUNT(cac)        FROM closed_deals
UNION ALL SELECT 'closed_deals','customer_segment', COUNT(*)-COUNT(customer_segment) FROM closed_deals;""")

dups = show("2a.2 Duplicate lead_ids (top 10)", """
SELECT lead_id, COUNT(*) AS occurrences FROM leads
GROUP BY lead_id HAVING COUNT(*)>1 ORDER BY occurrences DESC, lead_id LIMIT 10;""")
print(f"... total duplicated lead_ids: {len(pd.read_sql_query('SELECT lead_id FROM leads GROUP BY lead_id HAVING COUNT(*)>1', con))}")

show("2a.3 Closed Won opps missing close_date", """
SELECT opp_id, stage, created_date, close_date FROM opportunities
WHERE stage='Closed Won' AND close_date IS NULL;""")

show("2a.4 ARR outliers (<5k or >500k)", """
SELECT opp_id, arr_value FROM opportunities
WHERE arr_value IS NOT NULL AND (arr_value<5000 OR arr_value>500000) ORDER BY arr_value;""")

# ===================== 2b CLEANING (execute DDL) ==========================
ddl = open("phase2_cleaning_validation.sql").read()
# Execute only the cleaning block (everything from leads_clean DROP onward,
# up to the first analytical query marker) plus the profiling is harmless.
# Simplest robust approach: run the DROP/CREATE statements explicitly.
clean_stmts = []
capture = False
buff = []
for line in ddl.splitlines():
    if "STEP 2b" in line:
        capture = True
    if "STEP 2c" in line:
        capture = False
    if capture:
        buff.append(line)
clean_sql = "\n".join(buff)
con.executescript(clean_sql)
print("\n" + "=" * 70 + "\n2b CLEANING executed: leads_clean / opportunities_clean / closed_deals_clean built\n" + "=" * 70)
for t in ["leads_clean", "opportunities_clean", "closed_deals_clean"]:
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n} rows")

# verify imputations landed
imp = pd.read_sql_query("""SELECT SUM(arr_imputed_flag) arr_imp, SUM(close_date_imputed_flag) cd_imp
                           FROM opportunities_clean""", con)
print(f"  imputed arr_value: {int(imp.arr_imp[0])} | imputed close_date: {int(imp.cd_imp[0])}")
print(f"  null arr after clean: {cur.execute('SELECT COUNT(*) FROM opportunities_clean WHERE arr_value IS NULL').fetchone()[0]}")

# export cleaned tables for Phase 3
for t in ["leads_clean", "opportunities_clean", "closed_deals_clean"]:
    pd.read_sql_query(f"SELECT * FROM {t}", con).to_csv(f"data/{t}.csv", index=False)
print("  exported: leads_clean.csv, opportunities_clean.csv, closed_deals_clean.csv")

# ===================== 2c ANALYTICAL QUERIES ==============================
show("Q1 Funnel conversion by lead_source", """
WITH base AS (SELECT lead_source, COUNT(*) leads,
       SUM(CASE WHEN lead_status='Qualified' THEN 1 ELSE 0 END) qualified
       FROM leads_clean GROUP BY lead_source),
opp AS (SELECT lc.lead_source, COUNT(oc.opp_id) opps,
       SUM(CASE WHEN oc.stage='Closed Won' THEN 1 ELSE 0 END) won
       FROM opportunities_clean oc JOIN leads_clean lc ON oc.lead_id=lc.lead_id
       GROUP BY lc.lead_source)
SELECT b.lead_source,b.leads,b.qualified,COALESCE(o.opps,0) opps,COALESCE(o.won,0) won,
       ROUND(100.0*b.qualified/b.leads,1) lead_to_qual_pct,
       ROUND(100.0*COALESCE(o.won,0)/NULLIF(o.opps,0),1) opp_to_won_pct,
       ROUND(100.0*COALESCE(o.won,0)/b.leads,1) lead_to_won_pct
FROM base b LEFT JOIN opp o ON b.lead_source=o.lead_source ORDER BY b.leads DESC;""")

show("Q2 Stage velocity & drop-off", """
WITH ordered AS (SELECT stage,
   CASE stage WHEN 'Discovery' THEN 1 WHEN 'Evaluation' THEN 2 WHEN 'Proposal' THEN 3
              WHEN 'Negotiation' THEN 4 WHEN 'Closed Won' THEN 5 WHEN 'Closed Lost' THEN 6 END ord,
   COUNT(*) opp_count, ROUND(AVG(days_in_stage),1) avg_days_in_stage
   FROM opportunities_clean GROUP BY stage)
SELECT stage,opp_count,avg_days_in_stage,
   ROUND(100.0*opp_count/SUM(opp_count) OVER (),1) pct_of_pipeline
FROM ordered ORDER BY ord;""")

show("Q3 Pipeline coverage ratio", """
SELECT ROUND(SUM(arr_value),0) open_pipeline_arr, 1200000 quarterly_target,
   ROUND(SUM(arr_value)/1200000.0,2) coverage_ratio
FROM opportunities_clean WHERE stage NOT IN ('Closed Won','Closed Lost');""")

show("Q4 Win rate by rep", """
SELECT owner_id,
   SUM(CASE WHEN stage='Closed Won' THEN 1 ELSE 0 END) won,
   SUM(CASE WHEN stage='Closed Lost' THEN 1 ELSE 0 END) lost,
   ROUND(100.0*SUM(CASE WHEN stage='Closed Won' THEN 1 ELSE 0 END)
     /NULLIF(SUM(CASE WHEN stage IN ('Closed Won','Closed Lost') THEN 1 ELSE 0 END),0),1) win_rate_pct
FROM opportunities_clean GROUP BY owner_id ORDER BY win_rate_pct DESC;""")

show("Q5 Avg ARR & CAC by segment + source", """
SELECT cd.customer_segment, lc.lead_source, COUNT(*) deals,
   ROUND(AVG(cd.arr_value),0) avg_arr, ROUND(AVG(cd.cac),0) avg_cac
FROM closed_deals_clean cd
JOIN opportunities_clean oc ON cd.opp_id=oc.opp_id
JOIN leads_clean lc ON oc.lead_id=lc.lead_id
GROUP BY cd.customer_segment, lc.lead_source ORDER BY cd.customer_segment, avg_arr DESC;""")

show("Q6 Rolling 3-month Closed Won ARR", """
WITH monthly AS (SELECT strftime('%Y-%m',close_date) ym, SUM(arr_value) monthly_arr
   FROM closed_deals_clean GROUP BY strftime('%Y-%m',close_date))
SELECT ym, ROUND(monthly_arr,0) monthly_arr,
   ROUND(SUM(monthly_arr) OVER (ORDER BY ym ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),0) rolling_3mo_arr
FROM monthly ORDER BY ym;""")

show("Q7 Weighted forecast by quarter", """
SELECT CAST(strftime('%Y',created_date) AS INT) yr,
   'Q'||((CAST(strftime('%m',created_date) AS INT)-1)/3+1) qtr,
   ROUND(SUM(arr_value*close_probability/100.0),0) forecast_arr
FROM opportunities_clean WHERE stage NOT IN ('Closed Won','Closed Lost')
GROUP BY yr,qtr ORDER BY yr,qtr;""")

show("Q8 Top 10 open deals by ARR", """
SELECT opp_id, owner_id, stage, ROUND(arr_value,0) arr_value,
   CAST(julianday('now')-julianday(created_date) AS INT) days_open
FROM opportunities_clean WHERE stage NOT IN ('Closed Won','Closed Lost')
ORDER BY arr_value DESC LIMIT 10;""")

con.close()
print("\nPhase 2 complete.")
