"""Dataset Familiarization endpoints.

Read endpoints serve the static markdown / CSV / notebook artifacts.
Trigger endpoints call the same `run()` functions the CLI uses.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.profiling import enrich_schema as enrich_mod
from src.profiling import inventory as inventory_mod
from src.profiling import key_integrity as integrity_mod
from src.profiling import schema as schema_mod

from ..helpers import csv_to_records, markdown_response
from ..paths import NOTEBOOKS_DIR, REPORTS_DIR

router = APIRouter(prefix="/familiarization", tags=["familiarization"])


@router.get("", summary="Familiarization index — all available outputs")
def familiarization_index() -> dict:
    return {
        "area": "Dataset Familiarization",
        "reads": {
            "inventory":        "GET  /familiarization/inventory",
            "file_purpose":     "GET  /familiarization/file-purpose",
            "notebook":         "GET  /familiarization/notebook",
            "schema":           "GET  /familiarization/schema",
            "key_integrity":    "GET  /familiarization/key-integrity",
            "business_entities":"GET  /familiarization/business-entities",
            "special_fields":   "GET  /familiarization/special-fields",
            "limitations":      "GET  /familiarization/limitations",
            "assumptions":      "GET  /familiarization/assumptions",
        },
        "triggers": {
            "rebuild_inventory":   "POST /familiarization/inventory:rebuild",
            "rebuild_schema":      "POST /familiarization/schema:rebuild",
            "annotate_schema":     "POST /familiarization/schema:annotate",
            "rebuild_integrity":   "POST /familiarization/key-integrity:rebuild",
        },
    }


# ---------- read ----------

@router.get("/inventory", summary="Step 3 — dataset inventory (JSON)")
def get_inventory() -> list[dict]:
    return csv_to_records(REPORTS_DIR / "dataset_inventory.csv")


@router.get("/file-purpose", summary="Step 4 — per-file purpose (Markdown)")
def get_file_purpose():
    return markdown_response(REPORTS_DIR / "file_purpose.md")


@router.get("/notebook", summary="Step 5 — load notebook metadata")
def get_notebook_meta() -> dict:
    path = NOTEBOOKS_DIR / "01_dataset_familiarization.ipynb"
    if not path.exists():
        raise HTTPException(status_code=404, detail="notebook not present")
    return {
        "path": str(path.relative_to(NOTEBOOKS_DIR.parent)),
        "bytes": path.stat().st_size,
        "note": "Notebook is delivered as a file artifact; download via git/jupyter.",
    }


@router.get("/schema", summary="Steps 6+7 — column profile + annotations (JSON)")
def get_schema() -> list[dict]:
    return csv_to_records(REPORTS_DIR / "schema_documentation.csv")


@router.get("/key-integrity", summary="Step 8 — referential integrity (Markdown)")
def get_key_integrity():
    return markdown_response(REPORTS_DIR / "key_integrity.md")


@router.get("/business-entities", summary="Step 9 — entity glossary (Markdown)")
def get_business_entities():
    return markdown_response(REPORTS_DIR / "business_entities.md")


@router.get("/special-fields", summary="Step 10 — fields needing interpretation (Markdown)")
def get_special_fields():
    return markdown_response(REPORTS_DIR / "special_fields.md")


@router.get("/limitations", summary="Step 11 — dataset limitations (Markdown)")
def get_limitations():
    return markdown_response(REPORTS_DIR / "data_limitations.md")


@router.get("/assumptions", summary="Step 12 — assumptions log (Markdown)")
def get_assumptions():
    return markdown_response(REPORTS_DIR / "assumptions_log.md")


# ---------- triggers ----------

@router.post("/inventory:rebuild", summary="Re-run Step 3")
def rebuild_inventory(city: str = Query("london")) -> dict:
    return inventory_mod.run(city=city)


@router.post("/schema:rebuild", summary="Re-run Step 6")
def rebuild_schema(city: str = Query("london")) -> dict:
    return schema_mod.run(city=city)


@router.post("/schema:annotate", summary="Re-run Step 7")
def annotate_schema() -> dict:
    return enrich_mod.run()


@router.post("/key-integrity:rebuild", summary="Re-run Step 8")
def rebuild_integrity() -> dict:
    return integrity_mod.run()
