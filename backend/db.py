"""SQLite connection + schema for the CRPT tracker.

Single-file DB, rebuilt from data/crpt_data.json by loader.py on every load.
The JSON file is the source of truth; the DB is just its queryable form.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "crpt.db"

SCHEMA = """
-- Load provenance + validation results. One row per key.
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Fund facts (one row). Every fact carries the file's as-of date via meta.
CREATE TABLE fund (
    ticker                  TEXT PRIMARY KEY,
    etf_name                TEXT NOT NULL,
    intraday_nav_ticker     TEXT,
    issuer                  TEXT,
    subadvisor              TEXT,
    servicing_agent         TEXT,
    cusip                   TEXT,
    isin                    TEXT,
    exchange                TEXT,
    fund_type               TEXT,
    legal_type              TEXT,
    inception_date          TEXT,
    inception_price         REAL,
    inception_nav           REAL,
    fiscal_year_end         TEXT,
    expense_ratio_pct       REAL,
    expense_ratio_as_of     TEXT,
    management_style        TEXT,
    diversification         TEXT,
    mandate_summary         TEXT,
    yield_pct               REAL
);

-- The 19 securities + cash line, exactly as in the official file.
CREATE TABLE holdings (
    ticker            TEXT PRIMARY KEY,     -- '$USD' for the cash line
    name              TEXT NOT NULL,
    cusip             TEXT,
    classification    TEXT,                 -- fund's own tag, displayed as-is (incl. ASST's odd one)
    shares            REAL,
    market_value_usd  REAL,
    weight_pct        REAL,
    priceable         INTEGER NOT NULL,     -- 0 = NEVER send to the market-data adapter
    btc_etf           INTEGER NOT NULL DEFAULT 0,
    miner             INTEGER NOT NULL DEFAULT 0,
    note              TEXT,
    as_of             TEXT NOT NULL
);

-- Exposure buckets (the structural story: BTC ETFs / treasury cos / financials / miners).
CREATE TABLE exposure_buckets (
    bucket_key        TEXT PRIMARY KEY,
    label             TEXT NOT NULL,
    approx_weight_pct REAL
);
CREATE TABLE exposure_bucket_members (
    bucket_key TEXT NOT NULL REFERENCES exposure_buckets(bucket_key),
    ticker     TEXT NOT NULL REFERENCES holdings(ticker),
    PRIMARY KEY (bucket_key, ticker)
);

-- Benchmarks for the performance chart (IBIT / BITQ / SPY).
CREATE TABLE benchmarks (
    rank   INTEGER PRIMARY KEY,   -- 1 = primary
    ticker TEXT NOT NULL,
    label  TEXT NOT NULL
);

-- Historical reference blocks kept verbatim as JSON, each with its as-of date.
-- These are labeled HISTORICAL in the UI and are never rendered as current.
CREATE TABLE reference_snapshots (
    name    TEXT PRIMARY KEY,   -- 'current_fund_data', 'performance_snapshot', ...
    as_of   TEXT,
    payload TEXT NOT NULL       -- raw JSON block from the file
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rebuild_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        "DROP TABLE IF EXISTS exposure_bucket_members;"
        "DROP TABLE IF EXISTS exposure_buckets;"
        "DROP TABLE IF EXISTS benchmarks;"
        "DROP TABLE IF EXISTS reference_snapshots;"
        "DROP TABLE IF EXISTS holdings;"
        "DROP TABLE IF EXISTS fund;"
        "DROP TABLE IF EXISTS meta;"
    )
    conn.executescript(SCHEMA)
