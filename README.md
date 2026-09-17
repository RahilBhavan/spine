# Spine

Live risk dashboard and haircut backtest over Coinbase's on-chain loan book (Morpho Blue on Base).

- **Dashboard**: `site/index.html` (LTV distribution, liquidatable-vs-capacity curve, liquidation history, per market).
- **Writeup**: `WRITEUP.md` (argued haircuts per asset), rendered at `site/writeup.html`.
- **Plan and research**: `PLAN.md`, `research/`. Next steps: `ROADMAP.md`.

## Run

```
python3.12 -m spine.fetch_positions      # all positions, 9 markets (~90s)
python3.12 -m spine.fetch_liquidations   # every liquidation (~60s first run, incremental after)
python3.12 -m spine.tag_coinbase         # Coinbase Smart Wallet tags via Multicall3
python3.12 -m spine.fetch_prices         # Coinbase 5m candles for 7 crash windows (cached)
python3.12 -m spine.fetch_depth          # CEX L2 depth + DEX quoter capacity (~3 min)
python3.12 -m spine.summarize            # -> data/summary.json for the site
python3.12 -m http.server 8000           # then open http://localhost:8000/site/
```

Stress-test pipeline (slow, chunked; every script takes `--max-seconds` and resumes):

```
python3.12 -m spine.fetch_oracle                     # Chainlink AnswerUpdated paths for the lived events
python3.12 -m spine.calibrate Feb2026; ... ; python3.12 -m spine.calibrate   # realized latency/bonus/throughput
python3.12 -m spine.rebuild_book cbBTC 2026-02-03 2026-06-01 2025-10-09      # historical books from events
.venv/bin/python -m spine.backtest calib && .venv/bin/python -m spine.backtest grid --market cbBTC   # etc.
```

Fetchers are stdlib only. `backtest.py` needs numpy (`uv venv .venv && uv pip install numpy`). The GitHub Actions workflow refreshes the live data hourly and deploys to Pages.
