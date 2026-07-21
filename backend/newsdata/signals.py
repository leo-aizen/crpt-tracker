"""Heuristic signal tagging for news items — the criteria the desk actually
scans for on a crypto-equity ETF. Deterministic keyword rules over the
headline + summary text; no external calls, no fabrication (a tag is a
routing hint, honestly labeled "auto-tagged" in the UI, never a claim).

Adapter-agnostic: applied to whatever items the active news adapter returns.
First matching rule in priority order wins; no match -> "general".

An AI classifier (Claude API) can replace this later behind the same
function signature; keep the signal keys stable if it does.
"""
import re

# (key, label, priority-ordered regex). Order matters: a Metaplanet
# bitcoin-purchase story should tag btc_treasury even if it also says "Q2".
SIGNAL_RULES = [
    ("btc_treasury", "BTC treasury", re.compile(
        r"(bitcoin|btc)\b[^.]{0,80}\b(purchase[sd]?|buy[s]?|bought|add(s|ed)?|acqui|"
        r"holding[s]?|treasur|stack[s]?|accumulat)|\btreasur\w*[^.]{0,40}\b(bitcoin|btc)\b",
        re.I)),
    ("regulatory", "Regulatory", re.compile(
        r"\bsec\b|\bcftc\b|regulat|stablecoin\s+(rule|act|law)|genius act|congress|"
        r"senate\b|lawsuit|subpoena|probe\b|settle(s|d|ment)|fine[sd]\b|court\b|"
        r"etf approv|delist", re.I)),
    ("analyst", "Analyst action", re.compile(
        r"upgrade[sd]?|downgrade[sd]?|price target|initiat\w+ coverage|reiterat|"
        r"\brating\b|overweight|underweight|outperform|underperform|analyst[s]?\b", re.I)),
    ("deal", "Deals & capital", re.compile(
        r"acquir\w+|merger|takeover|buyout|\bm&a\b|\bstake\b|\bipo\b|spin-?off|"
        r"offering|convertible|raise[sd]?\s+\$|\bfundrais|private placement|buyback", re.I)),
    ("earnings", "Earnings", re.compile(
        r"earnings|\brevenue\b|profit|guidance|\bq[1-4]\b|quarterly|results\b|"
        r"\beps\b|outlook|forecast", re.I)),
    ("leadership", "Leadership", re.compile(
        r"\bceo\b|\bcfo\b|\bcio\b|\bcoo\b|chief (executive|financial|investment)|"
        r"appoint|resign|steps? down|\bnames\b[^.]{0,40}\b(chief|president|head)\b|"
        r"founder\b[^.]{0,30}\b(exit|leave|depart)", re.I)),
    ("mining", "Mining & infra", re.compile(
        r"hash ?rate|exahash|\bmining\b|\bminer[s]?\b|\brig[s]?\b|data ?center|"
        r"\bhpc\b|\bai compute\b|power (deal|agreement|purchase)|megawatt|energy cost", re.I)),
]

GENERAL = ("general", "General")

SIGNALS = [(k, lbl) for k, lbl, _ in SIGNAL_RULES] + [GENERAL]


def classify(headline, summary):
    text = f"{headline or ''} {summary or ''}"
    for key, _label, rx in SIGNAL_RULES:
        if rx.search(text):
            return key
    return GENERAL[0]
