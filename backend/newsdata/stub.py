"""Stub provider: wiring proof with zero fabrication.

Returns no items, so the feed renders its honest empty state. Data-honesty
rule: a stub must never invent headlines — "no data" beats plausible fakes.
"""
from .base import NewsAdapter


class StubAdapter(NewsAdapter):
    name = "stub"
    source_label = "stub (no provider wired — feed intentionally empty)"

    def news(self, tickers, names=None):
        return []
