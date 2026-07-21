"""Feed hygiene: deterministic clickbait and content-farm filtering.

A monitoring tool for a registered firm cannot surface "Top Midday Gainers"
or "3 Stocks That Could Make You a Millionaire". Rules are transparent and
listed here, not learned — every drop is explainable. The API reports how
many items were removed so the UI can say so instead of hiding it.
"""
import re

# Headline patterns that mark listicle/clickbait content, case-insensitive.
CLICKBAIT = [re.compile(p, re.I) for p in (
    r"^\d+\s+\w*\s*(stocks?|reasons?|things|ways|etfs?)\b",
    r"stocks? to (buy|watch|sell|own)\b",
    r"\btop\s+(\d+\s+)?(gainers|losers|movers|stocks|picks)\b",
    r"\b(midday|premarket|after.?hours) (gainers|losers|movers)\b",
    r"should you (buy|sell|invest)",
    r"here'?s (why|what|how)",
    r"you won'?t believe",
    r"price prediction|prediction:",
    r"if you('d| had)? invested",
    r"motley fool",
    r"\bbest\b.{0,30}\b(stocks?|etfs?|cryptos?)\b",
    r"reasons? to (buy|sell)",
    r"is it too late to (buy|sell)",
    r"trending (tickers|stocks)",
    r"\bhot stocks\b",
    r"could make you (rich|a millionaire)|millionaire.?maker",
    r"passive income",
    r"\bwhich is (the )?better (buy|stock)\b",
)]

# Content farms whose output is algorithmic or listicle-first. Conservative
# list — established newsrooms stay even when a headline is punchy.
JUNK_SOURCES = {
    "Insider Monkey",
    "StocksToTrade",
    "simplywall.st",
    "Simply Wall St.",
    "24/7 Wall St.",
}


def is_garbage(item) -> bool:
    if (item.get("source") or "") in JUNK_SOURCES:
        return True
    headline = item.get("headline") or ""
    return any(p.search(headline) for p in CLICKBAIT)


def clean(items):
    """Returns (kept, dropped_count)."""
    kept = [i for i in items if not is_garbage(i)]
    return kept, len(items) - len(kept)
