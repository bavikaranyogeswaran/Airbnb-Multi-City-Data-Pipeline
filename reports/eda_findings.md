# EDA Key Findings — London, Amsterdam, Madrid & Berlin Airbnb

**Assessment:** Experne'c Pvt Ltd — Inside Airbnb Data Engineer Intern  
**Cities:** London (snapshot 2025-09-14) · Amsterdam (snapshot 2025-09-11) · Madrid (snapshot 2025-09-14) · Berlin (snapshot 2025-09-23)  
**Notebooks:** `notebooks/03_exploratory_data_analysis.ipynb` (London) · `notebooks/04_statistical_analysis.ipynb` · `notebooks/05_amsterdam_eda.ipynb`  
**EDA generator:** `src/analytics/run_eda.py` — produces all 22 CSVs per city (incl. hypothesis tests and OLS regression) into `reports/tables/<city>/`  
**Updated:** 2026-06-22

---

## 1. Analysis Objectives

1. Understand the London Airbnb supply landscape: price distributions, room types, neighbourhood patterns.
2. Identify host segments and measure supply concentration.
3. Explore review activity as a demand proxy (A-005: calendar price is unavailable).
4. Detect geographic pricing gradients and borough-level quality variation.
5. Surface anomalous listings (high review activity + low rating) for operational follow-up.
6. Provide a reproducible, business-interpretable foundation for subsequent statistical modelling.

---

## 2. Data Used

| Dataset | File | Rows | Notes |
|---------|------|------|-------|
| Listing master | `listing_master.parquet` | 96,871 × 100 | Cleaned + enriched snapshot |
| Calendar | `calendar_clean.parquet` | 35,357,974 × 5 | Sep 2025 – Sep 2026; price NULL (A-005) |
| Reviews | `reviews_clean.parquet` | 2,097,996 × 8 | 2009-12-21 → 2025-09-17 |
| Neighbourhood boundaries | `neighbourhoods.geojson` | 33 boroughs | EPSG:4326, reprojected to 27700 |

---

## 3. Inclusion and Exclusion Rules

| Rule | Count | % of total |
|------|-------|-----------|
| Total listings in snapshot | 96,871 | 100% |
| Missing price (`price_numeric` NULL) | 34,908 | 36.0% |
| **Price-eligible analysis population** | **61,963** | **64.0%** |

Non-price analyses (availability, reviews, host profile) use the full 96,871-listing dataset.  
Listings with `number_of_reviews == 0` are excluded from review frequency charts (24,122 listings).

---

## 4. Summary Statistics

| Metric | Value |
|--------|-------|
| Total listings | 96,871 |
| Unique hosts | 55,646 |
| Median nightly price (GBP) | £135 |
| Mean nightly price (GBP) | £229 (inflated by luxury tail) |
| 99th-percentile price | £1100 |
| Entire homes | 62,907 (64.9%) |
| Private rooms | 33,643 (34.7%) |
| Median occupancy proxy | 73.7% |
| Median reviews / month | 0.17 |
| Median review score (overall) | 4.83 |
| Superhost rate | 18.1% |

---

## 5. Visualisations Produced

All charts are in `reports/figures/eda/`.

