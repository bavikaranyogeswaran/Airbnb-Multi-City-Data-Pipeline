"""Clean neighbourhoods.csv + neighbourhoods.geojson → neighbourhoods_clean.parquet.

Drops `neighbourhood_group` (100% null for London, A-028). Reads the
GeoJSON via GeoPandas, reprojects geometry to EPSG:27700 (British
National Grid, A-029) for area calculation, computes area_km2, and joins
back so the output Parquet carries both the WGS 84 centroid and the
projected area.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
PROCESSED_BASE = ROOT / "data" / "processed"

WGS84 = "EPSG:4326"
OSGB36 = "EPSG:27700"


def run(city: str = "london") -> dict:
    import geopandas as gpd

    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]

        csv_path = RAW_BASE / city / city_cfg["files"]["neighbourhoods"]["name"]
        gj_path = RAW_BASE / city / city_cfg["files"]["neighbourhoods_geojson"]["name"]
        out_dir = PROCESSED_BASE / city
        out_dir.mkdir(parents=True, exist_ok=True)

        csv = pd.read_csv(csv_path)
        csv = csv.drop(columns=[c for c in ("neighbourhood_group",) if c in csv.columns])
        csv["neighbourhood"] = csv["neighbourhood"].astype("string").str.strip()

        gdf = gpd.read_file(gj_path)
        gdf["neighbourhood"] = gdf["neighbourhood"].astype("string").str.strip()
        if "neighbourhood_group" in gdf.columns:
            gdf = gdf.drop(columns="neighbourhood_group")

        if gdf.crs is None:
            gdf = gdf.set_crs(WGS84)
        else:
            gdf = gdf.to_crs(WGS84)

        # Centroid in WGS84
        # Suppress geographic-CRS warning by computing centroid in projected CRS
        projected = gdf.to_crs(OSGB36)
        centroids_proj = projected.geometry.centroid
        centroids_wgs = centroids_proj.to_crs(WGS84)
        csv_join = csv.merge(
            pd.DataFrame({
                "neighbourhood": gdf["neighbourhood"],
                "centroid_latitude": centroids_wgs.y.values,
                "centroid_longitude": centroids_wgs.x.values,
                "area_km2": (projected.geometry.area / 1_000_000).values,
            }),
            on="neighbourhood",
            how="left",
        )

        clean_out = out_dir / "neighbourhoods_clean.parquet"
        csv_join.to_parquet(clean_out, index=False)

        # Also save the GeoJSON's geometry alongside in a separate file via GeoParquet.
        geo_out = out_dir / "neighbourhoods_geo.parquet"
        gdf[["neighbourhood", "geometry"]].to_parquet(geo_out, index=False)

    return make_result(
        step="cleaning.neighbourhoods",
        outputs=[clean_out, geo_out],
        summary={
            "city": city,
            "rows": int(len(csv_join)),
            "centroid_crs": WGS84,
            "area_crs": OSGB36,
            "total_area_km2": round(float(csv_join["area_km2"].sum()), 2),
        },
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    print(run(city=args.city))


if __name__ == "__main__":
    main()
