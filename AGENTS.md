# Spine project contract

## Purpose

Spine measures liquidation risk in Coinbase-linked Morpho Blue markets on Base. It fetches public market data, reconstructs historical books, calibrates a liquidation model, replays crash paths, and publishes a static dashboard and writeup.

Start with `CODEBASE_GUIDE.md` for the system tour. `PLAN.md` is the original product/model specification; `ROADMAP.md` records later corrections and planned work; `CONTRIBUTING.md` is the coding standard.

## Commands

- Setup: `uv venv .venv && uv pip install numpy pytest`
- Tests: `.venv/bin/python -m pytest -q tests`
- Live summary from existing inputs: `.venv/bin/python -m spine.summarize`
- Serve the static site from the repository root: `.venv/bin/python -m http.server 8000`
- Full data and model commands are listed in `README.md`.

## Working constraints

- Follow `CONTRIBUTING.md`: Python 3.12; standard library except NumPy in `spine/backtest.py`; plain functions and data; no framework, ORM, or CLI library.
- Treat `data/` as generated output. Change its producer, not a generated JSON or CSV file by hand.
- Preserve raw on-chain integers as JSON strings.
- Importing a module must not parse arguments, touch the network, or run its job.
- Long jobs must remain resumable and respect `--max-seconds`.
- Do not add keys, paid data sources, a backend, or production dependencies without explicit approval.
- Preserve unrelated working-tree changes. `ROADMAP.md` may contain user work.

## Verification

At minimum, run the narrowest relevant self-check plus `.venv/bin/python -m pytest -q tests` for model or data-contract changes. Report commands, exit status, and skipped checks.

