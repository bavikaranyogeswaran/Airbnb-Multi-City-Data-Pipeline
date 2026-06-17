"""Response helpers for reading file-backed artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse


def must_exist(path: Path) -> Path:
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{path.name} not generated yet. Trigger the corresponding pipeline step first.",
        )
    return path


def csv_to_records(path: Path) -> list[dict]:
    must_exist(path)
    df = pd.read_csv(path)
    df = df.where(pd.notna(df), None)
    return df.to_dict(orient="records")


def read_json(path: Path):
    must_exist(path)
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_response(path: Path) -> PlainTextResponse:
    must_exist(path)
    return PlainTextResponse(
        content=path.read_text(encoding="utf-8"),
        media_type="text/markdown",
    )


def html_response(path: Path) -> HTMLResponse:
    must_exist(path)
    return HTMLResponse(content=path.read_text(encoding="utf-8"))
