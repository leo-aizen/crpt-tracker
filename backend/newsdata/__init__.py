"""Swappable news adapters, mirroring the marketdata pattern.

get_adapter() is the ONLY entry point. Select with the CRPT_NEWS env var:
  multi (default) — Yahoo Finance RSS + Google News RSS, merged and deduped
  yahoo_rss       — Yahoo Finance per-ticker RSS only
  google_news     — Google News multi-outlet RSS only
  stub            — returns nothing, renders the honest empty state
A paid/curated provider can drop in later without touching anything else.
"""
import os


def get_adapter():
    name = os.environ.get("CRPT_NEWS", "multi")
    if name == "multi":
        from .multi import MultiAdapter
        return MultiAdapter()
    if name == "yahoo_rss":
        from .yahoo_rss import YahooRssAdapter
        return YahooRssAdapter()
    if name == "google_news":
        from .google_news import GoogleNewsAdapter
        return GoogleNewsAdapter()
    if name == "stub":
        from .stub import StubAdapter
        return StubAdapter()
    raise ValueError(f"Unknown news adapter: {name!r}")
