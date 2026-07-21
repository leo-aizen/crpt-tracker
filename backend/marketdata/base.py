"""Adapter contract. Every provider implements exactly this.

Symbols passed in are OUR canonical tickers (as stored in crpt_data.json,
e.g. "3350.JP") — each adapter owns its own mapping to provider symbols.
Adapters return raw prices only; return math happens in the API layer so it
is identical across providers.
"""


class MarketDataAdapter:
    name: str = "base"
    # Shown in the UI beside every figure this adapter produced.
    source_label: str = "unconfigured source"

    def quote(self, symbols: list[str]) -> dict:
        """{symbol: {"price": float, "prev_close": float|None,
                     "currency": str, "market_time_utc": str}}
        Symbols that fail are simply absent from the result — callers render
        "no data" for them, never a guess."""
        raise NotImplementedError

    def history(self, symbol: str, rng: str) -> dict:
        """rng is one of 1W / 1M / 3M / YTD / 1Y.
        Returns {"timestamps": [unix...], "closes": [float...], "currency": str}
        with None-close bars already dropped. Raises on failure."""
        raise NotImplementedError
