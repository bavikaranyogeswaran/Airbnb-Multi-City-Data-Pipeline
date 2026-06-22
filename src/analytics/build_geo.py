"""Build per-city enriched neighbourhood GeoJSON for the map dashboard."""
from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW  = ROOT / "data" / "raw"
TABLES = ROOT / "reports" / "tables"

log = logging.getLogger(__name__)

CITIES = ["london", "amsterdam", "berlin", "madrid"]


def _tables(city: str) -> Path:
    return TABLES if city == "london" else TABLES / city


def _build_city(city: str) -> None:
    tables = _tables(city)

    # ── load raw GeoJSON (polygon geometries only) ────────────────────────────
    geo_path = RAW / city / "neighbourhoods.geojson"
    with geo_path.open(encoding="utf-8") as f:
        raw_geo = json.load(f)

    # ── load density (all neighbourhoods) ────────────────────────────────────
    dens = pd.read_csv(tables / "neighbourhood_density.csv")
    dens = dens.rename(columns={"neighbourhood": "name"})

    # ── load price (may be a top-N subset) ───────────────────────────────────
    price_path = tables / "price_by_neighbourhood.csv"
    price = pd.read_csv(price_path).rename(
        columns={"neighbourhood_cleansed": "name"}
    )
    # keep only price columns; listing_count already in density
    price_cols = ["name", "median_price", "mean_price"] + [
        c for c in ("ci_lower", "ci_upper") if c in price.columns
    ]
    price = price[price_cols]

    # ── merge density + price on neighbourhood name ───────────────────────────
    merged = dens.merge(price, on="name", how="left")
    lookup: dict[str, dict] = {
        str(row["name"]).strip(): row.drop("name").to_dict()
        for _, row in merged.iterrows()
    }
    # Fallback lookups for encoding mismatches (ö/ü/ñ corruption in CSVs)
    ascii_lookup: dict[str, dict] = {_ascii_key(k): v for k, v in lookup.items()}
    corrupt_lookup: dict[str, dict] = {k: v for k, v in lookup.items()}

    # ── enrich GeoJSON features ───────────────────────────────────────────────
    enriched_features: list[dict] = []
    matched = 0
    for feat in raw_geo["features"]:
        raw_name: str = feat["properties"].get("neighbourhood") or ""
        corrupted = _corrupt_key(raw_name)
        stats = (
            lookup.get(raw_name.strip())
            or corrupt_lookup.get(corrupted)
            or ascii_lookup.get(_ascii_key(raw_name), {})
        )

        props: dict = {
            "neighbourhood": raw_name,
            "neighbourhood_group": feat["properties"].get("neighbourhood_group"),
            "listing_count": _int(stats.get("listing_count")),
            "unique_hosts": _int(stats.get("unique_hosts")),
            "listings_per_km2": _float(stats.get("listings_per_km2")),
            "median_price": _float(stats.get("median_price")),
            "mean_price": _float(stats.get("mean_price")),
            "ci_lower": _float(stats.get("ci_lower")),
            "ci_upper": _float(stats.get("ci_upper")),
        }
        if "area_km2" in stats:
            props["area_km2"] = _float(stats["area_km2"])

        if stats:
            matched += 1

        enriched_features.append(
            {"type": "Feature", "geometry": feat["geometry"], "properties": props}
        )

    output = {"type": "FeatureCollection", "features": enriched_features}

    out_path = tables / "neighbourhood_map.geojson"
    with out_path.open("w") as f:
        json.dump(output, f, separators=(",", ":"))

    total = len(enriched_features)
    log.info("%s: %d/%d features enriched -> %s", city, matched, total, out_path)
    print(f"  {city}: {matched}/{total} features enriched -> {out_path.relative_to(ROOT)}")


def _ascii_key(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def _corrupt_key(s: str) -> str:
    """Simulate reading a latin-1 string as UTF-8 (errors=replace).

    Our pipeline ingested raw listings CSVs that are latin-1 encoded but opened
    as UTF-8, so non-ASCII chars (ö, ü, ñ …) became U+FFFD replacement chars.
    Applying the same transform to the correctly-encoded GeoJSON names lets us
    join across the encoding mismatch.
    """
    try:
        return s.encode("latin-1").decode("utf-8", errors="replace").strip()
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s.strip()


def _int(v: Any) -> int | None:
    try:
        return int(v) if v is not None and str(v) != "nan" else None
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        f = float(v) if v is not None and str(v) != "nan" else None
        return round(f, 2) if f is not None else None
    except (TypeError, ValueError):
        return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("Building enriched neighbourhood GeoJSON...")
    for city in CITIES:
        _build_city(city)
    print("Done.")


if __name__ == "__main__":
    main()
