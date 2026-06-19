"""
Generate Amsterdam-specific EDA charts matching the London chart set.
Output: reports/figures/eda/amsterdam/  (01 through 23)
"""

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT   = Path(__file__).resolve().parent
TABLES = ROOT / "reports" / "tables" / "amsterdam"
PARQUET = ROOT / "data" / "processed" / "amsterdam" / "listing_master.parquet"
OUT    = ROOT / "reports" / "figures" / "eda" / "amsterdam"
OUT.mkdir(parents=True, exist_ok=True)

# ── shared style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.dpi": 150,
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})
C = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#7f7f7f"]
BLUE, ORANGE, GREEN, RED = C[0], C[1], C[2], C[3]

def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print(f"  [ok] {name}")

# ── load parquet once ─────────────────────────────────────────────────────────
print("Loading listing_master.parquet ...")
lm = pd.read_parquet(PARQUET)
print(f"  {len(lm):,} rows  ×  {len(lm.columns)} cols")

lm_p   = lm[lm["price_numeric"].notna()].copy()
p99    = lm_p["price_numeric"].quantile(0.99)
lm_cap = lm_p[lm_p["price_numeric"] <= p99].copy()

# ── 01  Price distribution ─────────────────────────────────────────────────────
print("Chart 01 …")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Amsterdam — Nightly Price Distribution (EUR)", fontsize=13, fontweight="bold")

med = lm_p["price_numeric"].median()
mn  = lm_p["price_numeric"].mean()

ax1.hist(lm_p["price_numeric"], bins=120, color=BLUE, alpha=0.8, edgecolor="white")
ax1.axvline(med, color=RED,    ls="--", lw=1.8, label=f"Median €{med:.0f}")
ax1.axvline(mn,  color=ORANGE, ls="--", lw=1.8, label=f"Mean  €{mn:.0f}")
ax1.set_title("Full Range"); ax1.set_xlabel("Price (EUR)"); ax1.set_ylabel("Listings"); ax1.legend()

ax2.hist(lm_cap["price_numeric"], bins=80, color=BLUE, alpha=0.8, edgecolor="white")
ax2.axvline(med, color=RED,    ls="--", lw=1.8, label=f"Median €{med:.0f}")
ax2.axvline(mn,  color=ORANGE, ls="--", lw=1.8, label=f"Mean  €{mn:.0f}")
ax2.set_title(f"P99-Capped (≤ €{p99:.0f})"); ax2.set_xlabel("Price (EUR)"); ax2.legend()

save(fig, "01_price_distribution.png")

# ── 02  Price by room type ────────────────────────────────────────────────────
print("Chart 02 …")
rt = pd.read_csv(TABLES / "price_by_room_type.csv")
order = ["entire_home", "private_room", "hotel_room", "shared_room"]
rt = rt.set_index("room_type").reindex([r for r in order if r in rt["room_type"].values]).reset_index()

fig, ax = plt.subplots(figsize=(10, 6))
fig.suptitle("Amsterdam — Nightly Price by Room Type (EUR)", fontsize=13, fontweight="bold")
x = np.arange(len(rt))
bars = ax.bar(x, rt["median_price"], color=C[:len(rt)], alpha=0.85, width=0.55)
ax.errorbar(x, rt["median_price"],
            yerr=[rt["median_price"] - rt["p25"], rt["p75"] - rt["median_price"]],
            fmt="none", color="black", capsize=5, lw=1.5)
ax.set_xticks(x)
ax.set_xticklabels([r.replace("_", " ").title() for r in rt["room_type"]])
ax.set_ylabel("Nightly Price (EUR)")
for bar, row in zip(bars, rt.itertuples()):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 4,
            f"€{row.median_price:.0f}\nn={row.listing_count:,}", ha="center", fontsize=9)
save(fig, "02_price_by_room_type.png")

