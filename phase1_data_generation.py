"""
==========================================================================
PHASE 1 - DATA GENERATION
GTM Pipeline Analytics | Simulated CRM dataset
--------------------------------------------------------------------------
Produces 4 raw tables (leads, opportunities, closed_deals, dim_date) with
realistic correlations and INTENTIONAL data-quality issues left unfixed.
Reproducible via fixed seed. Requires: pandas, numpy.
==========================================================================
"""

import numpy as np
import pandas as pd

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

# 24-month window anchored to the trailing 2 years from "today" (Jun 2026)
WINDOW_START = pd.Timestamp("2024-06-01")
WINDOW_END   = pd.Timestamp("2026-05-31")
WINDOW_DAYS  = (WINDOW_END - WINDOW_START).days

N_LEADS = 2000
N_REPS  = 8

OUT = "data/"  # relative output folder


def rand_dates(n, start=WINDOW_START, span_days=WINDOW_DAYS):
    """Uniform random timestamps across the data window."""
    offsets = rng.integers(0, span_days, size=n)
    return start + pd.to_timedelta(offsets, unit="D")


# ==========================================================================
# TABLE 1: leads
# ==========================================================================
print("=" * 70)
print("BUILDING: leads")
print("=" * 70)

lead_source = rng.choice(
    ["Organic Search", "Paid Ads", "Referral", "Outbound SDR", "Event", "Partner"],
    size=N_LEADS, p=[0.24, 0.22, 0.14, 0.20, 0.12, 0.08],
)
industry = rng.choice(
    ["SaaS", "FinTech", "HealthTech", "E-Commerce", "Manufacturing", "Professional Services"],
    size=N_LEADS, p=[0.28, 0.16, 0.14, 0.16, 0.13, 0.13],
)
company_size = rng.choice(
    ["1-10", "11-50", "51-200", "201-1000", "1000+"],
    size=N_LEADS, p=[0.22, 0.30, 0.26, 0.15, 0.07],
)
region = rng.choice(
    ["North America", "EMEA", "APAC", "LATAM"],
    size=N_LEADS, p=[0.46, 0.28, 0.18, 0.08],
)
# Status distribution: realistic top-of-funnel attrition
lead_status = rng.choice(
    ["New", "Contacted", "Qualified", "Disqualified"],
    size=N_LEADS, p=[0.28, 0.30, 0.26, 0.16],
)

leads = pd.DataFrame({
    "lead_id": [f"LD-{i:04d}" for i in range(1, N_LEADS + 1)],
    "created_date": rand_dates(N_LEADS),
    "lead_source": lead_source,
    "industry": industry,
    "company_size": company_size,
    "region": region,
    "lead_status": lead_status,
})
leads["created_date"] = leads["created_date"].dt.normalize()

print("shape:", leads.shape)
print(leads.dtypes)
print(leads.head())

# ==========================================================================
# TABLE 2: opportunities  (only Qualified leads convert)
# ==========================================================================
print("\n" + "=" * 70)
print("BUILDING: opportunities")
print("=" * 70)

qualified = leads[leads["lead_status"] == "Qualified"].copy()
n_opps = len(qualified)

# ARR base ranges skewed by company_size (USD ACV)
arr_ranges = {
    "1-10":     (8_000, 30_000),
    "11-50":    (15_000, 60_000),
    "51-200":   (30_000, 110_000),
    "201-1000": (60_000, 180_000),
    "1000+":    (90_000, 250_000),
}
arr_value = np.array([
    round(rng.uniform(*arr_ranges[cs]), -2)  # round to nearest $100
    for cs in qualified["company_size"]
])

# Stage distribution among created opps (open + closed mix)
stage = rng.choice(
    ["Discovery", "Evaluation", "Proposal", "Negotiation", "Closed Won", "Closed Lost"],
    size=n_opps, p=[0.18, 0.16, 0.14, 0.12, 0.22, 0.18],
)

