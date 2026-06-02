# SaaS Revenue Funnel Analytics

An end-to-end go-to-market (GTM) pipeline analytics project that takes simulated CRM data from raw generation through SQL cleaning, Python enrichment and modelling, and into a fully specified Power BI dashboard. Every Python and SQL step is runnable as-is and reproducible from a fixed random seed.

## Outputs at a glance

| Funnel | Forecast vs Target |
|---|---|
| ![Funnel](charts/funnel_chart.png) | ![Forecast](charts/forecast_chart.png) |

**Stack:** Python (pandas, numpy, scikit-learn, matplotlib) · SQL (ANSI / SQLite / PostgreSQL) · Power BI (DAX, star schema)

---

## Folder structure

```
SaaS-Revenue-Funnel-Analytics/
├── README.md                          # Phase 6 — this file (project front page)
├── requirements.txt                   # Python dependencies
├── .gitignore
├── phase1_data_generation.py          # Phase 1 — generates the 4 raw tables + dim_rep
├── phase2_cleaning_validation.sql     # Phase 2 — profiling, cleaning, 8 analytical queries (ANSI SQL)
├── phase2_run_sql.py                  # Phase 2 — loader: runs the SQL on the CSVs, exports clean tables
├── phase3_enrichment_modelling.py     # Phase 3 — features, KMeans, forecast, charts, modelled exports
├── data/
│   ├── leads_raw.csv                  # Phase 1 output (with planted DQ issues)
│   ├── opportunities_raw.csv          # Phase 1 output
│   ├── closed_deals_raw.csv           # Phase 1 output
│   ├── dim_date.csv                   # Phase 1 output (date dimension)
│   ├── dim_rep.csv                    # Phase 1 output (rep dimension, used in Phase 4)
│   ├── leads_clean.csv                # Phase 2 output (deduped, standardised)
│   ├── opportunities_clean.csv        # Phase 2 output (imputed)
│   ├── closed_deals_clean.csv         # Phase 2 output (validated)
│   ├── opportunities_modelled.csv     # Phase 3 output (engineered features)
│   ├── closed_deals_segmented.csv     # Phase 3 output (KMeans cluster labels)
│   └── forecast_summary.csv           # Phase 3 output (quarterly weighted forecast)
├── charts/
│   ├── forecast_chart.png             # Phase 3 — weighted forecast vs target (±15% band)
│   └── funnel_chart.png               # Phase 3 — lead→qualified→opp→won funnel
└── docs/
    ├── phase4_powerbi_data_model.md   # Phase 4 — import, star schema, 20 DAX measures
    └── phase5_powerbi_report_layout.md# Phase 5 — 5-page report spec
```

---

## How to reproduce end-to-end

> Requires Python 3.10+ with `pandas numpy matplotlib scikit-learn` (sqlite3 ships with Python). Install: `pip install pandas numpy matplotlib scikit-learn`.

1. **Phase 1 — generate raw data**
   ```bash
   python phase1_data_generation.py
   ```
   Writes `data/leads_raw.csv`, `opportunities_raw.csv`, `closed_deals_raw.csv`, `dim_date.csv`.

2. **Phase 2 — clean & validate**
   ```bash
   python phase2_run_sql.py
   ```
   Loads the raw CSVs into in-memory SQLite, runs the profiling + cleaning + analytical queries from `phase2_cleaning_validation.sql`, and writes `leads_clean.csv`, `opportunities_clean.csv`, `closed_deals_clean.csv`.
   *(To run the SQL directly in your own database, load the four raw CSVs as tables named `leads`, `opportunities`, `closed_deals`, `dim_date`, then execute `phase2_cleaning_validation.sql`.)*

3. **Phase 3 — enrich, model, visualise**
   ```bash
   python phase3_enrichment_modelling.py
   ```
   Writes `opportunities_modelled.csv`, `closed_deals_segmented.csv`, `forecast_summary.csv`, and the two PNG charts.

4. **Phase 4–5 — Power BI**
   Open Power BI Desktop and follow `docs/phase4_powerbi_data_model.md` (import the six CSVs: `leads_clean`, `opportunities_modelled`, `closed_deals_segmented`, `forecast_summary`, `dim_date`, `dim_rep`; build relationships; create the 20 measures), then build the 5 pages per `docs/phase5_powerbi_report_layout.md`.

Everything is seeded (`SEED = 42`), so re-running reproduces identical data.

---

## Data dictionary

### `leads_raw` / `leads_clean`
| Column | Type | Description |
|---|---|---|
| lead_id | text | Unique lead key, `LD-0001`…`LD-2000`. (Raw contains ~5% duplicates; clean is deduped.) |
| created_date | date | Date the lead was created (within the 24-month window). |
| lead_source | text | Acquisition channel: Organic Search, Paid Ads, Referral, Outbound SDR, Event, Partner. (Clean standardises casing/whitespace.) |
| industry | text | SaaS, FinTech, HealthTech, E-Commerce, Manufacturing, Professional Services. |
| company_size | text | Employee band: 1-10, 11-50, 51-200, 201-1000, 1000+. |
| region | text | North America, EMEA, APAC, LATAM. |
| lead_status | text | New, Contacted, Qualified, Disqualified. (Clean defaults NULL → New.) |

