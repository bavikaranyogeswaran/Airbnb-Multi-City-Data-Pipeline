"""Subprocess runner for pipeline modules.

The existing Phase 1 and Phase 2 CLI scripts (`python -m src.X.Y`)
remain the canonical execution path. The API trigger endpoints invoke
them via the current Python interpreter and capture stdout/stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass

from .paths import ROOT


@dataclass
class RunResult:
    module: str
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_module(module: str, *args: str, timeout: int = 600) -> RunResult:
    """Invoke `python -m <module> [args...]` from the project root.

    The current interpreter (`sys.executable`) is used so the API and
    workers share the same venv.
    """
    cmd = [sys.executable, "-m", module, *args]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return RunResult(
        module=module,
        args=list(args),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        elapsed_seconds=round(time.perf_counter() - started, 2),
    )