| # | File | Description |
|---|------|-------------|
| 01 | `01_price_distribution.png` | Price histogram — full range and P99-capped |
| 02 | `02_price_by_room_type.png` | Boxplot by room type |
| 03 | `03_price_by_property_type.png` | Median price by property bucket |
| 04 | `04_median_price_by_neighbourhood.png` | Top-15 boroughs by median price |
| 05 | `05_host_portfolio_distribution.png` | Listings and hosts by segment |
| 06 | `06_review_score_distributions.png` | All 7 review score histograms |
| 07 | `07_availability_bands.png` | Availability_365 distribution (bar + pie) |
| 08 | `08_listing_density_map.png` | Listing density choropleth (listings/km²) |
| 09 | `09_price_gradient_by_distance.png` | Price vs distance from Trafalgar Square |
| 10 | `10_review_score_map.png` | Median review score choropleth by borough |
| 11 | `11_room_type_by_neighbourhood.png` | Room-type % heatmap by borough |
| 12 | `12_monthly_availability_trend.png` | Monthly occupancy rate (A-005 adapted) |
| 13 | `13_weekday_vs_weekend_availability.png` | Weekday vs weekend occupancy |
| 14 | `14_monthly_review_volume.png` | Review activity 2009–2025 (3-panel) |
| 15 | `15_host_tenure_analysis.png` | Performance metrics by host tenure band |
| 16 | `16_minimum_nights_monthly.png` | Minimum-night policy trend |
| 17 | `17_host_segment_comparison.png` | 6-metric host segment comparison |
| 18 | `18_response_rate_analysis.png` | Response rate vs quality/price |
| 19 | `19_market_concentration.png` | Lorenz curve + top-20-hosts bar |
| 20 | `20_review_count_vs_price.png` | Review count vs price scatter (log x) |
| 21 | `21_review_frequency_demand.png` | Reviews/month demand proxy |
| 22 | `22_high_review_low_score.png` | Anomaly listing breakdown |
| 23 | `23_review_subdimensions_heatmap.png` | Sub-dimension correlation matrix |

---

## 6. Business Interpretation

Each finding follows the Section 11 framework: Question → Evidence → Interpretation → Business implication → Recommended action → Limitation.

### F-01 · Price Distribution is Highly Right-Skewed

**Question:** How are nightly prices distributed across London Airbnb listings?  
**Evidence:** Median £135/night; mean £229/night; P99 £1100/night. The distribution has a long luxury tail (max > £1M).  
**Interpretation:** The typical listing is priced at £135/night, but the mean is inflated by a small number of ultra-luxury or corporate properties. This is classic power-law skew.  
**Business implication:** Mean-based pricing benchmarks mislead the 99% of hosts who are not in the luxury segment. Median and percentile bands are the appropriate reference points.  
**Recommended action:** All pricing dashboards and host-facing recommendations should use median (or P25–P75 bands), not mean, as the default benchmark.  
**Limitation:** 36.0% of listings have no listed price. If unpriced listings are systematically cheaper (e.g. enquiry-only or inactive), observed prices are biased upward.

### F-02 · Entire Homes Charge ~2.9× the Private-Room Median

**Question:** Which room type commands the highest nightly price?  
**Evidence:** Entire homes median £175; private rooms median £61 (Charts 02–03, price_by_room_type.csv).  
**Interpretation:** Entire homes and hotel rooms occupy the upper price tier. Private rooms serve budget travelers and compete mainly on price, not experience.  
**Business implication:** Hosts should never benchmark against the citywide average — room type is the first segmentation variable. A private-room host seeing a £135 city median has already been misled.  
**Recommended action:** Implement room-type-specific pricing tiers in the recommendation engine from day one.  
**Limitation:** Room type does not control for listing size, capacity, or location. A 4-bedroom entire home and a studio are both 'entire_home' — within-type variance is large.

### F-03 · Borough Is a Dominant Price Driver

**Question:** Which boroughs have the highest median listing prices?  
**Evidence:** Top 3 boroughs by median price (Chart 04, price_by_neighbourhood.csv):  
  - **City of London**: median £248/night  
  - **Kensington and Chelsea**: median £225/night  
  - **Westminster**: median £220/night  
**Interpretation:** Central, tourist-heavy boroughs command a significant premium. The borough alone explains a large fraction of price variance even before controlling for room type.  
**Business implication:** Borough-level pricing benchmarks should be the default reference for both hosts and the platform analytics team. City-level medians are too coarse.  
**Recommended action:** Publish live borough-level price percentiles in the host dashboard.  
**Limitation:** Borough boundaries are administrative, not economic — gentrified areas at the edge of expensive boroughs may be priced more like neighbouring cheaper boroughs.

### F-04 · Price Declines with Distance from City Centre