# close_probability driven by stage (deterministic bands + small jitter)
prob_band = {
    "Discovery": (10, 25), "Evaluation": (25, 45), "Proposal": (45, 65),
    "Negotiation": (65, 85), "Closed Won": (100, 100), "Closed Lost": (0, 0),
}
close_probability = np.array([rng.integers(prob_band[s][0], prob_band[s][1] + 1) for s in stage])

# days_in_stage realistic per stage
dis_band = {
    "Discovery": (3, 21), "Evaluation": (7, 35), "Proposal": (5, 30),
    "Negotiation": (5, 45), "Closed Won": (1, 14), "Closed Lost": (1, 30),
}
days_in_stage = np.array([rng.integers(dis_band[s][0], dis_band[s][1] + 1) for s in stage])

owner_id = rng.choice([f"REP-{i:02d}" for i in range(1, N_REPS + 1)], size=n_opps)

opp_created = qualified["created_date"].values + pd.to_timedelta(
    rng.integers(1, 30, size=n_opps), unit="D"
)

# close_date: only for closed stages = opp_created + a realistic cycle length
is_closed = np.isin(stage, ["Closed Won", "Closed Lost"])
cycle_len = rng.integers(20, 160, size=n_opps)
close_date = np.where(
    is_closed,
    opp_created + pd.to_timedelta(cycle_len, unit="D"),
    np.datetime64("NaT"),
)

opportunities = pd.DataFrame({
    "opp_id": [f"OPP-{i:04d}" for i in range(1, n_opps + 1)],
    "lead_id": qualified["lead_id"].values,
    "stage": stage,
    "arr_value": arr_value,
    "created_date": pd.to_datetime(opp_created).normalize(),
    "close_date": pd.to_datetime(close_date),
    "days_in_stage": days_in_stage,
    "owner_id": owner_id,
    "close_probability": close_probability,
})
# clamp close_date to window end
opportunities.loc[opportunities["close_date"] > WINDOW_END, "close_date"] = WINDOW_END
opportunities["close_date"] = opportunities["close_date"].dt.normalize()

print("shape:", opportunities.shape)
print(opportunities.dtypes)
print(opportunities.head())

# ==========================================================================
# TABLE 3: closed_deals  (only Closed Won)
# ==========================================================================
print("\n" + "=" * 70)
print("BUILDING: closed_deals")
print("=" * 70)

won = opportunities[opportunities["stage"] == "Closed Won"].copy()
n_won = len(won)

# customer_segment derived by arr_value
def segment(arr):
    if arr < 25_000:
        return "SMB"
    elif arr < 100_000:
        return "Mid-Market"
    return "Enterprise"

# CAC realistic by lead_source (cheap inbound -> expensive outbound/event)
cac_base = {
    "Organic Search": (1_500, 4_000), "Referral": (1_000, 3_000),
    "Partner": (2_000, 5_000), "Paid Ads": (3_000, 8_000),
    "Event": (5_000, 14_000), "Outbound SDR": (4_000, 12_000),
}
won = won.merge(leads[["lead_id", "lead_source"]], on="lead_id", how="left")
cac = np.array([round(rng.uniform(*cac_base[src]), -1) for src in won["lead_source"]])

closed_deals = pd.DataFrame({
    "deal_id": [f"DEAL-{i:04d}" for i in range(1, n_won + 1)],
    "opp_id": won["opp_id"].values,
    "arr_value": won["arr_value"].values,
    "close_date": won["close_date"].values,
    "customer_segment": [segment(a) for a in won["arr_value"].values],
    "cac": cac,
    "renewal_flag": rng.random(n_won) < 0.20,   # 20% early renewal signal
})
print("shape:", closed_deals.shape)
print(closed_deals.dtypes)
print(closed_deals.head())

# ==========================================================================
# TABLE 4: dim_date
# ==========================================================================
print("\n" + "=" * 70)
print("BUILDING: dim_date")
print("=" * 70)