# ── 03  Price by property type ────────────────────────────────────────────────
print("Chart 03 …")
prop_col = "property_type_bucket" if "property_type_bucket" in lm.columns else "property_type"
if prop_col in lm.columns:
    if prop_col == "property_type":
        def _bucket(pt):
            if pd.isna(pt): return "other"
            pt = str(pt).lower()
            if any(k in pt for k in ["apartment", "flat", "condo"]): return "apartment"
            if any(k in pt for k in ["house", "villa", "cottage", "home", "bungalow"]): return "house"
            if any(k in pt for k in ["hotel", "hostel", "guesthouse", "bed and breakfast"]): return "hotel/guesthouse"
            if "boat" in pt or "houseboat" in pt: return "boat"
            if "room" in pt: return "room"
            return "other"
        lm_p["_bucket"] = lm_p[prop_col].apply(_bucket)
    else:
        lm_p["_bucket"] = lm_p[prop_col]

    prop_agg = (lm_p.groupby("_bucket")["price_numeric"]
                .agg(median="median", count="count")
                .reset_index()
                .rename(columns={"_bucket": "bucket"})
                .query("count >= 10")
                .sort_values("median", ascending=True))

    fig, ax = plt.subplots(figsize=(10, max(4, len(prop_agg) * 0.55)))
    fig.suptitle("Amsterdam — Median Price by Property Type (EUR)", fontsize=13, fontweight="bold")
    bars = ax.barh(prop_agg["bucket"], prop_agg["median"], color=BLUE, alpha=0.85)
    for bar, row in zip(bars, prop_agg.itertuples()):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
                f"€{row.median:.0f}  (n={row.count:,})", va="center", fontsize=9)
    ax.set_xlabel("Median Nightly Price (EUR)")
    save(fig, "03_price_by_property_type.png")
else:
    print("  (skipped — property_type column not found)")

# ── 04  Median price by neighbourhood ─────────────────────────────────────────
print("Chart 04 …")
nb = pd.read_csv(TABLES / "price_by_neighbourhood.csv").sort_values("median_price", ascending=False).head(15)

fig, ax = plt.subplots(figsize=(13, 6))
fig.suptitle("Amsterdam — Top 15 Neighbourhoods by Median Price (EUR)", fontsize=13, fontweight="bold")
colors = [RED if i < 3 else BLUE for i in range(len(nb))]
bars = ax.bar(range(len(nb)), nb["median_price"], color=colors, alpha=0.85)
ax.set_xticks(range(len(nb)))
ax.set_xticklabels(nb["neighbourhood_cleansed"], rotation=40, ha="right", fontsize=8)
ax.set_ylabel("Median Nightly Price (EUR)")
for bar, price in zip(bars, nb["median_price"]):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
            f"€{price:.0f}", ha="center", fontsize=8)
save(fig, "04_median_price_by_neighbourhood.png")

# ── 05  Host portfolio distribution ───────────────────────────────────────────
print("Chart 05 …")
seg = pd.read_csv(TABLES / "host_segment_summary.csv")
seg = seg.set_index("host_segment").reindex(["solo", "multi", "professional"]).reset_index()

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Amsterdam — Host Segment Distribution", fontsize=13, fontweight="bold")

ax1.bar(seg["host_segment"], seg["listing_count"], color=C[:3], alpha=0.85)
ax1.set_title("Listings by Segment"); ax1.set_ylabel("Number of Listings")
for i, row in enumerate(seg.itertuples()):
    ax1.text(i, row.listing_count + 40, f"{row.listing_count:,}", ha="center", fontsize=10)

ax2.bar(seg["host_segment"], seg["unique_hosts"], color=C[:3], alpha=0.85)
ax2.set_title("Unique Hosts by Segment"); ax2.set_ylabel("Number of Hosts")
for i, row in enumerate(seg.itertuples()):
    ax2.text(i, row.unique_hosts + 20, f"{row.unique_hosts:,}", ha="center", fontsize=10)

