"""Ingest data/crpt_data.json (the source of truth) into SQLite.

Run:  python3 loader.py

Validates before loading; FAILS LOUDLY (non-zero exit, nothing written)
if the file doesn't look like the vetted snapshot:
  - holding weights must sum to ~100% (tolerance +/- 0.5 pct-points)
  - security count must match the file's own count_securities
  - any line with no real ticker is forced priceable=0 (the "Ft Sky Crypt
    Cym" Cayman feeder rule: never send untickered lines to a price API)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import db

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "crpt_data.json"

WEIGHT_TOLERANCE_PP = 0.5  # percentage points around 100


def fail(msg: str) -> None:
    print(f"\n*** LOAD FAILED — {msg}", file=sys.stderr)
    print("*** Nothing was written to the database.", file=sys.stderr)
    sys.exit(1)


def validate(data: dict) -> dict:
    """Return computed validation facts, or exit loudly."""
    try:
        lines = data["holdings"]["line_items"]
    except KeyError:
        fail("crpt_data.json has no holdings.line_items block")

    weight_sum = round(sum(li.get("weight_pct") or 0 for li in lines), 2)
    if abs(weight_sum - 100.0) > WEIGHT_TOLERANCE_PP:
        fail(
            f"holding weights sum to {weight_sum}%, outside 100% ± {WEIGHT_TOLERANCE_PP}pp. "
            "The snapshot looks incomplete or corrupted — refusing to load it."
        )

    securities = [li for li in lines if li.get("classification") != "Cash"]
    declared = data["holdings"].get("count_securities")
    if declared is not None and len(securities) != declared:
        fail(
            f"file declares {declared} securities but line_items contains "
            f"{len(securities)} non-cash lines"
        )

    missing_weight = [li["name"] for li in lines if li.get("weight_pct") is None]
    if missing_weight:
        fail(f"line items with no weight_pct: {missing_weight}")

    return {"weight_sum": weight_sum, "security_count": len(securities), "line_count": len(lines)}


def normalize_line(li: dict) -> dict:
    """Apply the data-honesty rules that guard the price adapter."""
    li = dict(li)
    ticker = li.get("ticker")
    # Cayman-feeder / untickered rule: no ticker (or cash) => never priceable.
    if not ticker or ticker == "$USD":
        li["priceable"] = False
    # Defense in depth: the known feeder name is unpriceable even if a future
    # file version gives it a placeholder ticker.
    if "ft sky crypt" in (li.get("name") or "").lower():
        li["priceable"] = False
        li["note"] = (li.get("note") or "") + " [SkyBridge Cayman feeder — not priceable via market APIs]"
    return li


def load() -> None:
    if not DATA_PATH.exists():
        fail(f"data file not found at {DATA_PATH}")
    with open(DATA_PATH) as f:
        data = json.load(f)

    checks = validate(data)

    conn = db.connect()
    db.rebuild_schema(conn)

    fund = data["fund"]
    conn.execute(
        """INSERT INTO fund VALUES (:ticker,:etf_name,:intraday_nav_ticker,:issuer,
            :subadvisor,:servicing_agent,:cusip,:isin,:exchange,:fund_type,:legal_type,
            :inception_date,:inception_price,:inception_nav,:fiscal_year_end,
            :expense_ratio_pct,:expense_ratio_as_of,:management_style,:diversification,
            :mandate_summary,:yield_pct)""",
        {
            "ticker": fund["ticker"],
            "etf_name": fund["etf_name"],
            "intraday_nav_ticker": fund.get("intraday_nav_ticker"),
            "issuer": fund.get("issuer"),
            "subadvisor": fund.get("portfolio_manager_subadvisor"),
            "servicing_agent": fund.get("investor_servicing_agent"),
            "cusip": fund.get("cusip"),
            "isin": fund.get("isin"),
            "exchange": fund.get("exchange"),
            "fund_type": fund.get("fund_type"),
            "legal_type": fund.get("legal_type"),
            "inception_date": fund.get("inception_date"),
            "inception_price": fund.get("inception_price"),
            "inception_nav": fund.get("inception_nav"),
            "fiscal_year_end": fund.get("fiscal_year_end"),
            "expense_ratio_pct": fund.get("total_expense_ratio_pct"),
            "expense_ratio_as_of": fund.get("expense_ratio_as_of"),
            "management_style": fund.get("management_style"),
            "diversification": fund.get("diversification"),
            "mandate_summary": fund.get("mandate_summary"),
            "yield_pct": fund.get("yield_pct"),
        },
    )

    holdings_as_of = data["holdings"]["as_of"]
    for li in data["holdings"]["line_items"]:
        li = normalize_line(li)
        conn.execute(
            """INSERT INTO holdings (ticker,name,cusip,classification,shares,
               market_value_usd,weight_pct,priceable,btc_etf,miner,note,as_of)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                li.get("ticker"),
                li["name"],
                li.get("cusip"),
                li.get("classification"),
                li.get("shares"),
                li.get("market_value_usd"),
                li.get("weight_pct"),
                1 if li.get("priceable") else 0,
                1 if li.get("btc_etf") else 0,
                1 if li.get("miner") else 0,
                li.get("note"),
                holdings_as_of,
            ),
        )

    for key, bucket in data["holdings"]["exposure_buckets"].items():
        conn.execute(
            "INSERT INTO exposure_buckets VALUES (?,?,?)",
            (key, bucket["label"], bucket.get("approx_weight_pct")),
        )
        for t in bucket["tickers"]:
            conn.execute("INSERT INTO exposure_bucket_members VALUES (?,?)", (key, t))

    for rank, slot in enumerate(["primary", "secondary", "tertiary"], start=1):
        b = data["benchmark_config"].get(slot)
        if b:
            conn.execute("INSERT INTO benchmarks VALUES (?,?,?)", (rank, b["ticker"], b["label"]))

    # Historical reference blocks — stored verbatim, labeled HISTORICAL in the UI.
    for name in (
        "current_fund_data",
        "performance_snapshot",
        "fund_characteristics",
        "top_country_exposure",
        "top_industry_exposure",
        "premium_discount_history",
        "source_conflicts",
    ):
        block = data.get(name)
        if block is not None:
            conn.execute(
                "INSERT INTO reference_snapshots VALUES (?,?,?)",
                (name, block.get("as_of") if isinstance(block, dict) else None, json.dumps(block)),
            )

    meta = {
        "holdings_as_of": data["_metadata"]["holdings_as_of"],
        "fund_facts_as_of": data["_metadata"]["fund_facts_as_of"],
        "source_of_truth": data["_metadata"]["source_of_truth"],
        "loaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weight_sum_pct": str(checks["weight_sum"]),
        "security_count": str(checks["security_count"]),
        "line_count": str(checks["line_count"]),
    }
    conn.executemany("INSERT INTO meta VALUES (?,?)", meta.items())

    conn.commit()
    conn.close()

    print("Loaded crpt_data.json into", db.DB_PATH)
    print(f"  holdings as of : {meta['holdings_as_of']}")
    print(f"  line items     : {checks['line_count']} ({checks['security_count']} securities + cash)")
    print(f"  weight sum     : {checks['weight_sum']}%  (OK, within ±{WEIGHT_TOLERANCE_PP}pp of 100)")
    unpriceable = [
        li.get("ticker") or li["name"]
        for li in map(normalize_line, data["holdings"]["line_items"])
        if not li.get("priceable")
    ]
    print(f"  never priced   : {', '.join(unpriceable)}  (excluded from the market-data adapter)")


if __name__ == "__main__":
    load()
