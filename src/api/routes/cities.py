"""City configuration endpoints."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException

from ..paths import CONFIG_PATH

router = APIRouter(prefix="/cities", tags=["cities"])


def _load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.get("", summary="List configured cities")
def list_cities() -> dict:
    cfg = _load_config()
    return {
        "count": len(cfg["cities"]),
        "cities": [
            {
                "code": code,
                "name": city["name"],
                "country": city["country"],
                "snapshot_date": city["source"]["snapshot_date"],
            }
            for code, city in cfg["cities"].items()
        ],
    }


@router.get("/{code}", summary="Get full configuration for one city")
def get_city(code: str) -> dict:
    cfg = _load_config()
    if code not in cfg["cities"]:
        raise HTTPException(status_code=404, detail=f"Unknown city: {code}")
    return cfg["cities"][code]