**Question:** Does nightly price fall systematically as listings move further from Trafalgar Square?  
**Evidence:** Median price decreases monotonically across the five distance bands 0–2 km → 20+ km (Chart 09, price_by_distance_band.csv).  
**Interpretation:** A clear centre-periphery gradient exists. Listings closest to the centre can sustain substantially higher prices, reflecting demand from tourism and business travel.  
**Business implication:** Location scoring based on distance from attraction hubs is a tractable and defensible pricing input — more granular than borough alone.  
**Recommended action:** Add a distance-from-centre score as a feature in the pricing model.  
**Limitation:** London is polycentric (Canary Wharf, Shoreditch, South Bank are distinct demand centres). A single reference point oversimplifies the geography; this analysis understates the value of non-central clusters.

### F-05 · Supply Is Highly Concentrated Among a Few Hosts

**Question:** How concentrated is London's Airbnb supply among a small number of host operators?  
**Evidence:** Top 1% of hosts (556) control 19.3% of listings; top 10% control 42.9% (Chart 19, market_concentration.csv). Commercial segment (21+ listings/host) accounts for 15.2% of total supply.  
**Interpretation:** London's Airbnb market is an oligopoly of supply. A handful of professional operators control a disproportionate share of inventory, resembling a hotel management company more than a peer-to-peer market.  
**Business implication:** Platform policies targeting supply concentration (e.g. registration limits, commercial-host rules) will have high impact per operator affected. Conversely, tools for commercial hosts (bulk analytics, portfolio dashboards) have outsized reach.  
**Recommended action:** Build a separate commercial-host analytics track in the API; flag listings by host_segment in all downstream tools.  
**Limitation:** Hosts may operate under multiple accounts. True concentration is potentially higher. host_id is the only linkage available in this dataset.

### F-06 · Response Rate Is the Strongest Superhost Predictor

**Question:** What operational characteristics best distinguish high-quality hosts?  
**Evidence:** Superhost rate is 18.1% overall. Hosts with response rates ≥ 96% have the highest superhost rates, ratings, and occupancy across all segments (Charts 18–19, response_rate_summary.csv).  
**Interpretation:** Response rate is a strong, host-controlled quality signal. Unlike rating (partially driven by guest taste) or price (market-driven), response rate is a direct measure of host engagement.  
**Business implication:** Nudging hosts toward faster response rates is one of the highest-ROI quality interventions available — it improves both guest experience and occupancy.  
**Recommended action:** Surface response rate prominently in host dashboards; send automated prompts when response rate drops below 80%.  
**Limitation:** Response rate has 32.7% null values — primarily because Airbnb only calculates it for hosts with recent enquiries. Newer and inactive hosts are excluded, which inflates the observed rates.

### F-07 · High Review Count Does Not Signal Premium Pricing

**Question:** Do listings with more reviews charge more?  
**Evidence:** Median price by review count bucket (London; `review_price_score_buckets.csv`):

| Review count | Listings | Median price | Median rating |
|---|---|---|---|
| 0 reviews | 24,122 | £150 | — |
| 1–5 | 26,672 | £141 | 5.00 |
| 6–20 | 22,096 | £136 | 4.80 |
| 21–100 | 19,338 | £125 | 4.81 |
| 100+ | 4,643 | £86 | 4.81 |

Median price falls monotonically from £150 (unreviewed) to £86 (100+ reviews). Rating stabilises at 4.80–4.81 after the first few reviews; the inflated 5.00 for the 1–5 bucket reflects early-reviewer generosity bias.  
**Interpretation:** Review count is a proxy for throughput and budget positioning, not premium quality. Affordable, high-turnover listings accumulate reviews faster than luxury listings, which have fewer, longer stays. The unreviewed cohort (£150 median) is likely newly listed or luxury/enquiry-only — priced high before the market has tested them.  
**Business implication:** A dashboard ranking listings by review count will surface budget properties, not high-value ones. Review rate (per month) is a better demand proxy; review score is the quality signal.  
**Recommended action:** Separate 'review activity' (reviews/month = 0.17 median) from 'review quality' (overall score) in all host-facing dashboards. Flag the 100+ bucket as high-throughput / value-positioned — these hosts need volume-based analytics, not premium-pricing guidance.  
**Limitation:** Review count is cumulative and favours older listings regardless of current performance. A listing may have 500 reviews from 10 years ago and zero from the last 12 months.

