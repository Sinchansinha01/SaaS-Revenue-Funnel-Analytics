# Phase 5 — Power BI Report Layout

> **Input from Phase 4:** the star schema and 20 DAX measures built in Phase 4 are the source for every visual below. Field references use the exact table/column names produced in Phases 1–3.

A 5-page report. For each page: audience, every visual (type + field mapping), conditional formatting, slicers, and the **annotation/tooltip text** a first-time viewer should see.

> **Global slicer panel (sync across pages):** add these as slicers and use **View → Sync slicers** so they apply everywhere — `dim_date[date]` (date range), `leads_clean[region]`, `leads_clean[lead_source]`, `dim_rep[team]`. Place them in a left rail or a collapsible filter pane.

---

## Page 1 — Executive Summary
**Audience:** executives / VP Sales / CRO. One-screen health read.

| Visual | Type | Field mapping |
|---|---|---|
| Total Closed Won ARR | KPI card | Value = `[Total Closed Won ARR]` |
| Quarter-to-Date ARR vs target | Gauge | Value = `[Quarter-to-Date ARR]`, Target = constant 1,200,000 |
| Overall Win Rate (%) | KPI card | Value = `[Overall Win Rate (%)]` |
| Average Deal Size (ACV) | KPI card | Value = `[Average Deal Size (ACV)]` |
| Pipeline Coverage Ratio | KPI card | Value = `[Pipeline Coverage Ratio]` |
| Closed Won ARR trend | Line chart | Axis = `dim_date[date]` (month), Value = `[Total Closed Won ARR]` + `[Rolling 3-Month Closed ARR]` |
| ARR by Customer Segment | Donut | Legend = `closed_deals_segmented[customer_segment]`, Value = `[Total Closed Won ARR]` |
| ARR by Region | Map / filled map | Location = `leads_clean[region]`, Value = `[Total Closed Won ARR]` |

**Conditional formatting:**
- Win Rate card: font green if ≥ 60%, amber 45–60%, red < 45%.
- Coverage Ratio card: green ≥ 3×, amber 2–3×, red < 2×.

**Slicers:** quarter slicer (`dim_date[quarter]`), region.

**Annotation text:** "This page shows where revenue stands today. The gauge compares quarter-to-date closed ARR against the $1.2M target; the trend line overlays raw monthly ARR with a smoothed 3-month average so seasonality is easier to read."

---

## Page 2 — Funnel & Conversion Analysis
**Audience:** marketing ops + sales ops analysts.

| Visual | Type | Field mapping |
|---|---|---|
| Lead → Qualified → Opp → Won funnel | Funnel visual | Values (in order): `[Total Leads]`, `[Qualified Leads]`, `[Total Opportunities Created]`, `[Closed Won Count]` |
| Conversion rates | Multi-row card | `[Lead → Qualified Rate (%)]`, `[Overall Win Rate (%)]` |
| Conversion by lead source | Clustered bar | Axis = `leads_clean[lead_source]`, Values = `[Total Leads]`, `[Qualified Leads]`, `[Closed Won Count]` |
| Stage drop-off | Stacked column | Axis = `opportunities_modelled[stage]`, Value = `[Total Opportunities Created]` |
| Avg days in stage | Bar | Axis = `opportunities_modelled[stage]`, Value = `AVERAGE(opportunities_modelled[days_in_stage])` |

**Conditional formatting:** data bars on the conversion-by-source bar chart; color the lead_source with the highest `[Closed Won Count]` green.

**Slicers:** `leads_clean[industry]`, `leads_clean[company_size]`, `dim_date[quarter]`.

**Annotation text:** "Each step of the funnel is a count from the previous step. The bar chart breaks conversion down by acquisition channel — look for sources with high lead volume but weak qualified-to-won conversion, which signal lead-quality problems rather than volume problems."

---

## Page 3 — Revenue Forecast vs Target
**Audience:** sales leadership + finance.

| Visual | Type | Field mapping |
|---|---|---|
| Forecasted vs target | Line + clustered column | Axis = `dim_date[date]` (month); Column = `[Forecasted ARR]`; Line = constant target ($400k/mo) |
| Forecast variance ($) | KPI card | Value = `[Forecast vs Target Variance ($)]` |
| Forecast variance (%) | KPI card | Value = `[Forecast vs Target Variance (%)]` |
| Quarterly forecast table | Matrix | Rows = `forecast_summary[quarter]`; Values = `forecast_arr`, `target`, `variance_abs`, `variance_pct` |
| Stalled risk | KPI cards | `[Stalled Deal Count]`, `[Stalled Deal ARR at Risk]` |
| Coverage by stage | Stacked bar | Axis = `opportunities_modelled[stage]` (open only), Value = `[Open Pipeline ARR]` |

