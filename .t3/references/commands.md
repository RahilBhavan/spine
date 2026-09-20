# Commands and evidence

Run from the repository root. Use the repository virtual environment so Python and NumPy are consistent.

## Setup and local viewing

- `uv venv .venv && uv pip install numpy pytest` — derived from `pyproject.toml`, `README.md`, and CI dependencies.
- `.venv/bin/python -m http.server 8000` — serve the repository root, then open `/site/`; required because the site fetches `../data/*.json`.

## Verification

- `.venv/bin/python -m pytest -q tests` — exact CI test command, with the virtual-environment interpreter.
- `.venv/bin/python -m spine.api` — shared-helper self-check plus a live Morpho probe.
- `.venv/bin/python -m spine.summarize` — rebuild compact dashboard data and run its invariants.
- `.venv/bin/python -m spine.writeup_tables` — regenerate/inspect all numeric writeup tables.
- `.venv/bin/python -m spine.render_writeup` — regenerate `site/writeup.html` and verify required output markers.

## Live data pipeline

In dependency order:

1. `.venv/bin/python -m spine.fetch_positions`
2. `.venv/bin/python -m spine.fetch_liquidations`
3. `.venv/bin/python -m spine.tag_coinbase`
4. `.venv/bin/python -m spine.fetch_depth`
5. `.venv/bin/python -m spine.summarize`
6. `.venv/bin/python -m spine.history`
7. `.venv/bin/python -m spine.render_writeup`

## Historical/model pipeline

- `.venv/bin/python -m spine.fetch_prices`
- `.venv/bin/python -m spine.fetch_oracle --max-seconds 200` — rerun until it reports complete.
- `.venv/bin/python -m spine.calibrate Feb2026 --max-seconds 200` — repeat for individual windows; run without a window to assemble.
- `.venv/bin/python -m spine.rebuild_book cbBTC 2026-02-03 2026-06-01 2025-10-09 --max-seconds 200`
- `.venv/bin/python -m spine.backtest calib --max-seconds 200`
- `.venv/bin/python -m spine.backtest grid --market cbBTC --max-seconds 200` — rerun until complete.
- `.venv/bin/python -m spine.backtest sens --market cbBTC --max-seconds 200` — rerun until complete.
- `.venv/bin/python -m spine.caps`

Commands are taken from module docstrings, `README.md`, workflows, and `CONTRIBUTING.md`. Networked commands depend on public endpoints and can be slow or rate-limited.