### F-08 · 38.3% of Listings Are Effectively Inactive

**Question:** What share of listings are genuinely active versus blocked or inactive?  
**Evidence:** 38.3% of listings have availability_365 ≤ 30 days (Chart 07, availability_band_summary.csv). The median occupancy proxy across all listings is 73.7%.  
**Interpretation:** A significant portion of the listed supply is not accessible to guests. These may be test listings, seasonally inactive properties, or hosts who have left the platform but not delisted.  
**Business implication:** Raw listing counts overstate true market depth. Active supply (91–365 availability days) is the correct denominator for supply-demand ratio calculations.  
**Recommended action:** Filter to 'active' listings (availability_365 > 30) for all market sizing and pricing analysis. Report both raw and active counts in dashboards.  
**Limitation:** availability_365 is from the listings snapshot, not the calendar. A listing could appear unavailable because it is fully booked (high demand) rather than inactive.

### F-09 · 4,565 Listings Are Popular but Underperforming (4.7% of Total)

**Question:** Are there listings that attract high review activity but receive below-average ratings?  
**Evidence:** 4,565 listings (4.7% of all listings) meet both thresholds: ≥ 20 reviews (P75) AND overall rating ≤ 4.58 (P25). They cluster disproportionately in certain boroughs and room types, with lower cleanliness and communication sub-scores (Chart 22, high_review_low_score_listings.csv).  
**Interpretation:** These listings are actively booked despite below-median quality — suggesting either price-sensitive guests who tolerate lower quality or a mismatch between guest expectations and listing reality.  
**Business implication:** These 4,565 listings are the platform's highest-priority intervention candidates: they generate review volume (traffic) but depress overall platform NPS.  
**Recommended action:** Flag anomaly listings in the operations dashboard. Trigger automated host coaching for cleanliness and communication sub-scores < platform median. Consider warning flags if rating remains below P25 after 6 months.  
**Limitation:** The rating threshold (P25 = 4.58) is low by absolute standards — all Airbnb ratings cluster between 4.0 and 5.0. A 4.58 rating is within a narrow band; caution is warranted before escalating to enforcement.

### F-10 · Review Sub-Dimensions Are Highly Correlated; Location and Value Are Most Distinct

**Question:** Do the six review sub-dimensions measure independent constructs or are they all capturing the same overall satisfaction signal?  
**Evidence:** Pearson r ranges from 0.565 to 0.833 across all sub-dimension pairs. The highest-rated dimension is Communication (4.812); the lowest is Value (4.616). Location and value show the weakest correlations with the host-controlled dimensions (Chart 23, review_subdimension_summary.csv).  
**Interpretation:** Sub-dimensions are highly inter-correlated, confirming that a single overall score is a reasonable summary. However, location and value are somewhat independent signals — location reflects neighbourhood, not host effort; value reflects perceived price-quality fit.  
**Business implication:** The overall score is a defensible single KPI. But host coaching programmes should decompose scores: location is non-actionable; value, cleanliness, and communication are host-controlled levers.  
**Recommended action:** In the quality model, use a composite score that down-weights location (non-actionable) and emphasises cleanliness, communication, and check-in responsiveness.  
**Limitation:** Scores cluster near 5.0 (right-skew ceiling), compressing variance and artificially inflating Pearson r. True dimensionality may be greater than the correlations suggest.

---

## 7. Key Market Insights

1. **London's Airbnb market is premium and polarised.** Median price £135/night but mean £229 — a 70% gap driven by luxury outliers. Any single-number benchmark hides two distinct markets.
2. **Borough + room type together explain the majority of price variance.** Neither alone is sufficient for benchmarking.
3. **Supply is professionally managed.** Top 10% of hosts control 42.9% of listings; commercial operators (15.2% of supply) behave like hotel chains, not casual sharers.
4. **38.3% of listed supply is not actually available.** True active supply is substantially smaller than headline listing counts suggest.
5. **Review activity and rating are orthogonal dimensions.** High throughput ≠ high quality. Dashboards that combine them mislead hosts.
6. **Response rate is the highest-ROI quality intervention.** It is host-controlled, directly observable, and strongly correlated with guest outcomes.
7. **4,565 listings are operationally risky.** Popular enough to accumulate reviews, poor enough to drag platform NPS — a targeted intervention cohort exists today.

