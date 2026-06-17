"""Config-driven downloader with retry, checksumming, and an append-only manifest.

The 7 files for London 2025-09-14 are already on disk. Running this
module is idempotent: for each file in `config/cities.yml`, it checks
the existing checksum, records or refreshes the manifest entry, and
only downloads if the file is missing or `--force` is passed.

Manifest at `data/raw/_manifest.csv`:
  city, snapshot_date, file_key, file_name, url,
  started_at, finished_at, bytes, sha256, status, error
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import logging
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_BASE / "_manifest.csv"
LOGS_DIR = ROOT / "logs"

MANIFEST_COLUMNS = [
    "city", "snapshot_date", "file_key", "file_name", "url",
    "started_at", "finished_at", "bytes", "sha256", "status", "error",
]

log = logging.getLogger("ingest")


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "ingest.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def sha256_of(path: Path, chunk: int = 8192) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def download_with_retry(
    url: str,
    destination: Path,
    timeout: int = 60,
    max_attempts: int = 4,
    backoff_base: float = 2.0,
) -> int:
    """Download `url` to `destination` with retry+backoff. Returns bytes written."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            with requests.get(url, timeout=timeout, stream=True) as r:
                r.raise_for_status()
                total = 0
                with destination.open("wb") as f:
                    for block in r.iter_content(chunk_size=65536):
                        if block:
                            total += len(block)
                            f.write(block)
                return total
        except requests.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if 400 <= status < 500:
                # Don't retry client errors (bad URL, 404, 403).
                raise
            last_exc = e
        except requests.RequestException as e:
            last_exc = e
        sleep = backoff_base ** attempt
        log.warning("attempt %d/%d failed for %s: %s; sleeping %.1fs",
                    attempt, max_attempts, url, last_exc, sleep)
        time.sleep(sleep)
    raise RuntimeError(f"download failed after {max_attempts} attempts: {url}") from last_exc


def append_manifest(rows: list[dict]) -> None:
    is_new = not MANIFEST_PATH.exists()
    with MANIFEST_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in MANIFEST_COLUMNS})


def process_file(city_code: str, snapshot: str, key: str, file_cfg: dict, force: bool) -> dict:
    raw_dir = RAW_BASE / city_code
    name = file_cfg["name"]
    url = file_cfg["url"]
    destination = raw_dir / name

    row = {
        "city": city_code,
        "snapshot_date": snapshot,
        "file_key": key,
        "file_name": name,
        "url": url,
        "started_at": now_iso(),
        "finished_at": "",
        "bytes": "",
        "sha256": "",
        "status": "",
        "error": "",
    }

    try:
        if destination.exists() and not force:
            row["status"] = "present"
            row["bytes"] = destination.stat().st_size
            row["sha256"] = sha256_of(destination)
            row["finished_at"] = now_iso()
            log.info("%-26s present (%d bytes, sha256=%s...)",
                     name, row["bytes"], row["sha256"][:10])
            return row

        log.info("%-26s downloading from %s", name, url)
        written = download_with_retry(url, destination)
        row["bytes"] = written
        row["sha256"] = sha256_of(destination)
        row["finished_at"] = now_iso()
        row["status"] = "downloaded"
        log.info("%-26s downloaded (%d bytes, sha256=%s...)",
                 name, written, row["sha256"][:10])
    except Exception as e:
        row["status"] = "error"
        row["error"] = f"{type(e).__name__}: {e}"
        row["finished_at"] = now_iso()
        log.error("%-26s FAILED: %s", name, row["error"])

    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if file is present.")
    args = parser.parse_args()

    setup_logging()
    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    city_cfg = cfg["cities"][args.city]
    snapshot = city_cfg["source"]["snapshot_date"]

    log.info("ingest start: city=%s snapshot=%s force=%s",
             args.city, snapshot, args.force)

    rows = []
    for key, file_cfg in city_cfg["files"].items():
        rows.append(process_file(args.city, snapshot, key, file_cfg, args.force))

    append_manifest(rows)
    log.info("manifest updated: %s (+%d rows)", MANIFEST_PATH, len(rows))

    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    log.info("status counts: %s", by_status)


if __name__ == "__main__":
    main()
