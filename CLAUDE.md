# CRPT Tracker

## What this is
An internal SkyBridge tool for monitoring the CRPT ETF (First Trust SkyBridge Crypto Industry and Digital Economy ETF), which SkyBridge Capital II sub-advises. It gives the team a fast, repeatable way to check CRPT's price and performance, see its holdings and exposures, and follow news on those holdings. Built by Leo Bernstein (summer analyst).

## Who uses it
SkyBridge investment/research staff. Internal monitoring tool, not client-facing, not a trading system. Finance-literate, non-technical users.

## Look and feel: match the SURF tracker
This app should feel like a sibling of SkyBridge's existing "Surf Tracker" so the two read as one suite:
- Dark theme, mobile-first, PWA feel.
- Pinned toolbar under a title bar; content scrolls beneath it.
- Card-based layout; dense, legible, dates on everything; no decorative fluff.
- A `styles.css` from the SURF tracker may be provided to reuse as the visual baseline. Match its variables (colors, spacing, type). If reused, keep it as a separate stylesheet, do not claim SURF's app code as this app's.
Build this app's own code fresh (do not fork SURF's backend). Style parity, not code copy.

## SOURCE OF TRUTH: crpt_data.json
`crpt_data.json` is authoritative and vetted. Read it before building anything. Rules:
1. It is a 2026-07-17 snapshot. Label holdings and fund facts "as of" their dates in the UI. CRPT is actively managed; weights move daily.
2. When any external source (Morningstar, StockAnalysis, Yahoo, an API) disagrees with this file on holdings/weights/net assets, THIS FILE WINS. The `source_conflicts` block documents why they differ (all date/vendor artifacts).
3. Never hardcode a live price. Prices and returns come from a runtime market-data adapter. The `current_fund_data` and `performance_snapshot` numbers in the file are HISTORICAL reference only, never render them as "current".
4. Never fabricate a value. Missing data shows "no data", never a guess.

## Critical build gotchas (these are in the data; honor them)
- **Untickered top holding.** Third-party sites list "Ft Sky Crypt Cym 1002063" (~20%) with no ticker. It is a SkyBridge Cayman feeder, NOT priceable via any market API, and is absent from the official file. If it ever appears in holdings, mark `priceable:false`, never send it to the price adapter.
- **Metaplanet (3350.JP) is Tokyo-listed.** Non-US ticker. Yahoo uses `3350.T`, Bloomberg `3350 JP Equity`. Many free APIs don't cover it. The adapter must handle non-US symbols explicitly, don't assume every holding resolves on a US-only endpoint.
- **Cash line ($USD).** `priceable:false`. Exclude from price fetches and from any "per-holding return" logic.
- **Strive (ASST) classification** reads "Health Care Equipment & Supplies" in the fund's own file. Odd for a crypto-treasury name but it's the fund's tag. Display as-is; don't silently recategorize.

## Views to build
1. **Overview** — fund facts from the file (name, ticker CRPT, issuer, sub-advisor SkyBridge, inception, expense ratio, NAV, net assets) with visible as-of dates. Live price + a performance chart of CRPT vs. benchmark(s) over selectable windows (1W/1M/3M/YTD/1Y), computed from the adapter's price series (not from the static snapshot numbers).
2. **Holdings** — the 19 securities + cash from the file, with weight, classification, market value. Surface the `exposure_buckets` (direct BTC ETFs ~20%, bitcoin-treasury names ~41%, crypto financials ~31%, miners ~8%) as a grouping view, that's the real story of what CRPT is.
3. **News** — a card feed over the holding tickers (SURF pattern). Start with a swappable news adapter + stub; wire a real provider later.

## Benchmarks
First Trust officially benchmarks CRPT to the S&P 500. For an internal tool that's misleading in isolation (it can't tell you if CRPT is beating its category). Show multiple per `benchmark_config`: a spot-BTC proxy (IBIT), a crypto-equity peer (BITQ), and broad equity (SPY). Let the user separate "is crypto up" from "is CRPT beating peers".

## Tech stack
- Backend: Python + FastAPI. Storage: SQLite. Frontend: React (or plain HTML/JS if reusing SURF's non-React shell, match whatever SURF uses).
- Single swappable **market-data adapter** module for price/chart data: placeholder provider now (e.g. a free delayed API), Bloomberg DAPI later. Never hardcode the source elsewhere.
- Single swappable **news adapter** module, same pattern.
- Runnable locally with minimal setup; document run steps in a README.

## Build order (STOP for review after each step)
Do not generate the whole app at once. Pause after each numbered step for Leo to review:
1. App shell + styling (SURF-matched) + loader that ingests crpt_data.json and validates weights sum to ~100%.
2. Overview view: fund facts with as-of dates (static from file, clearly labeled).
3. Market-data adapter interface + placeholder impl; wire live price + performance chart vs benchmarks. Compute cumulative return from the price series.
4. Holdings view + exposure buckets.
5. News adapter interface + stub + feed UI.

## Judgment notes
- Credibility with Svolos comes from honesty about data limits and correct handling of the messy bits (untickered feeder, Tokyo listing, stale third-party numbers), not from flash.
- The interesting analytical framing this tool can make visible: CRPT is a high-beta (3Y beta ~3.8), high-vol (~75% std dev) crypto-equity basket whose largest structural bet is bitcoin-treasury proxy companies (MSTR/Metaplanet/Strive ~41%) plus direct BTC ETFs (~20%). Surface that, don't bury it.