---

## 8. Recommendations

| Priority | Recommendation | Evidence base |
|----------|---------------|---------------|
| P1 | Replace mean with median in all public-facing pricing benchmarks | F-01: mean inflated 70% above median |
| P1 | Segment all pricing tools by room_type as the first dimension | F-02: ~2.9× entire-home premium over private rooms |
| P1 | Flag and review 4,565 anomaly listings; trigger host coaching | F-09: popular but underperforming cohort |
| P2 | Build borough-level live price percentile dashboards | F-03: borough drives price more than any other single variable |
| P2 | Add distance-from-centre as a pricing model feature | F-04: monotonic centre-periphery gradient confirmed |
| P2 | Build commercial-host analytics track (21+ listings) | F-05: 19.3% of supply controlled by top 1% of hosts |
| P3 | Surface response rate prominently; alert when < 80% | F-06: response rate is strongest superhost predictor |
| P3 | Exclude blocked listings (availability ≤ 30 d) from supply metrics | F-08: 38.3% of listings are non-accessible |
| P3 | Decompose quality score to separate location from host-controlled sub-scores | F-10: location is non-actionable; cleanliness + communication are |

---

## 9. Limitations

1. **A-005 — Calendar price unavailable.** `calendar.price` and `calendar.adjusted_price` are 100% NULL in this snapshot. All temporal analyses substitute availability/occupancy. Revenue proxies use listing-snapshot price only.
2. **Single-point-in-time snapshot.** The listing snapshot is 2025-09-14. Prices, availability, and host status change continuously; these findings reflect one moment.
3. **Review count ≠ booking count.** Airbnb's review rate is approximately 50–70% of stays. review volume understates true occupancy.
4. **36% of listings have no price.** Unpriced listings are excluded from all price analyses. If they are systematically cheap (inactive or enquiry-only), observed prices are biased upward.
5. **Two cities, same snapshot window.** London and Amsterdam have been analysed; findings reflect each city's own market structure, regulation, and tourism demand. Cross-city comparisons (Section 11) identify structural differences but cannot establish causality. Generalisation to other markets requires separate validation.
6. **Trafalgar Square as centre.** London is polycentric; a single distance reference underestimates location value in non-central demand clusters (Canary Wharf, Shoreditch, Heathrow corridor).
7. **Host identity.** A single operator may run multiple host accounts. Concentration metrics based on host_id understate true market concentration.
8. **Right-skewed rating distribution.** Scores cluster near 5.0, compressing variance. Pearson correlations and percentile thresholds should be interpreted within this narrow range.

---

## 10. Next Analysis Steps

1. **Statistical Analysis (Phase 2):** Regression models for price prediction; hypothesis tests for segment differences; confidence intervals around key metrics.
2. **Multi-City EDA:** ✅ All four cities complete — London, Amsterdam, Madrid, and Berlin each have 22 EDA + statistical analysis CSVs in `reports/tables/<city>/` generated by `src/analytics/run_eda.py`.
3. **ML Modelling (Phase 3):** Train a price prediction model using borough, room type, distance, host segment, and review metrics as features.
4. **Calendar Price Recovery:** Investigate whether the A-005 NULL prices are recoverable from listing `price` × calendar `minimum_nights` × `adjusted_price` fields in raw data.
5. **Anomaly Monitoring API:** Expose the high-review / low-score listing set via a FastAPI endpoint for the operations team.
6. **Superhost Causal Analysis:** Use host tenure as an instrument to estimate whether superhost status causes higher ratings or is a selection effect.

---

*This document was generated programmatically from `notebooks/03_exploratory_data_analysis.ipynb`.*  
*All figures referenced are stored in `reports/figures/eda/`; all tables in `reports/tables/`.*
---