dates = pd.date_range(WINDOW_START, WINDOW_END, freq="D")
dim_date = pd.DataFrame({"date": dates})
dim_date["year"] = dim_date["date"].dt.year
dim_date["quarter"] = "Q" + dim_date["date"].dt.quarter.astype(str)
dim_date["month_num"] = dim_date["date"].dt.month
dim_date["month_name"] = dim_date["date"].dt.month_name()
dim_date["week_num"] = dim_date["date"].dt.isocalendar().week.astype(int)
dim_date["is_weekday"] = dim_date["date"].dt.dayofweek < 5

print("shape:", dim_date.shape)
print(dim_date.dtypes)
print(dim_date.head())

# ==========================================================================
# DIMENSION: dim_rep  (sales rep attributes; Phase 4 star-schema dimension)
# ==========================================================================
print("\n" + "=" * 70)
print("BUILDING: dim_rep")
print("=" * 70)
dim_rep = pd.DataFrame({
    "owner_id":     [f"REP-{i:02d}" for i in range(1, N_REPS + 1)],
    "rep_name":     ["Alex Chen", "Bianca Rossi", "Carlos Mendez", "Dana Okafor",
                     "Evan Li", "Farah Haddad", "Grace Park", "Hugo Weber"],
    "team":         ["Enterprise", "Enterprise", "Mid-Market", "Mid-Market",
                     "Mid-Market", "SMB", "SMB", "Enterprise"],
    "rep_region":   ["North America", "EMEA", "LATAM", "North America",
                     "APAC", "EMEA", "North America", "EMEA"],
    "annual_quota": [1_200_000, 1_200_000, 800_000, 800_000,
                     800_000, 500_000, 500_000, 1_200_000],
})
dim_rep.to_csv(OUT + "dim_rep.csv", index=False)
print("shape:", dim_rep.shape)
print(dim_rep.head())

# ==========================================================================
# INTENTIONAL DATA-QUALITY ISSUES (left unfixed for Phase 2 to handle)
# ==========================================================================
print("\n" + "=" * 70)
print("INJECTING DATA-QUALITY ISSUES")
print("=" * 70)

# ~5% duplicate lead records (append exact duplicates)
n_dup = int(round(0.05 * len(leads)))
dup_rows = leads.sample(n=n_dup, random_state=SEED)
leads = pd.concat([leads, dup_rows], ignore_index=True)
print(f"+ Added {n_dup} duplicate lead rows  -> leads now {leads.shape}")

# ~3% of Closed Won opps: wipe close_date despite being won
won_idx = opportunities.index[opportunities["stage"] == "Closed Won"]
n_missing_cd = max(1, int(round(0.03 * len(opportunities))))
n_missing_cd = min(n_missing_cd, len(won_idx))
wipe_idx = rng.choice(won_idx, size=n_missing_cd, replace=False)
opportunities.loc[wipe_idx, "close_date"] = pd.NaT
print(f"+ Nulled close_date on {n_missing_cd} Closed Won opps")

# ~2% of arr_value -> NULL
n_null_arr = int(round(0.02 * len(opportunities)))
null_idx = rng.choice(opportunities.index, size=n_null_arr, replace=False)
opportunities.loc[null_idx, "arr_value"] = np.nan
print(f"+ Nulled arr_value on {n_null_arr} opps")

# ==========================================================================
# EXPORT
# ==========================================================================
leads.to_csv(OUT + "leads_raw.csv", index=False)
opportunities.to_csv(OUT + "opportunities_raw.csv", index=False)
closed_deals.to_csv(OUT + "closed_deals_raw.csv", index=False)
dim_date.to_csv(OUT + "dim_date.csv", index=False)

print("\n" + "=" * 70)
print("EXPORTED: leads_raw.csv, opportunities_raw.csv, closed_deals_raw.csv, dim_date.csv")
print("=" * 70)
print(f"leads_raw:        {leads.shape}")
print(f"opportunities_raw:{opportunities.shape}")
print(f"closed_deals_raw: {closed_deals.shape}")
print(f"dim_date:         {dim_date.shape}")
