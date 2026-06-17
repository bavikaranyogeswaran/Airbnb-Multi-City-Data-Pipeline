"""Shared result type returned by every pipeline `run()` function.

The same dict shape is consumed by the CLI wrappers (printed) and the
FastAPI endpoints (returned as JSON).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def make_result(
    step: str,
    *,
    status: str = "ok",
    outputs: list[Path] | None = None,
    summary: dict[str, Any] | None = None,
    elapsed_seconds: float | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "step": step,
        "status": status,
        "outputs": [str(p) for p in (outputs or [])],
        "summary": summary or {},
        "elapsed_seconds": elapsed_seconds,
        "error": error,
    }


@contextmanager
def timed():
    """Yield a function that returns elapsed seconds since the block started."""
    started = time.perf_counter()
    yield lambda: round(time.perf_counter() - started, 2)
