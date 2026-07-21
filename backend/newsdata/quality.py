"""Feed hygiene: source ALLOWLIST + deterministic clickbait filtering.

Only outlets on the firm's approved list appear in the feed, full stop —
anything unrecognized is dropped, not judged case-by-case. On top of that,
clickbait patterns are filtered even from approved outlets (a Forbes
contributor listicle is still a listicle). Rules are transparent and listed
here, not learned; the API reports how many items were removed.
"""
import re

# Approved sources. Keys are lowercase substrings matched against the raw
# source string; values are the canonical display name. Anything that
# matches nothing is dropped.
ALLOWED = [
    ("yahoo", "Yahoo Finance"),
    ("forbes", "Forbes"),
    ("morningstar", "Morningstar"),
    ("cnbc", "CNBC"),          # before cnn: "cnbc" contains no "cnn" but order is cheap safety
    ("cnn", "CNN"),
    ("bloomberg", "Bloomberg"),
    ("sec edgar", "SEC EDGAR"),
    ("stock trader", "Stock Traders Daily"),
    ("investing.com", "Investing.com"),
    ("tradingview", "TradingView"),
    ("wall street journal", "WSJ"),
    ("wsj", "WSJ"),
    ("coindesk", "CoinDesk"),  # the one crypto trade outlet, most-cited institutionally
]


def canonical_source(raw):
    """Canonical name if the source is approved, else None."""
    low = (raw or "").lower()
    for key, name in ALLOWED:
        if key in low:
            return name
    return None


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


def clean(items):
    """Allowlist sources (rewriting to canonical names), drop clickbait.
    Returns (kept, dropped_count)."""
    kept = []
    for item in items:
        name = canonical_source(item.get("source"))
        if name is None:
            continue
        headline = item.get("headline") or ""
        if any(p.search(headline) for p in CLICKBAIT):
            continue
        item = {**item, "source": name}
        kept.append(item)
    return kept, len(items) - len(kept)
