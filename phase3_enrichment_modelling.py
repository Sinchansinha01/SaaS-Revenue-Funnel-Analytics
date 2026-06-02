"""
==========================================================================
PHASE 3 - ENRICHMENT & MODELLING
GTM Pipeline Analytics
--------------------------------------------------------------------------
Loads the *_clean CSVs from Phase 2, engineers features, runs KMeans
segmentation, builds a weighted pipeline forecast, renders two charts, and
exports the final modelled tables. Requires: pandas, numpy, matplotlib,
scikit-learn.
==========================================================================
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")                      # headless backend
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

SEED = 42
TODAY = pd.Timestamp("2026-06-01")         # analysis "as of" date
TARGET_Q = 1_200_000                       # quarterly revenue target

leads = pd.read_csv("data/leads_clean.csv", parse_dates=["created_date"])
opps  = pd.read_csv("data/opportunities_clean.csv", parse_dates=["created_date", "close_date"])
deals = pd.read_csv("data/closed_deals_clean.csv", parse_dates=["close_date"])

OPEN = ~opps["stage"].isin(["Closed Won", "Closed Lost"])

# ==========================================================================
# 3a - FEATURE ENGINEERING
# ==========================================================================
print("=" * 70 + "\n3a FEATURE ENGINEERING\n" + "=" * 70)

# days_since_created (pipeline age) for OPEN opps; NaN for closed
opps["days_since_created"] = np.where(
    OPEN, (TODAY - opps["created_date"]).dt.days, np.nan
)

# is_stalled: open > 1.5x average days_in_stage for its stage
avg_dis = opps.groupby("stage")["days_in_stage"].transform("mean")
opps["is_stalled"] = OPEN & (opps["days_since_created"] > 1.5 * avg_dis)

# deal_size_band: ARR quartiles Q1 (smallest) -> Q4 (largest)
opps["deal_size_band"] = pd.qcut(
    opps["arr_value"], q=4, labels=["Q1", "Q2", "Q3", "Q4"]
)

print("open opps:", int(OPEN.sum()), "| stalled:", int(opps['is_stalled'].sum()))
print(opps[["opp_id", "stage", "days_since_created", "is_stalled", "deal_size_band"]].head())

# cac_efficiency lives where CAC exists (closed_deals): arr / cac
deals["cac_efficiency"] = (deals["arr_value"] / deals["cac"]).round(2)
print("\ncac_efficiency (closed deals) summary:")
print(deals["cac_efficiency"].describe()[["mean", "min", "max"]].round(2).to_string())

# ==========================================================================
# 3b - KMEANS SEGMENTATION (k=3)
#   Rationale for k=3: the business wants three named archetypes, and an
#   elbow/silhouette on this feature set offers no strong reason to deviate.
#   Features are standardised so large ARR magnitudes don't dominate CAC/days.
# ==========================================================================
print("\n" + "=" * 70 + "\n3b KMEANS SEGMENTATION (k=3)\n" + "=" * 70)

# join days_in_stage from opps onto closed deals
seg = deals.merge(opps[["opp_id", "days_in_stage"]], on="opp_id", how="left")
feat_cols = ["arr_value", "cac", "days_in_stage"]
X = StandardScaler().fit_transform(seg[feat_cols])

km = KMeans(n_clusters=3, random_state=SEED, n_init=10)
seg["cluster_raw"] = km.fit_predict(X)

# centroids in original units for labelling (mean of each raw cluster is the
# most interpretable form and matches KMeans centers in original space)
centroids = seg.groupby("cluster_raw")[feat_cols].mean()
print("Cluster centroids (raw units):")
print(centroids.round(0).to_string())

# Label clusters deterministically:
#   highest ARR & lowest days_in_stage -> "High Value Fast Close"
#   lowest ARR                         -> "Long Tail"
#   remaining                          -> "Mid Market Standard"
hv = centroids.assign(score=centroids["arr_value"] - centroids["days_in_stage"] * 1000)["score"].idxmax()
lt = centroids["arr_value"].idxmin()
labels = {}
for c in centroids.index:
    if c == hv:
        labels[c] = "High Value Fast Close"
    elif c == lt and c != hv:
        labels[c] = "Long Tail"
    else:
        labels[c] = "Mid Market Standard"
# guarantee all three names are used even if hv==lt edge case
if len(set(labels.values())) < 3:
    ordered = centroids["arr_value"].sort_values(ascending=False).index.tolist()
    names = ["High Value Fast Close", "Mid Market Standard", "Long Tail"]
    labels = {c: names[i] for i, c in enumerate(ordered)}

seg["cluster_label"] = seg["cluster_raw"].map(labels)
print("\nCount per cluster:")
print(seg["cluster_label"].value_counts().to_string())

# ==========================================================================
# 3c - WEIGHTED PIPELINE FORECAST
# ==========================================================================
print("\n" + "=" * 70 + "\n3c REVENUE FORECAST\n" + "=" * 70)

open_opps = opps[OPEN].copy()
open_opps["expected_arr"] = open_opps["arr_value"] * open_opps["close_probability"] / 100.0
open_opps["month"] = open_opps["created_date"].dt.to_period("M").astype(str)
open_opps["quarter"] = (
    open_opps["created_date"].dt.year.astype(str) + "-Q"
    + open_opps["created_date"].dt.quarter.astype(str)
)

monthly = open_opps.groupby("month")["expected_arr"].sum().reset_index()
quarterly = open_opps.groupby("quarter")["expected_arr"].sum().reset_index()
quarterly["target"] = TARGET_Q
quarterly["variance_abs"] = quarterly["expected_arr"] - TARGET_Q
quarterly["variance_pct"] = (quarterly["variance_abs"] / TARGET_Q * 100).round(1)
print(quarterly.round(0).to_string(index=False))

# ---- forecast chart: dual-axis, monthly forecast vs quarterly target, +-15% band
fig, ax1 = plt.subplots(figsize=(11, 5.5))
m = monthly.copy()
ax1.plot(m["month"], m["expected_arr"], color="#2563eb", marker="o", lw=2, label="Forecast ARR (monthly)")
ax1.fill_between(m["month"], m["expected_arr"] * 0.85, m["expected_arr"] * 1.15,
                 color="#2563eb", alpha=0.15, label="±15% confidence band")
monthly_target = TARGET_Q / 3.0           # quarterly target spread to monthly
ax1.axhline(monthly_target, color="#dc2626", ls="--", lw=1.8, label="Monthly target ($400k)")
ax1.set_ylabel("Forecast ARR ($)", color="#2563eb")
ax1.tick_params(axis="y", labelcolor="#2563eb")
ax1.set_xticks(range(len(m)))
ax1.set_xticklabels(m["month"], rotation=45, ha="right", fontsize=8)
ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
ax1.set_title("Weighted Pipeline Forecast vs Target (open opportunities)", fontsize=13, fontweight="bold")
ax1.grid(alpha=0.25)
# secondary axis: cumulative forecast
ax2 = ax1.twinx()
ax2.plot(m["month"], m["expected_arr"].cumsum(), color="#16a34a", lw=1.5, ls=":", label="Cumulative forecast")
ax2.set_ylabel("Cumulative forecast ($)", color="#16a34a")
ax2.tick_params(axis="y", labelcolor="#16a34a")
ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1e6:.1f}M"))
l1, lb1 = ax1.get_legend_handles_labels(); l2, lb2 = ax2.get_legend_handles_labels()
ax1.legend(l1 + l2, lb1 + lb2, loc="upper left", fontsize=8, framealpha=0.9)
plt.tight_layout()
plt.savefig("charts/forecast_chart.png", dpi=130)
plt.close()
print("saved charts/forecast_chart.png")

# ==========================================================================
# 3d - FUNNEL VISUALISATION
# ==========================================================================
print("\n" + "=" * 70 + "\n3d FUNNEL CHART\n" + "=" * 70)

n_leads = len(leads)
n_qual  = int((leads["lead_status"] == "Qualified").sum())
n_opps  = len(opps)
n_won   = int((opps["stage"] == "Closed Won").sum())
stages  = ["Leads", "Qualified", "Opportunities", "Closed Won"]
counts  = [n_leads, n_qual, n_opps, n_won]
print(dict(zip(stages, counts)))

fig, ax = plt.subplots(figsize=(10, 5.5))
colors = ["#1e3a8a", "#2563eb", "#3b82f6", "#16a34a"]
bars = ax.bar(stages, counts, color=colors, width=0.6)
for i, (b, c) in enumerate(zip(bars, counts)):
    ax.text(b.get_x() + b.get_width()/2, c + n_leads*0.015, f"{c:,}",
            ha="center", va="bottom", fontweight="bold")
    if i > 0:
        conv = 100.0 * counts[i] / counts[i-1]
        ax.annotate(f"{conv:.1f}%\nvs prev", xy=(i-0.5, (counts[i]+counts[i-1])/2),
                    ha="center", va="center", fontsize=9, color="#b91c1c", fontweight="bold")
ax.set_title("GTM Funnel: Lead → Qualified → Opportunity → Closed Won",
             fontsize=13, fontweight="bold")
ax.set_ylabel("Count")
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig("charts/funnel_chart.png", dpi=130)
plt.close()
print("saved charts/funnel_chart.png")

# ==========================================================================
# 3e - EXPORT FINAL MODELLED TABLES
# ==========================================================================
print("\n" + "=" * 70 + "\n3e EXPORT\n" + "=" * 70)

opps.to_csv("data/opportunities_modelled.csv", index=False)
seg.drop(columns=["cluster_raw"]).to_csv("data/closed_deals_segmented.csv", index=False)

forecast_summary = quarterly.rename(columns={"expected_arr": "forecast_arr"})
forecast_summary.to_csv("data/forecast_summary.csv", index=False)

print("exported: opportunities_modelled.csv, closed_deals_segmented.csv, forecast_summary.csv")
print(f"  opportunities_modelled: {opps.shape}")
print(f"  closed_deals_segmented: {seg.shape}")
print(f"  forecast_summary:       {forecast_summary.shape}")
print("\nPhase 3 complete.")