save(fig, "05_host_portfolio_distribution.png")

# ── 06  Review score distributions ───────────────────────────────────────────
print("Chart 06 …")
score_cols = ["review_scores_rating", "review_scores_accuracy", "review_scores_cleanliness",
              "review_scores_checkin", "review_scores_communication",
              "review_scores_location", "review_scores_value"]
labels = ["Overall", "Accuracy", "Cleanliness", "Check-in", "Communication", "Location", "Value"]

fig, axes = plt.subplots(2, 4, figsize=(16, 8))
fig.suptitle("Amsterdam — Review Score Distributions", fontsize=13, fontweight="bold")
for i, (col, lbl) in enumerate(zip(score_cols, labels)):
    ax = axes.flatten()[i]
    data = lm[col].dropna()
    ax.hist(data, bins=50, color=C[i % len(C)], alpha=0.8, edgecolor="white")
    ax.set_title(lbl)
    ax.set_xlabel("Score")
    ax.set_ylabel("Count" if i % 4 == 0 else "")
    ax.axvline(data.median(), color="red", ls="--", lw=1.5, label=f"Median {data.median():.2f}")
    ax.legend(fontsize=8)
axes.flatten()[-1].set_visible(False)
save(fig, "06_review_score_distributions.png")

# ── 07  Availability bands ────────────────────────────────────────────────────
print("Chart 07 …")
av = pd.read_csv(TABLES / "availability_band_summary.csv")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Amsterdam — Listing Availability (Days/Year)", fontsize=13, fontweight="bold")
ax1.bar(av["band"], av["listing_count"], color=C[:len(av)], alpha=0.85)
ax1.set_title("Listings per Band"); ax1.set_xlabel("Availability (days/year)"); ax1.set_ylabel("Listings")
for i, row in enumerate(av.itertuples()):
    ax1.text(i, row.listing_count + 15, f"{row.share_pct:.1f}%", ha="center", fontsize=9)
ax2.pie(av["listing_count"], labels=av["band"], autopct="%1.1f%%",
        colors=C[:len(av)], startangle=90)
ax2.set_title("Share of Total Listings")
save(fig, "07_availability_bands.png")

# ── 08  Listing density by neighbourhood (bar — no geo) ───────────────────────
print("Chart 08 …")
dens = pd.read_csv(TABLES / "neighbourhood_density.csv").sort_values("listings_per_km2", ascending=False)

fig, ax = plt.subplots(figsize=(13, 6))
fig.suptitle("Amsterdam — Listing Density by Neighbourhood (listings/km²)", fontsize=13, fontweight="bold")
colors = [RED if i < 3 else BLUE for i in range(len(dens))]
ax.bar(range(len(dens)), dens["listings_per_km2"], color=colors, alpha=0.85)
ax.set_xticks(range(len(dens)))
ax.set_xticklabels(dens["neighbourhood"], rotation=45, ha="right", fontsize=7)
ax.set_ylabel("Listings per km²")
for i, row in enumerate(dens.iterrows()):
    ax.text(i, row[1]["listings_per_km2"] + 3, f"{row[1]['listings_per_km2']:.0f}", ha="center", fontsize=7)
save(fig, "08_listing_density_by_neighbourhood.png")

# ── 09  Price gradient by distance ───────────────────────────────────────────
print("Chart 09 …")
dist = pd.read_csv(TABLES / "price_by_distance_band.csv")

fig, ax = plt.subplots(figsize=(9, 5))
fig.suptitle("Amsterdam — Price Gradient by Distance from Centraal Station", fontsize=13, fontweight="bold")
x = range(len(dist))
ax.bar(x, dist["median_price"], color=C[:len(dist)], alpha=0.85, width=0.5)
ax.plot(x, dist["median_price"], color="black", marker="o", lw=2, ms=8)
ax.set_xticks(x); ax.set_xticklabels(dist["dist_band"])
ax.set_xlabel("Distance Band (km)"); ax.set_ylabel("Median Nightly Price (EUR)")
for i, row in enumerate(dist.itertuples()):
    ax.text(i, row.median_price + 2, f"€{row.median_price:.0f}\nn={row.listing_count:,}",
            ha="center", fontsize=9)
