"""
Prompt templates for LLM-generated market summaries.

SYSTEM is the shared system prompt injected into every call.
render(summary_type, context) returns the user-turn prompt for a given
summary type and pre-built context dict (from context_builder).

Summary types: "city", "model", "clusters", "hosts", "cross_city"
"""
from __future__ import annotations

import json
import numpy as np

VALID_TYPES = {"city", "model", "clusters", "hosts", "cross_city"}

SYSTEM = """\
You are a senior short-term rental market analyst writing for a non-technical \
business audience — property investors, platform managers, and city planners. \
Your task is to turn structured data into clear, readable prose.

Rules you must follow without exception:
1. Use ONLY the numbers supplied in the data block. Never add figures from \
general knowledge about these cities.
2. Write flowing paragraphs — no bullet points, no numbered lists, no headers.
3. Aim for 180–240 words. Do not go under 150 or over 280.
4. Refer to prices with their currency as given in the data \
(e.g. "£135 median nightly rate" or "€110 median nightly rate").
5. Write in present tense, third person.
6. End with one forward-looking sentence about what the data suggests \
for hosts, investors, or the platform.\
"""


class _NumpyEncoder(json.JSONEncoder):
    """Coerce numpy scalar types to native Python so json.dumps never throws."""
    def default(self, o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def _json_block(data: dict | list) -> str:
    """Compact JSON suitable for embedding in a prompt."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), cls=_NumpyEncoder)


def _city_prompt(ctx: dict) -> str:
    rt = ctx["room_type_mix_pct"]
    top_nbhd = ", ".join(list(ctx["top_5_neighbourhoods"].keys())[:3])
    return f"""\
Below is the market data for {ctx["city"].title()}. Write a 3-paragraph \
overview of this Airbnb market.

Paragraph 1 — size and pricing: cover total listings \
({ctx["total_listings"]:,}), unique hosts ({ctx["unique_hosts"]:,}), \
median nightly rate ({ctx["currency"]} {ctx["median_price"]}), \
and the price spread (25th–75th percentile: \
{ctx["p25_price"]}–{ctx["p75_price"]}, 95th percentile: {ctx["p95_price"]}).

Paragraph 2 — supply structure: cover the room-type mix \
(entire home {rt.get("entire_home", 0)}%, \
private room {rt.get("private_room", 0)}%), \
superhost rate ({ctx["superhost_rate_pct"]}%), \
median availability ({ctx["median_availability_365"]} days/year), \
and the share of highly-available listings \
({ctx["pct_high_availability"]}% listed 270+ days/year).

Paragraph 3 — guest experience and geography: cover median guest rating \
({ctx["median_rating"]}/5), median reviews per listing \
({ctx["median_reviews"]}), and note the top neighbourhoods by listing \
concentration ({top_nbhd}).

Data:
{_json_block(ctx)}\
"""


def _model_prompt(ctx: dict) -> str:
    top = ", ".join(ctx["top_features"]) if ctx["top_features"] else "not available"
    mae_rank = ctx.get("mae_rank_among_cities")
    rank_note = (
        f"This ranks {mae_rank}{'st' if mae_rank == 1 else 'nd' if mae_rank == 2 else 'rd' if mae_rank == 3 else 'th'} "
        f"most accurate among the four cities."
    ) if mae_rank else ""
    r2 = ctx.get("r2_log")
    within = ctx.get("within_20pct")

    return f"""\
Below are the price model results for {ctx["city"].title()}. Write a \
2-paragraph explanation of model performance for a non-technical reader.

Paragraph 1 — accuracy: explain that a {ctx["algorithm"]} model was trained \
on {ctx["train_rows"]:,} listings and tested on {ctx["test_rows"]:,}. \
The test MAE is {ctx["currency"]} {ctx["mae"]} — meaning predictions are \
typically within that amount of the actual price. \
{f"The model explains {ctx['r2_log']} of log-price variance (R² on log scale). " if r2 else ""}\
{f"{within}% of predictions land within 20% of the actual price. " if within else ""}\
{rank_note}

Paragraph 2 — drivers and limitations: explain which factors drive price \
most (top features: {top}) and note the known limitation that \
luxury listings are systematically under-predicted because the model \
is trained on log-price — it gravitates toward the market average \
in thin, high-price regions.

Data:
{_json_block(ctx)}\
"""


def _clusters_prompt(ctx: dict) -> str:
    k = ctx["k"]
    names = [s["cluster_name"] for s in ctx["segments"]]
    return f"""\
Below are the {k} listing market segments identified for \
{ctx["city"].title()} by K-Means clustering. The segments are ordered \
from lowest to highest median price.

Segment names: {", ".join(names)}.

Write 3 paragraphs:

Paragraph 1 — budget and economy end: describe the cheapest 2–3 segments. \
Include their median price, share of the market, typical accommodation size, \
and dominant room type.

Paragraph 2 — mid-market: describe the middle segments. Focus on what \
distinguishes them — availability patterns, distance from centre, \
review activity.

Paragraph 3 — premium end and unusual segments: describe the most expensive \
segments and highlight any structurally unusual segments (e.g. new/unreviewed \
listings, high-turnover lets). Explain what makes them distinct.

Use {ctx["currency"]} for all prices. Do not list every segment mechanically — \
weave the details into flowing narrative.

Data:
{_json_block(ctx)}\
"""


def _hosts_prompt(ctx: dict) -> str:
    k = ctx["k"]
    names = [s["cluster_name"] for s in ctx["segments"]]
    return f"""\
Below are the {k} host segments identified for {ctx["city"].title()} \
by K-Means clustering on host portfolio data. Segments are ordered \
from largest to smallest share of hosts.

Segment names: {", ".join(names)}.

Write 2–3 paragraphs characterising the host population:

Paragraph 1 — the dominant host type: describe the largest segment. \
Cover what share they represent, their superhost rate, response and \
acceptance rates, typical availability, and what this says about \
the platform health in this city.

Paragraph 2 — professional and occasional hosts: describe the \
superhost-heavy or multi-listing segment versus the casual/occasional \
hosts. What distinguishes their behaviour and portfolio size?

Paragraph 3 (if k ≥ 4) — edge segments: describe any small but notable \
groups such as passive listers (low response, low acceptance) or \
luxury operators. What platform risk or opportunity do they represent?

Data:
{_json_block(ctx)}\
"""


def _cross_city_prompt(ctx: dict) -> str:
    cities = [c["city"].title() for c in ctx["cities"]]
    return f"""\
Below is a side-by-side comparison of four European Airbnb markets: \
{", ".join(cities)}.

Write 3 paragraphs:

Paragraph 1 — price and scale: compare median nightly rates across cities, \
noting currency differences (London in GBP, others in EUR). Comment on \
market size (total listings) and what it implies about competition and \
supply density.

Paragraph 2 — supply structure: compare the share of entire-home listings, \
superhost rates, median availability, and commercial host concentration. \
Highlight the most structurally distinctive market.

Paragraph 3 — predictability and data quality: compare the ML model \
accuracy (MAE) across cities. Explain in plain terms why smaller markets \
like Madrid and Berlin achieve lower MAE than London and Amsterdam despite \
fewer listings. Note any data quality issues (e.g. cities with high \
price-null rates).

Data:
{_json_block(ctx)}\
"""


_RENDERERS = {
    "city":       _city_prompt,
    "model":      _model_prompt,
    "clusters":   _clusters_prompt,
    "hosts":      _hosts_prompt,
    "cross_city": _cross_city_prompt,
}


def render(summary_type: str, context: dict) -> str:
    """Return the user-turn prompt for the given summary type and context."""
    if summary_type not in _RENDERERS:
        raise ValueError(
            f"Unknown summary type '{summary_type}'. "
            f"Valid types: {sorted(VALID_TYPES)}"
        )
    return _RENDERERS[summary_type](context)