### `opportunities_raw` / `opportunities_clean` / `opportunities_modelled`
| Column | Type | Description | Added in |
|---|---|---|---|
| opp_id | text | Unique opportunity key, `OPP-0001`. | raw |
| lead_id | text | FK to `leads` (only Qualified leads convert). | raw |
| stage | text | Discovery, Evaluation, Proposal, Negotiation, Closed Won, Closed Lost. | raw |
| arr_value | decimal | Annual recurring revenue / ACV (USD), skewed by company_size. (Raw ~2% NULL; clean imputes via industry+size median.) | raw |
| created_date | date | Opportunity creation date. | raw |
| close_date | date | Close date; NULL while open. (Raw: ~3% of Closed Won nulled; clean imputes = created + avg stage cycle.) | raw |
| days_in_stage | int | Days spent in the current stage. | raw |
| owner_id | text | Sales rep, `REP-01`…`REP-08` (FK to dim_rep). | raw |
| close_probability | int | 0–100, driven by stage. | raw |
| arr_imputed_flag | int | 1 if arr_value was imputed in cleaning, else 0. | clean |
| close_date_imputed_flag | int | 1 if close_date was imputed, else 0. | clean |
| industry | text | Joined from the lead (for imputation/analysis). | clean |
| company_size | text | Joined from the lead. | clean |
| days_since_created | decimal | Pipeline age in days for open opps (NaN if closed). | modelled |
| is_stalled | bool | True if open and days_since_created > 1.5 × avg days_in_stage for the stage. | modelled |
| deal_size_band | text | ARR quartile label Q1 (smallest) … Q4 (largest). | modelled |

### `closed_deals_raw` / `closed_deals_clean` / `closed_deals_segmented`
| Column | Type | Description | Added in |
|---|---|---|---|
| deal_id | text | Unique deal key, `DEAL-0001`. | raw |
| opp_id | text | FK to `opportunities` (only Closed Won). | raw |
| arr_value | decimal | Won ARR (USD). | raw |
| close_date | date | Deal close date. | raw |
| customer_segment | text | SMB (<$25k), Mid-Market (<$100k), Enterprise (≥$100k); derived from arr_value. | raw |
| cac | decimal | Customer acquisition cost (USD), skewed by lead_source. | raw |
| renewal_flag | bool | True if an early renewal signal exists (~20%). | raw |
| cac_efficiency | decimal | arr_value ÷ cac (ARR earned per acquisition dollar). | segmented |
| days_in_stage | int | Joined from the opportunity (KMeans feature). | segmented |
| cluster_label | text | KMeans archetype: High Value Fast Close / Mid Market Standard / Long Tail. | segmented |

### `dim_date`
| Column | Type | Description |
|---|---|---|
| date | date | Daily grain, 2024-06-01 → 2026-05-31. |
| year | int | Calendar year. |
| quarter | text | Q1–Q4. |
| month_num | int | 1–12. |
| month_name | text | January … December. |
| week_num | int | ISO week number. |
| is_weekday | bool | True Mon–Fri. |

### `dim_rep`
| Column | Type | Description |
|---|---|---|
| owner_id | text | `REP-01`…`REP-08` (FK target from opportunities). |
| rep_name | text | Sales rep display name. |
| team | text | Enterprise / Mid-Market / SMB. |
| rep_region | text | Rep's home region. |
| annual_quota | int | Annual revenue quota (USD). |

### `forecast_summary`
| Column | Type | Description |
|---|---|---|
| quarter | text | `YYYY-Qn`. |
| forecast_arr | decimal | Sum of probability-weighted open-opp ARR for the quarter. |
| target | decimal | Quarterly target ($1.2M). |
| variance_abs | decimal | forecast_arr − target. |
| variance_pct | decimal | variance_abs ÷ target × 100. |

---

## Known limitations & assumptions

- **Simulated, not real, data.** All values are randomly generated with planted correlations; numbers are illustrative.
- **`is_stalled` is over-triggered (~97% of open opps).** The spec formula compares total pipeline *age* to a *single* stage's average duration, while the generator spreads open-opp `created_date`s across the full 24 months. Faithful to the brief but not realistic; fix by scoping open `created_date`s nearer to today or comparing against cumulative expected cycle.
- **Pipeline coverage ratio (~15×) is inflated** because all 24 months of open opps are summed against a single-quarter target. A production measure should scope open pipeline to the current/next quarter.
- **`cac_efficiency` lives on closed deals only**, since CAC is defined only for won deals (not open opportunities).
- **Funnel is 1:1 by construction** (every Qualified lead → one opp; every Closed Won → one deal), so Qualified→Opp conversion is exactly 100%. Real funnels lose volume at every step.
- **`forecast_summary` is bucketed by opp `created_date` quarter**, not expected close quarter; a close-date-weighted forecast is more standard for commit/coverage reporting.
- **Date arithmetic in the SQL targets SQLite** (`date()`, `strftime`); PostgreSQL equivalents are noted inline as comments.
- **Median imputation uses the window-function pattern** (averaging the middle 1–2 rows), valid on SQLite 3.25+ and PostgreSQL.

## Suggested next steps

- **Connect to a live CRM** (Salesforce / HubSpot API) to replace the simulator with real pipeline data; schedule incremental refresh.
- **Add a churn / renewal-risk ML model** using `renewal_flag`, tenure, segment, and CAC efficiency as features.
- **Lead-scoring model** to predict Lead→Qualified probability from source/industry/size and prioritise SDR effort.
- **Refine the forecast** with a close-date-weighted, current-quarter-scoped pipeline and stage-transition (Markov) probabilities instead of static close_probability.
- **Data quality monitoring**: promote the Phase 2 profiling queries into scheduled tests (e.g., dbt tests or Great Expectations) that alert on new nulls/duplicates.
- **Row-level security** in Power BI so each rep sees only their own pipeline.
