"""Fill in expected_type / business_meaning / cleaning_requirement on schema_documentation.csv.

Annotations are curated by hand based on the Inside Airbnb data dictionary
and the profile findings for the London 2025-09-14 snapshot. Reading
expected_type tells Phase 2.2 what to coerce; cleaning_requirement
tells it how.

Format of CLEANING actions used downstream:
  none                  no change
  parse_date            pd.to_datetime(errors='coerce')
  parse_money           strip $ and , -> float
  parse_percent         strip % -> float; divide by 100
  parse_bool            t/true/1/yes -> True; f/false/0/no -> False; else NULL
  parse_json_list       json.loads -> Python list
  parse_python_list     ast.literal_eval -> Python list
  parse_bathrooms_text  e.g. "1.5 shared baths" -> (count=1.5, private=False)
  trim                  strip whitespace
  cap_sentinel_intmax   replace 2**31-1 (and similar) with NULL
  normalize_category    lower, strip, map known synonyms
  validate_lat          numeric in [-90, 90]
  validate_lon          numeric in [-180, 180]
  validate_range_0_365  integer in [0, 365]
  drop                  exclude from clean output (e.g. 100% null fields, scrape URLs)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "reports" / "schema_documentation.csv"


# (source_file, column_name) -> (expected_type, business_meaning, cleaning_requirement)
A: dict[tuple[str, str], tuple[str, str, str]] = {}


def annotate(source: str, column: str, expected_type: str, meaning: str, cleaning: str) -> None:
    A[(source, column)] = (expected_type, meaning, cleaning)


# ---------- listings.csv.gz (detailed, 79 cols) ----------
LD = "listings.csv.gz"

# identity / scrape
annotate(LD, "id",                            "integer (PK)",   "Listing identifier (source primary key).",                                  "none")
annotate(LD, "listing_url",                   "string",         "URL to the listing page on airbnb.com.",                                    "drop")
annotate(LD, "scrape_id",                     "integer",        "Inside Airbnb scrape batch identifier.",                                    "drop")
annotate(LD, "last_scraped",                  "date",           "Date the listing was scraped from Airbnb.",                                 "parse_date")
annotate(LD, "source",                        "category",       "Inside Airbnb scrape source channel (search vs. discovery).",               "normalize_category")
annotate(LD, "name",                          "string",         "Listing title shown to guests.",                                            "trim")
annotate(LD, "description",                   "string",         "Long-form listing description (marketing copy).",                           "trim")
annotate(LD, "neighborhood_overview",         "string",         "Host-written description of the neighbourhood.",                            "trim")
annotate(LD, "picture_url",                   "string",         "Hero image URL for the listing.",                                           "drop")

# host (denormalised)
annotate(LD, "host_id",                       "integer (FK)",   "Host identifier; foreign key to derived dim_host.",                         "none")
annotate(LD, "host_url",                      "string",         "URL to the host profile on airbnb.com.",                                    "drop")
annotate(LD, "host_name",                     "string",         "Host display name.",                                                        "trim")
annotate(LD, "host_since",                    "date",           "Date the host joined the platform.",                                        "parse_date")
annotate(LD, "host_location",                 "string",         "Host's self-reported home location (free text).",                           "trim")
annotate(LD, "host_about",                    "string",         "Host bio.",                                                                 "trim")
annotate(LD, "host_response_time",            "category",       "Bucketed response time ('within an hour', etc.).",                          "normalize_category")
annotate(LD, "host_response_rate",            "percentage",     "Fraction of guest messages the host responds to (0-1 after cleaning).",     "parse_percent")
annotate(LD, "host_acceptance_rate",          "percentage",     "Fraction of booking requests the host accepts (0-1 after cleaning).",       "parse_percent")
annotate(LD, "host_is_superhost",             "boolean",        "Superhost status flag.",                                                    "parse_bool")
annotate(LD, "host_thumbnail_url",            "string",         "Host profile thumbnail URL.",                                               "drop")
annotate(LD, "host_picture_url",              "string",         "Host profile picture URL.",                                                 "drop")
annotate(LD, "host_neighbourhood",            "string",         "Host's self-reported neighbourhood (free text, often missing).",            "trim")
annotate(LD, "host_listings_count",           "integer",        "Listings count reported by the host on their profile.",                     "none")
annotate(LD, "host_total_listings_count",     "integer",        "Total listings count as observed by Airbnb (incl. inactive).",              "none")
annotate(LD, "host_verifications",            "list[string]",   "Verification methods (email, phone, etc.) as a Python-literal list.",       "parse_python_list")
annotate(LD, "host_has_profile_pic",          "boolean",        "Profile picture present flag.",                                             "parse_bool")
annotate(LD, "host_identity_verified",        "boolean",        "Identity verification flag.",                                               "parse_bool")

# geography
annotate(LD, "neighbourhood",                 "string",         "Raw self-reported neighbourhood text (often blank).",                       "trim")
annotate(LD, "neighbourhood_cleansed",        "string (FK)",    "Inside Airbnb-cleansed neighbourhood (= London borough). Joins to dim_neighbourhood.", "trim")
annotate(LD, "neighbourhood_group_cleansed",  "string",         "Parent geography group; null for all London rows in this snapshot.",        "drop")
annotate(LD, "latitude",                      "decimal",        "Listing latitude in WGS 84 degrees.",                                       "validate_lat")
annotate(LD, "longitude",                     "decimal",        "Listing longitude in WGS 84 degrees.",                                      "validate_lon")

# physical
annotate(LD, "property_type",                 "category",       "Granular property type (91 distinct values; long tail).",                   "normalize_category")
annotate(LD, "room_type",                     "category",       "One of {entire_home, private_room, shared_room, hotel_room}.",              "normalize_category")
annotate(LD, "accommodates",                  "integer",        "Maximum guest capacity.",                                                   "none")
annotate(LD, "bathrooms",                     "decimal",        "Bathroom count (half-baths as 0.5).",                                       "none")
annotate(LD, "bathrooms_text",                "string",         "Textual bathroom description, e.g. '1.5 shared baths'.",                    "parse_bathrooms_text")
annotate(LD, "bedrooms",                      "integer",        "Bedroom count. Keep NULL where missing.",                                   "none")
annotate(LD, "beds",                          "integer",        "Bed count. Keep NULL where missing.",                                       "none")
annotate(LD, "amenities",                     "list[string]",   "JSON list of amenity strings.",                                             "parse_json_list")

# pricing & stay rules
annotate(LD, "price",                         "decimal (GBP)",  "Nightly price; 36% null in this snapshot.",                                 "parse_money")
annotate(LD, "minimum_nights",                "integer",        "Default minimum-night stay rule.",                                          "cap_sentinel_intmax")
annotate(LD, "maximum_nights",                "integer",        "Default maximum-night stay rule.",                                          "cap_sentinel_intmax")
annotate(LD, "minimum_minimum_nights",        "integer",        "Min observed minimum_nights across the 365-day calendar.",                  "cap_sentinel_intmax")
annotate(LD, "maximum_minimum_nights",        "integer",        "Max observed minimum_nights across the 365-day calendar.",                  "cap_sentinel_intmax")
annotate(LD, "minimum_maximum_nights",        "integer",        "Min observed maximum_nights across the 365-day calendar.",                  "cap_sentinel_intmax")
annotate(LD, "maximum_maximum_nights",        "integer",        "Max observed maximum_nights across the 365-day calendar.",                  "cap_sentinel_intmax")
annotate(LD, "minimum_nights_avg_ntm",        "decimal",        "Average minimum_nights over the next-twelve-months calendar.",              "none")
annotate(LD, "maximum_nights_avg_ntm",        "decimal",        "Average maximum_nights over the next-twelve-months calendar.",              "none")

# availability
annotate(LD, "calendar_updated",              "string",         "Date calendar was last updated by host; 100% null.",                        "drop")
annotate(LD, "has_availability",              "boolean",        "Whether the listing has any available days in the calendar.",               "parse_bool")
annotate(LD, "availability_30",               "integer",        "Available days in the next 30 days.",                                       "validate_range_0_365")
annotate(LD, "availability_60",               "integer",        "Available days in the next 60 days.",                                       "validate_range_0_365")
annotate(LD, "availability_90",               "integer",        "Available days in the next 90 days.",                                       "validate_range_0_365")
annotate(LD, "availability_365",              "integer",        "Available days in the next 365 days.",                                      "validate_range_0_365")
annotate(LD, "calendar_last_scraped",         "date",           "Date the calendar slice was scraped.",                                      "parse_date")
annotate(LD, "availability_eoy",              "integer",        "Available days from snapshot date to year-end.",                            "validate_range_0_365")

# activity
annotate(LD, "number_of_reviews",             "integer",        "Lifetime review count.",                                                    "none")
annotate(LD, "number_of_reviews_ltm",         "integer",        "Reviews in the last twelve months.",                                        "none")
annotate(LD, "number_of_reviews_l30d",        "integer",        "Reviews in the last 30 days.",                                              "none")
annotate(LD, "number_of_reviews_ly",          "integer",        "Reviews in the previous calendar year.",                                    "none")
annotate(LD, "estimated_occupancy_l365d",     "integer",        "Inside Airbnb's estimated occupied nights in last 365 days. Do not trust blindly (blocked-vs-booked).", "none")
annotate(LD, "estimated_revenue_l365d",       "decimal (GBP)",  "Inside Airbnb's estimated revenue in last 365 days. Same caveat as occupancy.", "none")
annotate(LD, "first_review",                  "date",           "Date of the first review on this listing.",                                 "parse_date")
annotate(LD, "last_review",                   "date",           "Date of the most recent review on this listing.",                           "parse_date")
annotate(LD, "reviews_per_month",             "decimal",        "Inside Airbnb's derived review velocity. Recompute in 2.3.",                 "none")

# review scores
annotate(LD, "review_scores_rating",          "decimal",        "Aggregate review score 0-5; null for listings with no reviews.",            "none")
annotate(LD, "review_scores_accuracy",        "decimal",        "Sub-score: accuracy of listing description.",                               "none")
annotate(LD, "review_scores_cleanliness",     "decimal",        "Sub-score: cleanliness.",                                                   "none")
annotate(LD, "review_scores_checkin",         "decimal",        "Sub-score: check-in smoothness.",                                           "none")
annotate(LD, "review_scores_communication",   "decimal",        "Sub-score: host communication.",                                            "none")
annotate(LD, "review_scores_location",        "decimal",        "Sub-score: location.",                                                      "none")
annotate(LD, "review_scores_value",           "decimal",        "Sub-score: value for money.",                                               "none")

# regulatory
annotate(LD, "license",                       "string",         "Short-term rental licence number; 100% null in this snapshot.",             "drop")
annotate(LD, "instant_bookable",              "boolean",        "Whether guests can book without host approval.",                            "parse_bool")

# IA-derived host portfolio
annotate(LD, "calculated_host_listings_count",                  "integer", "Inside Airbnb-counted listings for this host in this city.", "none")
annotate(LD, "calculated_host_listings_count_entire_homes",     "integer", "Of which: entire homes.",                                     "none")
annotate(LD, "calculated_host_listings_count_private_rooms",    "integer", "Of which: private rooms.",                                    "none")
annotate(LD, "calculated_host_listings_count_shared_rooms",     "integer", "Of which: shared rooms.",                                     "none")


# ---------- calendar.csv.gz (7 cols) ----------
CA = "calendar.csv.gz"
annotate(CA, "listing_id",     "integer (FK)",  "Foreign key to listings.id.",                                                "none")
annotate(CA, "date",           "date",          "Calendar date; ~365 days forward of snapshot.",                              "parse_date")
annotate(CA, "available",      "boolean",       "t = available, f = unavailable. f does NOT imply booked (A-002).",           "parse_bool")
annotate(CA, "price",          "decimal (GBP)", "Per-date posted price; 100% null in this snapshot (A-005).",                 "drop")
annotate(CA, "adjusted_price", "decimal (GBP)", "Inside Airbnb's cleaned per-date price; 100% null in this snapshot.",        "drop")
annotate(CA, "minimum_nights", "integer",       "Per-date minimum-stay override; can differ from listing default.",           "cap_sentinel_intmax")
annotate(CA, "maximum_nights", "integer",       "Per-date maximum-stay override; replace INT_MAX sentinel with NULL.",        "cap_sentinel_intmax")


# ---------- reviews.csv.gz (6 cols) ----------
RD = "reviews.csv.gz"
annotate(RD, "listing_id",    "integer (FK)", "Foreign key to listings.id. Orphans expected and counted in Step 8.", "none")
annotate(RD, "id",            "integer (PK)", "Review identifier.",                                                  "none")
annotate(RD, "date",          "date",         "Review date.",                                                        "parse_date")
annotate(RD, "reviewer_id",   "integer",      "Reviewer identifier (no separate reviewer dim available).",           "none")
annotate(RD, "reviewer_name", "string",       "Reviewer display name.",                                              "trim")
annotate(RD, "comments",      "string",       "Free-text review body; multi-line.",                                  "trim")


# ---------- listings.csv (summary, 18 cols) ----------
LS = "listings.csv"
SUMMARY_NOTE = "Use the detailed file (listings.csv.gz) instead; this summary is non-canonical."
for col in ["id", "name", "host_id", "host_name", "neighbourhood_group", "neighbourhood",
            "latitude", "longitude", "room_type", "price", "minimum_nights",
            "number_of_reviews", "last_review", "reviews_per_month",
            "calculated_host_listings_count", "availability_365",
            "number_of_reviews_ltm", "license"]:
    annotate(LS, col, "(see detailed file)", SUMMARY_NOTE, "drop")


# ---------- reviews.csv (summary, 2 cols) ----------
RS = "reviews.csv"
for col in ["listing_id", "date"]:
    annotate(RS, col, "(see detailed file)", "Use the detailed file (reviews.csv.gz) instead; this summary is non-canonical.", "drop")


# ---------- neighbourhoods.csv (2 cols) ----------
NC = "neighbourhoods.csv"
annotate(NC, "neighbourhood_group", "string", "Parent group; 100% null for London.", "drop")
annotate(NC, "neighbourhood",       "string (PK)", "Borough name; primary key for dim_neighbourhood.", "trim")


# ---------- neighbourhoods.geojson (3 cols) ----------
NG = "neighbourhoods.geojson"
annotate(NG, "neighbourhood",       "string (FK)", "Borough name; joins to neighbourhoods.csv.", "trim")
annotate(NG, "neighbourhood_group", "string",      "Parent group; 100% null for London.", "drop")
annotate(NG, "geometry_type",       "string",      "GeoJSON geometry type (MultiPolygon for all 33 features).", "none")


def apply_annotations(schema: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    missing: list[tuple[str, str]] = []
    for idx, row in schema.iterrows():
        key = (row["source_file"], row["column_name"])
        ann = A.get(key)
        if ann is None:
            missing.append(key)
            continue
        schema.at[idx, "expected_type"] = ann[0]
        schema.at[idx, "business_meaning"] = ann[1]
        schema.at[idx, "cleaning_requirement"] = ann[2]
    return schema, missing


def run(schema_path: str | None = None) -> dict:
    from src.api.result import make_result, timed

    path = schema_path or str(SCHEMA_PATH)

    with timed() as elapsed:
        schema = pd.read_csv(path)
        for col in ("expected_type", "business_meaning", "cleaning_requirement"):
            if col not in schema.columns:
                schema[col] = ""
            schema[col] = schema[col].fillna("")

        enriched, missing = apply_annotations(schema)
        enriched.to_csv(path, index=False)

    total = len(enriched)
    return make_result(
        step="familiarization.enrich_schema",
        outputs=[SCHEMA_PATH],
        summary={
            "total_columns": total,
            "annotated": total - len(missing),
            "missing": [{"source_file": s, "column": c} for s, c in missing],
            "cleaning_requirement_counts": enriched["cleaning_requirement"].value_counts().to_dict(),
        },
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", default=str(SCHEMA_PATH))
    args = parser.parse_args()
    print(run(schema_path=args.schema))


if __name__ == "__main__":
    main()
