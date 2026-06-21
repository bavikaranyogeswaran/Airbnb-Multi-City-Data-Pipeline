# Change Data Capture (CDC) Architecture for Listings

**Project:** Inside Airbnb Data Engineering Assessment — Expernec Pvt Ltd  
**Author:** Data Engineering Team  
**Date:** 2026-06-21  
**Status:** Design Document (not implemented — see §1 for rationale)

---

## Table of Contents

1. [Why CDC Is Not Implemented Here](#1-why-cdc-is-not-implemented-here)
2. [Target Architecture Overview](#2-target-architecture-overview)
3. [Component Design](#3-component-design)
   - 3.1 Source — PostgreSQL Operational Database
   - 3.2 Debezium Connector
   - 3.3 Kafka Topics
   - 3.4 Stream Processor
   - 3.5 DuckDB Upsert Layer
4. [CDC Event Schema](#4-cdc-event-schema)
5. [SCD-2 Strategy for the Listings Table](#5-scd-2-strategy-for-the-listings-table)
6. [Exactly-Once Guarantees and Failure Handling](#6-exactly-once-guarantees-and-failure-handling)
7. [Comparison: Current Snapshot Approach vs CDC](#7-comparison-current-snapshot-approach-vs-cdc)
8. [Migration Path from Snapshots to CDC](#8-migration-path-from-snapshots-to-cdc)

---

## 1. Why CDC Is Not Implemented Here

Inside Airbnb publishes **monthly static snapshots** scraped from the public website. There is no operational database, no write-ahead log (WAL), and no streaming source signal — the prerequisites for CDC do not exist in this dataset.

The current pipeline treats each city snapshot as a full reload:

```
listings.csv.gz (monthly) → clean → feature-engineer → load into DuckDB warehouse
```

This is correct for the data source. CDC would be applicable in a production Airbnb-like system where:

- Listings are created, updated, and deleted in real time by hosts
- Prices change dynamically (smart pricing, manual edits)
- Availability and calendar blocks are set and released continuously
- Regulatory status changes (e.g., licence revoked, neighbourhood cap reached)

The sections below describe how CDC would be designed for that production scenario.

---

## 2. Target Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  OPERATIONAL LAYER                                                       │
│                                                                         │
│  ┌──────────────────┐    WAL streaming     ┌──────────────────────┐    │
│  │  PostgreSQL       │ ──────────────────► │  Debezium Connector  │    │
│  │  (listings DB)    │   (pg_logical /      │  (Kafka Connect)     │    │
│  │                   │    wal2json)         │                      │    │
│  │  Tables:          │                     │  - Captures INSERT   │    │
│  │  • listings       │                     │  - Captures UPDATE   │    │
│  │  • calendar       │                     │  - Captures DELETE   │    │
│  │  • hosts          │                     │  - Schema registry   │    │
│  └──────────────────┘                     └──────────┬───────────┘    │
└──────────────────────────────────────────────────────┼─────────────────┘
                                                        │
                                          CDC events (Avro)
                                                        │
┌───────────────────────────────────────────────────────▼────────────────┐
│  STREAMING LAYER                                                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  Apache Kafka                                               │       │
│  │                                                             │       │
│  │  Topic: airbnb.listings.changes   (partitioned by city_id)  │       │
│  │  Topic: airbnb.calendar.changes   (partitioned by city_id)  │       │
│  │  Topic: airbnb.hosts.changes      (partitioned by host_id)  │       │
│  │                                                             │       │
│  │  Retention: 7 days (replay window for late consumers)       │       │
│  └─────────────────────────┬───────────────────────────────────┘       │
└─────────────────────────────┼──────────────────────────────────────────┘
                              │
                    Consume + transform
                              │
┌─────────────────────────────▼──────────────────────────────────────────┐
│  PROCESSING LAYER                                                       │
│                                                                         │
│  ┌──────────────────────┐      ┌──────────────────────────────────┐    │
│  │  Stream Processor    │      │  Dead-Letter Queue               │    │
│  │  (Flink / Spark      │      │  airbnb.listings.changes.dlq     │    │
│  │   Structured         ├─────►│  (malformed / schema-mismatch    │    │
│  │   Streaming)         │      │   events held for inspection)    │    │
│  │                      │      └──────────────────────────────────┘    │
│  │  - Deduplicate       │                                              │
│  │  - Validate schema   │                                              │
│  │  - Route by op type  │                                              │
│  │  - Watermark track   │                                              │
│  └──────────┬───────────┘                                              │
└─────────────┼──────────────────────────────────────────────────────────┘
              │
       Upsert / SCD-2
              │
┌─────────────▼──────────────────────────────────────────────────────────┐
│  STORAGE LAYER                                                          │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  DuckDB Warehouse  (per city)                                │      │
│  │                                                              │      │
│  │  dim_listing        ← SCD-2 (INSERT new version on change)   │      │
│  │  dim_host           ← SCD-2                                  │      │
│  │  fact_listing_snap  ← append-only daily snapshots            │      │
│  │  fact_calendar      ← upsert on (listing_key, date_key)      │      │
│  │  cdc_watermark      ← tracks last applied LSN per table      │      │
│  └──────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Design

### 3.1 Source — PostgreSQL Operational Database

CDC requires PostgreSQL to be configured with logical replication:

```sql
-- postgresql.conf
wal_level = logical
max_replication_slots = 4
max_wal_senders = 4

-- Create a replication slot for Debezium
SELECT pg_create_logical_replication_slot('debezium_listings', 'pgoutput');

-- Grant replication privileges
ALTER ROLE airbnb_cdc_user REPLICATION LOGIN;
GRANT SELECT ON TABLE listings, calendar, hosts TO airbnb_cdc_user;
```

The `listings` table requires a primary key and `REPLICA IDENTITY FULL` so that UPDATE events include the full before-image (needed to detect which fields changed):

```sql
ALTER TABLE listings REPLICA IDENTITY FULL;
```

### 3.2 Debezium Connector

Debezium is deployed as a Kafka Connect plugin. The connector configuration for the listings table:

```json
{
  "name": "airbnb-listings-cdc",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "pg-operational.internal",
    "database.port": "5432",
    "database.user": "airbnb_cdc_user",
    "database.password": "${file:/opt/kafka/connect-secrets.properties:pg.password}",
    "database.dbname": "airbnb_operational",
    "database.server.name": "airbnb",
    "table.include.list": "public.listings,public.calendar,public.hosts",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_listings",
    "publication.name": "airbnb_cdc_pub",

    "key.converter": "io.confluent.kafka.serializers.KafkaAvroSerializer",
    "value.converter": "io.confluent.kafka.serializers.KafkaAvroSerializer",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter.schema.registry.url": "http://schema-registry:8081",

    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.ReplaceField$Value",
    "snapshot.mode": "initial",
    "heartbeat.interval.ms": "30000",
    "tombstones.on.delete": "true"
  }
}
```

**Snapshot mode `initial`**: on first startup Debezium performs a consistent snapshot of the entire table, then switches to streaming from the WAL. This ensures no events are missed at the seam.

### 3.3 Kafka Topics

Each source table maps to one Kafka topic. Topics are **partitioned by `city_id`** so all events for a city land on the same partition, preserving per-city ordering:

| Topic | Partitions | Key | Retention |
|---|---|---|---|
| `airbnb.public.listings` | 20 (one per city shard) | `listing_id` | 7 days |
| `airbnb.public.calendar` | 20 | `listing_id` | 3 days |
| `airbnb.public.hosts` | 10 | `host_id` | 7 days |
| `airbnb.listings.changes.dlq` | 5 | `listing_id` | 30 days |

Replication factor: 3 (tolerate 1 broker loss without data loss).

### 3.4 Stream Processor

A Flink job (or Spark Structured Streaming) consumes from the Kafka topics, deduplicates events within a 30-second window (Debezium can emit duplicates across connector restarts), and routes by operation type:

```python
# Pseudocode — Flink PyFlink or PySpark Structured Streaming

def process_listing_event(event: dict) -> None:
    op   = event["op"]        # "c" = create, "u" = update, "d" = delete, "r" = snapshot read
    before = event["before"]  # row state before the change (None for inserts)
    after  = event["after"]   # row state after the change (None for deletes)
    lsn    = event["source"]["lsn"]   # PostgreSQL log sequence number
    ts_ms  = event["source"]["ts_ms"] # event timestamp in milliseconds

    if op in ("c", "r"):
        upsert_listing(after, lsn, ts_ms, is_delete=False)
    elif op == "u":
        close_scd2_version(before["listing_id"], ts_ms)
        upsert_listing(after, lsn, ts_ms, is_delete=False)
    elif op == "d":
        close_scd2_version(before["listing_id"], ts_ms)
        upsert_listing(before, lsn, ts_ms, is_delete=True)
```

### 3.5 DuckDB Upsert Layer

DuckDB does not support row-level streaming writes natively, so the consumer accumulates a micro-batch (e.g. 500 events or 10 seconds, whichever comes first) and applies them in a single transaction:

```python
import duckdb

def apply_micro_batch(events: list[dict], city: str) -> None:
    con = duckdb.connect(f"data/processed/{city}/warehouse.duckdb")
    con.begin()
    try:
        for e in events:
            _apply_one(con, e)
        _advance_watermark(con, events[-1]["lsn"], "listings")
        con.commit()
    except Exception:
        con.rollback()
        raise

def _apply_one(con, event: dict) -> None:
    if event["is_delete"]:
        con.execute("""
            UPDATE dim_listing
            SET is_current = FALSE, valid_to = ?
            WHERE listing_id = ? AND is_current = TRUE
        """, [event["ts_ms"], event["listing_id"]])
    else:
        con.execute("""
            INSERT INTO dim_listing (
                listing_key, listing_id, city_id, host_key,
                room_type, property_type_bucket, neighbourhood_cleansed,
                accommodates, bedrooms, price_numeric,
                valid_from, valid_to, is_current
            )
            VALUES (nextval('dim_listing_seq'), ?, ?, ?,  ?, ?, ?,  ?, ?, ?,  ?, NULL, TRUE)
            ON CONFLICT (listing_id, is_current) WHERE is_current = TRUE
            DO UPDATE SET
                room_type               = excluded.room_type,
                price_numeric           = excluded.price_numeric,
                neighbourhood_cleansed  = excluded.neighbourhood_cleansed
        """, [event["listing_id"], event["city_id"], event["host_key"],
              event["room_type"], event["property_type_bucket"],
              event["neighbourhood_cleansed"], event["accommodates"],
              event["bedrooms"], event["price_numeric"], event["ts_ms"]])
```

---

## 4. CDC Event Schema

Debezium wraps every row change in an **envelope** with before/after images. Example UPDATE event for a price change:

```json
{
  "schema": { "type": "struct", "name": "airbnb.public.listings.Envelope" },
  "payload": {
    "op": "u",
    "ts_ms": 1750550400000,
    "source": {
      "version": "2.5.0.Final",
      "connector": "postgresql",
      "name": "airbnb",
      "ts_ms": 1750550399800,
      "db": "airbnb_operational",
      "table": "listings",
      "lsn": 28472910,
      "txId": 5041
    },
    "before": {
      "listing_id": 12345,
      "city_id": "london",
      "price_numeric": 120.00,
      "room_type": "entire_home",
      "updated_at": "2026-06-20T10:00:00Z"
    },
    "after": {
      "listing_id": 12345,
      "city_id": "london",
      "price_numeric": 145.00,
      "room_type": "entire_home",
      "updated_at": "2026-06-21T09:00:00Z"
    }
  }
}
```

Key fields used downstream:

| Field | Purpose |
|---|---|
| `op` | Route to INSERT / SCD-2 close / soft-delete logic |
| `source.lsn` | Watermark — tracks exactly how far we've consumed |
| `source.ts_ms` | Event time for `valid_from` / `valid_to` in SCD-2 |
| `before` | Needed to identify which SCD-2 row to close |
| `after` | The new state to insert |

---

## 5. SCD-2 Strategy for the Listings Table

Slowly Changing Dimension Type 2 preserves the full history of listing attributes by adding a new row for every material change, rather than overwriting.

**Schema additions to `dim_listing`:**

```sql
ALTER TABLE dim_listing ADD COLUMN valid_from   TIMESTAMPTZ NOT NULL;
ALTER TABLE dim_listing ADD COLUMN valid_to     TIMESTAMPTZ;          -- NULL = current version
ALTER TABLE dim_listing ADD COLUMN is_current   BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE dim_listing ADD COLUMN source_lsn   BIGINT;               -- for deduplication
ALTER TABLE dim_listing ADD COLUMN is_deleted   BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX uq_dim_listing_current
    ON dim_listing (listing_id)
    WHERE is_current = TRUE;
```

**SCD-2 lifecycle for a listing that changes price:**

```
listing_id  price   valid_from            valid_to              is_current
──────────  ──────  ────────────────────  ────────────────────  ──────────
12345       £120    2026-01-01 00:00:00   2026-06-21 09:00:00   FALSE
12345       £145    2026-06-21 09:00:00   NULL                  TRUE
```

**Which fields trigger a new SCD-2 version?**

Not every column change warrants a new version. The following fields are defined as *tracked* (trigger SCD-2):

| Column | Rationale |
|---|---|
| `price_numeric` | Core analytical metric; history needed for trend analysis |
| `room_type` | Structural change — changes query semantics |
| `neighbourhood_cleansed` | Rare but material; affects geographic analysis |
| `host_id` | Ownership transfer |
| `property_type_bucket` | Structural reclassification |

*Untracked* columns (overwrite in place):
`last_scraped`, `availability_365`, `number_of_reviews`, `review_scores_rating`
— these are volatile metrics better captured in `fact_listing_snapshot` snapshots.

---

## 6. Exactly-Once Guarantees and Failure Handling

### Watermark Table

```sql
CREATE TABLE cdc_watermark (
    table_name    VARCHAR PRIMARY KEY,
    last_lsn      BIGINT  NOT NULL,
    last_event_ts TIMESTAMPTZ,
    applied_at    TIMESTAMPTZ DEFAULT now()
);
```

On consumer restart, it reads `last_lsn` and tells the Kafka consumer to seek to the offset corresponding to that LSN — re-processing any events after the last committed LSN. The SCD-2 upsert is idempotent (ON CONFLICT DO UPDATE), so re-applying an already-seen event is safe.

### Dead-Letter Queue

Events that fail schema validation or cause a DuckDB constraint violation are routed to `airbnb.listings.changes.dlq` with a header `failure_reason`. A separate monitoring job reads the DLQ and pages on-call if the DLQ depth exceeds 100 events.

### Ordering Guarantee

Kafka guarantees ordering within a partition. Since topics are partitioned by `city_id`, all events for a city arrive in LSN order to a single consumer thread — no cross-partition ordering problems.

---

## 7. Comparison: Current Snapshot Approach vs CDC

| Dimension | Current (Monthly Snapshot) | CDC (Production) |
|---|---|---|
| **Latency** | ~30 days (next snapshot) | Seconds to minutes |
| **History granularity** | One point-in-time per month | Every individual change |
| **Data volume per run** | Full reload (25k–100k rows) | Delta only (typically <1% of table) |
| **Infrastructure** | Python + DuckDB (local) | Kafka + Debezium + Flink + DuckDB |
| **Operational complexity** | Low | High |
| **Source requirement** | Static file | PostgreSQL WAL access |
| **Price change tracking** | Only visible if scraped in different months | Captured within seconds |
| **Delete tracking** | Inferred from absence in next snapshot | Explicit DELETE event |
| **Suitable for** | Analytics on monthly cadence data | Real-time dashboards, fraud detection, dynamic pricing |

---

## 8. Migration Path from Snapshots to CDC

If Inside Airbnb ever provided database-level access, the migration would proceed in four phases:

**Phase 1 — Dual-write (weeks 1–2)**  
Run snapshot pipeline and CDC pipeline in parallel. Reconcile row counts and field-level checksums daily. Trust snapshot; use CDC as shadow.

**Phase 2 — SCD-2 backfill (weeks 3–4)**  
Replay all historical monthly snapshots through the SCD-2 loader to populate `valid_from` / `valid_to` for the known history. Each monthly snapshot becomes a "bulk CDC event" with `op = r`.

**Phase 3 — Cut over (week 5)**  
Disable snapshot pipeline. CDC pipeline becomes the single write path. Confirm watermark is advancing and DLQ is empty.

**Phase 4 — Decommission (week 6)**  
Remove snapshot ingestion code. Archive raw CSV files. Update documentation.

---

*This document describes a target architecture. The current implementation uses monthly snapshot ingestion, which is the correct design for the Inside Airbnb public dataset. CDC would be adopted if access to the operational PostgreSQL database were available.*
