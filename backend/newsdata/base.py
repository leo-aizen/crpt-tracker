"""News adapter contract.

Tickers passed in are OUR canonical tickers (e.g. "3350.JP"); each adapter
owns its own provider-symbol mapping. Items must be real, sourced headlines —
an adapter with nothing to say returns an empty list, never filler.
"""


class NewsAdapter:
    name: str = "base"
    # Shown in the UI beside the feed.
    source_label: str = "no news provider configured"

    def news(self, tickers: list[str], names=None) -> list[dict]:
        """Returns items across all requested tickers, deduped, each:
          {"id": str, "tickers": [str, ...], "headline": str,
           "summary": str|None, "source": str|None, "url": str,
           "published_utc": str|None}
        Tickers that fail are silently skipped (their absence IS the honest
        answer); a total failure raises."""
        raise NotImplementedError
