"""Shared path constants for the API layer."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_BASE / "_manifest.csv"
REPORTS_DIR = ROOT / "reports"
NOTEBOOKS_DIR = ROOT / "notebooks"
LOGS_DIR = ROOT / "logs"
