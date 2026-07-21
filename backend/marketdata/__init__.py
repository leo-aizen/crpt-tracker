"""Swappable market-data adapters.

get_adapter() is the ONLY entry point the rest of the app may use — no
provider names or symbol quirks leak outside this package. Select the
provider with the CRPT_MARKETDATA env var (default: yahoo placeholder;
"bloomberg" reserved for the future DAPI adapter).
"""
import os


def get_adapter():
    name = os.environ.get("CRPT_MARKETDATA", "yahoo")
    if name == "yahoo":
        from .yahoo import YahooAdapter
        return YahooAdapter()
    raise ValueError(f"Unknown market-data adapter: {name!r}")
