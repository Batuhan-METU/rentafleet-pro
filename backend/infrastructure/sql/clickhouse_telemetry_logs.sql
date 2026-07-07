-- =====================================================================
-- RentA-Fleet PRO — ClickHouse OLAP schema
-- Table: telemetry_logs
-- Engine: MergeTree
-- Purpose: high-volume, append-only IoT telemetry from fleet devices.
-- =====================================================================

CREATE TABLE IF NOT EXISTS telemetry_logs
(
    `device_id`   UInt64,                       -- IoT/GPS unit id (numeric => compact, fast to compare)
    `timestamp`   DateTime          CODEC(DoubleDelta, ZSTD(1)),  -- event time (UTC)
    `speed`       Float32           CODEC(Gorilla, ZSTD(1)),      -- km/h
    `fuel_level`  Float32           CODEC(Gorilla, ZSTD(1)),      -- percentage 0-100
    `latitude`    Float64           CODEC(Gorilla, ZSTD(1)),
    `longitude`   Float64           CODEC(Gorilla, ZSTD(1)),
    `event_type`  LowCardinality(String),       -- 'normal' | 'harsh_brake' | 'speed_violation' | 'geofence_out'
    `ingested_at` DateTime DEFAULT now()        -- server-side ingestion time (auditing / lag analysis)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
PRIMARY KEY (device_id, timestamp)
ORDER BY (device_id, timestamp)
TTL timestamp + INTERVAL 13 MONTH          -- retain ~13 months of raw telemetry, then drop
SETTINGS index_granularity = 8192;

-- ---------------------------------------------------------------------
-- Secondary (data-skipping) indexes
-- ---------------------------------------------------------------------
-- event_type is low-cardinality but NOT part of ORDER BY, so a set index
-- lets queries like "show all speed_violation events" skip granules that
-- don't contain the value without a full scan.
ALTER TABLE telemetry_logs
    ADD INDEX IF NOT EXISTS idx_event_type event_type TYPE set(0) GRANULARITY 4;