**Conditional formatting:**
- Variance ($) and (%) cards: red when negative, green when ≥ 0.
- Matrix `variance_pct` column: background color scale red→green.

**Slicers:** `dim_rep[rep_name]`, `dim_date[quarter]`.

**Annotation text:** "Forecasted ARR weights each open deal by its close probability, so a $100k deal at 40% contributes $40k. The red line is the $1.2M quarterly target spread monthly. The stalled-risk cards flag pipeline that has aged well past its stage norm and may need re-qualification."

---

## Page 4 — Rep Performance & Leaderboard
**Audience:** sales managers; 1:1 coaching.

| Visual | Type | Field mapping |
|---|---|---|
| Rep leaderboard | Table | Rows = `dim_rep[rep_name]`; Cols = `[Closed Won Count]`, `[Total Closed Won ARR]`, `[Overall Win Rate (%)]`, `[Avg Days to Close]`, `[Stalled Deal ARR at Risk]` |
| Win rate by rep | Bar | Axis = `dim_rep[rep_name]`, Value = `[Overall Win Rate (%)]` |
| ARR vs quota | Clustered column | Axis = `dim_rep[rep_name]`, Values = `[Total Closed Won ARR]`, `SUM(dim_rep[annual_quota])` |
| Velocity vs win rate | Scatter | X = `[Avg Days to Close]`, Y = `[Overall Win Rate (%)]`, Size = `[Total Closed Won ARR]`, Legend = `dim_rep[rep_name]` |

**Conditional formatting:** leaderboard win-rate column as a red→green color scale; ARR-vs-quota bars green where ARR ≥ quota.

**Slicers:** `dim_rep[team]`, `dim_rep[rep_region]`, `dim_date[quarter]`.

**Annotation text:** "Each rep's win rate is wins ÷ (wins + losses). The scatter plots speed against quality: top-right reps close fast *and* win often; bottom-right reps win but move slowly. Bubble size is total ARR closed, so a small fast-winning bubble may still be low-impact."

---

## Page 5 — Customer Segment Deep Dive
**Audience:** revenue strategy / pricing analysts.

| Visual | Type | Field mapping |
|---|---|---|
| ARR by segment | Matrix | Rows = `closed_deals_segmented[customer_segment]`; Value = `[ARR by Customer Segment]` (measure #20) |
| Avg ARR vs Avg CAC by source | Clustered bar | Axis = `leads_clean[lead_source]`, Values = `[Average Deal Size (ACV)]`, `[CAC by Lead Source (avg)]` |
| CAC efficiency by segment | Bar | Axis = `closed_deals_segmented[customer_segment]`, Value = `[CAC Efficiency Ratio]` |
| KMeans cluster mix | Stacked column | Axis = `closed_deals_segmented[customer_segment]`, Legend = `closed_deals_segmented[cluster_label]`, Value = `COUNT(deal_id)` |
| Deal-size distribution | Histogram / column | Axis = `opportunities_modelled[deal_size_band]`, Value = `[Closed Won Count]` |

**Conditional formatting:** CAC-efficiency bars green when ratio ≥ 10×, red below 5×; cluster legend uses a fixed palette (High Value Fast Close = green, Mid Market Standard = blue, Long Tail = grey).

**Slicers:** `closed_deals_segmented[cluster_label]`, `leads_clean[industry]`, `closed_deals_segmented[renewal_flag]`.

**Annotation text:** "Segments are derived from deal ARR (SMB < $25k, Mid-Market < $100k, Enterprise above). CAC efficiency is ARR earned per acquisition dollar — higher is better. The cluster mix overlays the unsupervised KMeans archetypes so you can see, for example, how much of 'Enterprise' is genuinely 'High Value Fast Close' versus slow-moving long-tail deals."

---

### ✅ Phase 5 checklist
- ✅ 5 pages defined with audience, visuals, field mappings, conditional formatting, slicers
- ✅ First-time-viewer annotation text for every page
- ✅ Synced global slicers specified
- ⚠️ Assumption: target visualised as $400k/month (the $1.2M quarterly target ÷ 3) on monthly charts