save(fig, "09_price_gradient_by_distance.png")

# ── 10  Review score by neighbourhood (bar chart) ─────────────────────────────
print("Chart 10 …")
nb_score = (lm.groupby("neighbourhood_cleansed")["review_scores_rating"]
            .agg(median="median", count="count")
            .reset_index()
            .query("count >= 20")
            .sort_values("median", ascending=False))

fig, ax = plt.subplots(figsize=(13, 6))
fig.suptitle("Amsterdam — Median Review Score by Neighbourhood", fontsize=13, fontweight="bold")
colors = [GREEN if s >= nb_score["median"].quantile(0.67) else
          ORANGE if s >= nb_score["median"].quantile(0.33) else RED
          for s in nb_score["median"]]
ax.bar(range(len(nb_score)), nb_score["median"], color=colors, alpha=0.85)
ax.set_xticks(range(len(nb_score)))
ax.set_xticklabels(nb_score["neighbourhood_cleansed"], rotation=45, ha="right", fontsize=7)
ax.set_ylabel("Median Review Score")
ax.set_ylim(nb_score["median"].min() * 0.995, 5.02)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=GREEN, label="Top tier"),
                   Patch(color=ORANGE, label="Mid tier"),
                   Patch(color=RED,   label="Lower tier")], fontsize=9)
save(fig, "10_review_score_by_neighbourhood.png")

# ── 12  Monthly availability trend ───────────────────────────────────────────
print("Chart 12 …")
mo = pd.read_csv(TABLES / "monthly_availability.csv")

fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle("Amsterdam — Monthly Availability & Occupancy (Sep 2025 – Sep 2026)", fontsize=13, fontweight="bold")
x = range(len(mo))
ax.bar(x, mo["availability_rate"] * 100, color=BLUE, alpha=0.65, label="Availability %")
ax.plot(x, mo["occupancy_rate"] * 100, color=RED, marker="o", lw=2, ms=6, label="Occupancy Proxy %")
ax.set_xticks(x); ax.set_xticklabels(mo["month"], rotation=45, ha="right", fontsize=8)
ax.set_ylabel("Rate (%)"); ax.legend()
save(fig, "12_monthly_availability_trend.png")

# ── 13  Weekday vs weekend availability ──────────────────────────────────────
print("Chart 13 …")
ww = pd.read_csv(TABLES / "weekday_weekend_availability.csv")

fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle("Amsterdam — Weekday vs Weekend Availability", fontsize=13, fontweight="bold")

for ax, col, title, fmt in zip(
    axes,
    ["availability_rate", "occupancy_rate"],
    ["Availability Rate (%)", "Occupancy Rate (%)"],
    ["{:.1f}%", "{:.1f}%"]
):
    vals = ww[col] * 100
    bars = ax.bar(ww["label"], vals, color=[BLUE, ORANGE], alpha=0.85, width=0.4)
    ax.set_title(title); ax.set_ylabel(title)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                fmt.format(v), ha="center", fontsize=11)

save(fig, "13_weekday_vs_weekend_availability.png")

# ── 14  Monthly review volume ─────────────────────────────────────────────────
print("Chart 14 …")
rv = pd.read_csv(TABLES / "monthly_review_volume.csv")

fig, axes = plt.subplots(3, 1, figsize=(14, 11))
fig.suptitle("Amsterdam — Review Activity Timeline (2010–2025)", fontsize=13, fontweight="bold")

