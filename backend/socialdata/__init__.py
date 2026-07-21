"""Swappable social-sentiment adapters, same pattern as marketdata/newsdata.

Select with CRPT_SOCIAL:
  stocktwits (default) — free, keyless, cashtag-native per-symbol streams
  (reddit and X adapters can be added later: Reddit needs registered OAuth
   app credentials; X requires a paid API tier. Neither is scraped — terms.)
"""
import os


def get_adapter():
    name = os.environ.get("CRPT_SOCIAL", "stocktwits")
    if name == "stocktwits":
        from .stocktwits import StocktwitsAdapter
        return StocktwitsAdapter()
    raise ValueError(f"Unknown social adapter: {name!r}")