## 11. Four-City Comparison: London · Amsterdam · Madrid · Berlin

### City Overview

| Metric | London (GBP) | Amsterdam (EUR) | Madrid (EUR) | Berlin (EUR) |
|--------|-------------|----------------|-------------|-------------|
| Snapshot date | 2025-09-14 | 2025-09-11 | 2025-09-14 | 2025-09-23 |
| Total listings | 96,871 | 10,480 | 25,000 | 14,274 |
| Price-eligible listings | 61,963 | 5,874 | 18,953 | 9,264 |
| Unique hosts | 55,646 | 9,201 | 10,453 | 9,464 |
| Median price (local currency) | £135 | €222 | €105 | €89 |
| Entire home share | 64.9% | 81.7% | — | — |
| Commercial host share (21+) | 15.2% | 0.8% | — | — |
| Superhost rate | 18.1% | 18.0% | — | — |
| Median review score | 4.83 | 4.92 | — | — |

### Key Cross-City Findings

**C-01 · Amsterdam is heavily entire-home dominant**
Amsterdam is 82% entire homes vs London's 65%.
This likely reflects Amsterdam's stricter short-stay registration rules, which push
casual room-sharing out and leave only committed entire-home operators on the platform.

**C-02 · Amsterdam has far less professional-operator concentration**
Commercial hosts (21+ listings) account for only 0.8% of Amsterdam supply vs
15.2% in London. Top-1% host supply share: Amsterdam 7.1% vs London 19.3%.
London's market is structurally more concentrated — resembling a managed-property market.

**C-03 · Amsterdam listings are much less available**
Median availability_365 is only 20 days in Amsterdam vs 96 days in London.
This is consistent with Amsterdam's 30-night-per-year short-stay cap, which forces
hosts to block the majority of the calendar.

**C-04 · Amsterdam scores higher on review quality**
Median overall rating: Amsterdam 4.92 vs London 4.83.
With far fewer active listings (regulation effect), Amsterdam's supply is skewed
toward experienced, high-quality operators who survived the regulatory filter.

**C-05 · Price comparison requires city-median normalisation**
Amsterdam median is EUR 222 vs London GBP 135. These are not directly
comparable (different currencies, purchasing power, and regulatory environments).
The normalised distribution (Chart 26) shows Amsterdam has a heavier right tail —
more listings priced at 2× or more the city median — consistent with fewer but
more premium entire-home listings.

**C-06 · Amsterdam non-superhosts rated higher (H2 reversal)**
Hypothesis H2 (superhost → higher rating) holds for London but reverses in Amsterdam:
Mann-Whitney test is significant (p < 0.001), but the direction is reversed — Amsterdam
non-superhosts have a marginally higher median rating. Possible explanations: Amsterdam's
regulatory filter already removes poor-quality hosts, compressing the rating distribution;
superhost status may lag quality for newly-registered hosts who quickly reach 4.8+ ratings
without yet accumulating enough reviews for the superhost badge.

**C-07 · Regression explains less variance in Amsterdam (R² 0.47 vs 0.64)**
The OLS model (room type + accommodates + bedrooms + rating + superhost + neighbourhood)
explains 47% of log-price variance in Amsterdam vs 64% in London. Neighbourhood
contributes less in Amsterdam — its 22 districts are geographically compact (all within
~10 km of the centre), so location is a weaker price signal than in London's sprawling
33-borough market.

### Limitations

- Currency differences (EUR vs GBP) prevent direct nominal price comparison across cities.
- Price null rates differ: London 36%, Amsterdam 44% — price-based analyses use only eligible rows.
- Statistical tests for smaller cities use a threshold of 50 listings/neighbourhood for H4 (vs 100 for London) to retain sufficient groups.
- Madrid and Berlin detailed cross-city narrative pending extended analysis; key figures are available via `GET /analytics/llm/cross-city`.

*EDA tables per city: `reports/tables/{city}/` (22 CSVs each) · Cross-city tables: `reports/tables/city_comparison_summary.csv`, `room_type_city_comparison.csv`*