ax = axes[0]
ax.fill_between(range(len(rv)), rv["review_count"], alpha=0.45, color=BLUE)
ax.plot(range(len(rv)), rv["review_count"], color=BLUE, lw=1)
ax.set_title("Monthly Review Volume"); ax.set_ylabel("Reviews")
ax.set_xticks([]); ax.set_xlim(0, len(rv) - 1)

ax = axes[1]
ax.fill_between(range(len(rv)), rv["active_listings"], alpha=0.45, color=GREEN)
ax.plot(range(len(rv)), rv["active_listings"], color=GREEN, lw=1)
ax.set_title("Active Listings per Month"); ax.set_ylabel("Listings")
ax.set_xticks([]); ax.set_xlim(0, len(rv) - 1)

ax = axes[2]
ax.plot(range(len(rv)), rv["reviews_per_active_listing"], color=ORANGE, lw=1.5)
ax.set_title("Reviews per Active Listing"); ax.set_ylabel("Reviews/Listing")
year_ticks = [i for i, m in enumerate(rv["month"]) if str(m).endswith("-01")]
year_labels = [str(m)[:4] for m in rv["month"] if str(m).endswith("-01")]
ax.set_xticks(year_ticks[::2]); ax.set_xticklabels(year_labels[::2], rotation=45)
ax.set_xlim(0, len(rv) - 1)

plt.tight_layout()
save(fig, "14_monthly_review_volume.png")

# ── 15  Host tenure analysis ──────────────────────────────────────────────────
print("Chart 15 …")
ten = pd.read_csv(TABLES / "host_tenure_summary.csv")

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle("Amsterdam — Performance by Host Tenure Band", fontsize=13, fontweight="bold")

specs = [
    ("median_price",    "Median Price (EUR)",    "€{:.0f}"),
    ("median_rating",   "Median Rating",          "{:.2f}"),
    ("superhost_rate",  "Superhost Rate",         "{:.1%}"),
    ("median_occupancy","Median Occupancy Rate",  "{:.1%}"),
]
for ax, (col, title, fmt) in zip(axes.flatten(), specs):
    bars = ax.bar(range(len(ten)), ten[col], color=C[:len(ten)], alpha=0.85)
    ax.set_title(title)
    ax.set_xticks(range(len(ten)))
    ax.set_xticklabels(ten["tenure_band"], rotation=30, ha="right", fontsize=9)
    for bar, val in zip(bars, ten[col]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                fmt.format(val), ha="center", fontsize=8)

save(fig, "15_host_tenure_analysis.png")

# ── 16  Minimum nights monthly ────────────────────────────────────────────────
print("Chart 16 …")
mn_df = pd.read_csv(TABLES / "minimum_nights_monthly.csv")

fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle("Amsterdam — Minimum Night Policy Trend (Sep 2025 – Sep 2026)", fontsize=13, fontweight="bold")
x = range(len(mn_df))
ax.plot(x, mn_df["median_min_nights"], color=BLUE, marker="o", lw=2, ms=6, label="Median")
ax.plot(x, mn_df["mean_min_nights"],   color=ORANGE, marker="s", lw=2, ms=6, ls="--", label="Mean")
ax.fill_between(x, mn_df["median_min_nights"], alpha=0.15, color=BLUE)
ax.set_xticks(x); ax.set_xticklabels(mn_df["month"], rotation=45, ha="right", fontsize=8)
ax.set_ylabel("Minimum Nights"); ax.legend()
save(fig, "16_minimum_nights_monthly.png")

# ── 17  Host segment comparison ───────────────────────────────────────────────
print("Chart 17 …")
seg = pd.read_csv(TABLES / "host_segment_summary.csv")
seg = seg.set_index("host_segment").reindex(["solo", "multi", "professional"]).reset_index()

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle("Amsterdam — Host Segment Comparison", fontsize=13, fontweight="bold")

