# Outreach drafts (ROADMAP Phase F4)

Drafts only; nothing here has been posted. Numbers are from WRITEUP.md as of 2026-09-19 and must be re-checked
against `spine/writeup_tables.py` output before posting. The Dune mirror of `summary.json` is not drafted: it
needs a Dune account and queries against Dune's Morpho tables that cannot be checked from this repo.

## 1. Morpho governance forum post

**Title:** Liquidation-capacity replay of the Coinbase cbBTC/USDC market on Base: what binds is liquidator capital, not the LLTV

Morpho runs Dune dashboards on the Coinbase markets, so most of you know the shape of the book: about $1.4B of
USDC borrowed against $2.9B of cbBTC at an 86% LLTV, 39,000 positions, almost all of them Coinbase Smart
Wallets. It has cleared $256M of liquidations across three real stress weeks with zero bad debt.

We built a public replay of that book through seven historical crash paths (March 2020, May 2021, FTX, Aug
2024, Oct 2025, Feb 2026, Jun 2026) with liquidators and borrowers behaving the way the lived events show they
behave. Everything is public data and open code: https://github.com/RahilBhavan/spine, dashboard at
https://rahilbhavan.github.io/spine/, refreshed hourly.

What the replay says:

- Bots are not the bottleneck. Median latency from the oracle update to the liquidation is 0-4 seconds; 80-94%
  of lived liquidations repaid the whole debt.
- Borrowers cure most of the at-risk debt when they get warning. On the Feb 2026 book $515M crossed 86% at the
  trough and $151M was liquidated. The lived events gave the median liquidated position 2-48 hours of warning
  between 80% and 86%. March 2020 would have given it 25 minutes.
- On a March 2020 path at today's terms the realized loss is small ($9.2M, 0.6% of supply) but $158M (10% of
  supply) sits underwater and unserved at the trough. Holding the low for one day before the same bounce turns
  the realized figure into $38M.
- The LLTV barely moves the second number (77% LLTV: 8.4% exposed). Liquidator capital does: the only
  measurement of it is the $97M repaid on Feb 5 2026, a day when it did not bind. Tripling it takes trough
  exposure to 6.2%; a backstop liquidator that can redeem cbBTC and sell on Coinbase's book takes it to 0.8%.

What we would ask the market's owners to consider, in order: a committed backstop liquidator (only Coinbase can
be one; nothing public says it is), a pre-liquidation band at 80-86% so the queue drains during the slide
rather than at the cliff, then 80% LLTV with a 66-70% origination cap. WETH to 77%, where cbETH already sits.
Alts: keep 62.5% but cap each book at what Coinbase's own order book can absorb; cbXRP is already past that
cap.

Full argument, tables and limitations: https://rahilbhavan.github.io/spine/writeup.html. The model is two
parameters fit on three events and the capital figure is a floor, not an estimate; section 7 lists what it does
not capture. Corrections welcome, ideally as issues on the repo.

## 2. Short thread (warning time is the shareable result)

1/ Coinbase's on-chain BTC loans ($1.4B on Morpho, Base) have survived three crashes with zero bad debt. That
record is real. It is also not the test. Here is why, in one table.

2/ Time between a position entering Coinbase's warning zone (80% LTV) and crossing the 86% liquidation line,
for the median position that ended up liquidated, replayed on today's book:

| Crash | Warning time |
|---|---|
| Aug 2024 | 48 h |
| Jun 2026 | 35 h |
| Feb 2026 | 22 h |
| FTX Nov 2022 | 14 h |
| May 2021 | 4 h |
| Oct 2025 | 2 h |
| Mar 2020 | 25 min |

3/ Every crash the book has lived through gave borrowers hours to days to top up. They did: on the Feb 2026 book
$515M crossed the line at the trough and only $151M was liquidated. March 2020 gives 25 minutes. Nobody tops up
in 25 minutes.

4/ In that case only liquidators can save the lenders, and what binds is how much capital they can deploy in a
day. The only measurement is Feb 5 2026: $97M repaid, on a day it did not bind. At that capacity a March 2020
path leaves $158M (10% of supply) underwater at the trough.

5/ Cutting the LLTV does little to that number (77%: still 8.4%). A backstop liquidator does (0.8%). Public
data, open code, hourly dashboard: https://rahilbhavan.github.io/spine/. Writeup with everything it does not
capture: https://rahilbhavan.github.io/spine/writeup.html
