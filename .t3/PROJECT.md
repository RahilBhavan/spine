# Spine

Spine is a public-data risk analysis of Coinbase's on-chain lending book in Morpho Blue markets on Base. It has three products:

1. An hourly static dashboard of the current book and observed liquidity.
2. A calibrated liquidation-queue backtest over historical crash paths.
3. A reproducible haircut recommendation whose numeric tables come from generated data.

The repository is deliberately a Python-script pipeline plus a static HTML/CSS/JavaScript site. There is no application server or database. Public Morpho, Base, Coinbase, Kraken, and Chainlink interfaces are the external trust boundary. Generated files under `data/` are the interface between acquisition/modeling code and presentation code.

Primary specifications are `PLAN.md`, `WRITEUP.md`, and `ROADMAP.md`. Coding conventions are authoritative in `CONTRIBUTING.md`.

Unknown: the intended owner and review process after the research project is published.