specs = [
    ("median_price",    "Median Price (EUR)",       "€{:.0f}"),
    ("median_rating",   "Median Rating",             "{:.2f}"),
    ("median_occupancy","Median Occupancy Rate",     "{:.1%}"),
    ("superhost_rate",  "Superhost Rate",            "{:.1%}"),
]
for ax, (col, title, fmt) in zip(axes.flatten(), specs):
    bars = ax.bar(seg["host_segment"], seg[col], color=C[:3], alpha=0.85)
    ax.set_title(title); ax.set_xlabel("Host Segment")
    for bar, val in zip(bars, seg[col]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                fmt.format(val), ha="center", fontsize=10)

save(fig, "17_host_segment_comparison.png")

# ── 18  Response rate analysis ────────────────────────────────────────────────
print("Chart 18 …")
rr = pd.read_csv(TABLES / "response_rate_summary.csv")

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle("Amsterdam — Response Rate vs Quality Metrics", fontsize=13, fontweight="bold")

for ax, (col, title) in zip(axes, [
    ("superhost_rate",  "Superhost Rate"),
    ("median_rating",   "Median Rating"),
    ("median_occupancy","Median Occupancy"),
]):
    bars = ax.bar(rr["response_rate_band"], rr[col], color=C[:len(rr)], alpha=0.85)
    ax.set_title(title); ax.set_xlabel("Response Rate Band")
    ax.tick_params(axis="x", rotation=30)
    for bar, val in zip(bars, rr[col]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                f"{val:.2f}", ha="center", fontsize=9)

save(fig, "18_response_rate_analysis.png")

# ── 19  Market concentration ──────────────────────────────────────────────────
print("Chart 19 …")
conc = pd.read_csv(TABLES / "market_concentration.csv")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle("Amsterdam — Host Market Concentration", fontsize=13, fontweight="bold")

# Lorenz curve
total = conc["listing_count"].sum()
cum_l = conc["listing_count"].cumsum() / total
cum_h = np.linspace(0, 1, len(conc) + 1)[1:]
ax1.plot([0] + list(cum_h), [0] + list(cum_l), color=BLUE, lw=2, label="Actual")
ax1.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect equality")
ax1.fill_between([0] + list(cum_h), [0] + list(cum_l), [0] + list(cum_h), alpha=0.2, color=BLUE)
ax1.set_xlabel("Cumulative Host Share"); ax1.set_ylabel("Cumulative Listing Share")
ax1.set_title("Lorenz Curve"); ax1.legend()

# Top 20 hosts
top20 = conc.head(20).reset_index(drop=True)
ax2.bar(range(1, 21), top20["listing_count"], color=BLUE, alpha=0.85)
ax2.set_xlabel("Host Rank"); ax2.set_ylabel("Number of Listings")
ax2.set_title("Top 20 Hosts by Listing Count")
ax2.set_xticks(range(1, 21)); ax2.set_xticklabels([str(i) for i in range(1, 21)], fontsize=8)

save(fig, "19_market_concentration.png")

# ── 20  Review count vs price scatter ────────────────────────────────────────
print("Chart 20 …")
scatter = lm_cap[lm_cap["number_of_reviews"] > 0].copy()
sample  = scatter.sample(min(3000, len(scatter)), random_state=42)
sample["log_rev"] = np.log1p(sample["number_of_reviews"])

fig, ax = plt.subplots(figsize=(10, 6))
fig.suptitle("Amsterdam — Review Count vs Nightly Price", fontsize=13, fontweight="bold")
ax.scatter(sample["log_rev"], sample["price_numeric"], alpha=0.25, s=10, color=BLUE)

# Binned median trend line
bins = np.linspace(0, sample["log_rev"].max(), 15)
sample["bin"] = pd.cut(sample["log_rev"], bins)
trend = sample.groupby("bin")["price_numeric"].median()
centers = [b.mid for b in trend.index]
ax.plot(centers, trend.values, color=RED, lw=2.5, marker="o", ms=5, label="Binned median")
ax.set_xlabel("log(1 + Review Count)"); ax.set_ylabel("Nightly Price (EUR)"); ax.legend()
save(fig, "20_review_count_vs_price.png")

# ── 21  Review frequency as demand proxy ─────────────────────────────────────
print("Chart 21 …")
rv2 = pd.read_csv(TABLES / "monthly_review_volume.csv")
recent = rv2[rv2["month"] >= "2018-01"].reset_index(drop=True)

fig, ax = plt.subplots(figsize=(13, 5))
fig.suptitle("Amsterdam — Review Frequency as Demand Proxy (2018–2025)", fontsize=13, fontweight="bold")
ax.fill_between(range(len(recent)), recent["reviews_per_active_listing"], alpha=0.4, color=ORANGE)
ax.plot(range(len(recent)), recent["reviews_per_active_listing"], color=ORANGE, lw=1.5)
yticks = [i for i, m in enumerate(recent["month"]) if str(m).endswith("-01")]
ylabels = [str(m)[:4] for m in recent["month"] if str(m).endswith("-01")]
ax.set_xticks(yticks); ax.set_xticklabels(ylabels, rotation=45, fontsize=9)
ax.set_ylabel("Reviews per Active Listing"); ax.set_xlabel("Month")
save(fig, "21_review_frequency_demand.png")

# ── 22  High review + low score listings ─────────────────────────────────────
print("Chart 22 …")
anom = pd.read_csv(TABLES / "high_review_low_score_listings.csv")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(f"Amsterdam — Popular but Underperforming Listings (n={len(anom):,})",
             fontsize=13, fontweight="bold")

nb_counts = anom["neighbourhood_cleansed"].value_counts().head(10)
ax1.barh(nb_counts.index[::-1], nb_counts.values[::-1], color=RED, alpha=0.85)
ax1.set_xlabel("Count"); ax1.set_title("Top 10 Neighbourhoods")
for i, v in enumerate(nb_counts.values[::-1]):
    ax1.text(v + 0.3, i, str(v), va="center", fontsize=9)

rt_counts = anom["room_type"].value_counts()
ax2.bar(rt_counts.index, rt_counts.values, color=C[:len(rt_counts)], alpha=0.85)
ax2.set_title("By Room Type"); ax2.set_xlabel("Room Type"); ax2.set_ylabel("Count")
for i, (rt, cnt) in enumerate(rt_counts.items()):
    ax2.text(i, cnt + 0.5, str(cnt), ha="center", fontsize=10)

save(fig, "22_high_review_low_score.png")

# ── 23  Review subdimensions correlation matrix ───────────────────────────────
print("Chart 23 …")
score_cols = ["review_scores_accuracy", "review_scores_cleanliness", "review_scores_checkin",
              "review_scores_communication", "review_scores_location", "review_scores_value"]
col_labels = ["Accuracy", "Cleanliness", "Check-in", "Communication", "Location", "Value"]
corr = lm[score_cols].dropna().corr().values

fig, ax = plt.subplots(figsize=(8, 6))
fig.suptitle("Amsterdam — Review Sub-Dimension Correlation Matrix", fontsize=13, fontweight="bold")
im = ax.imshow(corr, cmap="Blues", vmin=0.3, vmax=1.0)
ax.set_xticks(range(len(col_labels))); ax.set_xticklabels(col_labels, rotation=45, ha="right")
ax.set_yticks(range(len(col_labels))); ax.set_yticklabels(col_labels)
for i in range(len(col_labels)):
    for j in range(len(col_labels)):
        ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center",
                fontsize=9, color="white" if corr[i, j] > 0.80 else "black")
plt.colorbar(im, ax=ax, shrink=0.8)
save(fig, "23_review_subdimensions_heatmap.png")

# ── summary ───────────────────────────────────────────────────────────────────
charts = sorted(OUT.glob("*.png"))
print(f"\nDone — {len(charts)} charts saved to {OUT.relative_to(ROOT)}")
for c in charts:
    print(f"  {c.name}")
