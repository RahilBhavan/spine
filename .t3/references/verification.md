# Verification by change type

Always record the exact command, exit status, and meaningful result. Generated-data tests may skip when their input files are absent.

- Shared helpers or fetchers: run the changed module's `__main__` self-check. Confirm imports alone do not access argv or network. Run the full pytest suite.
- Position/liquidation schemas: run the relevant fetcher, `spine.summarize`, and `tests/test_data.py` through the full suite.
- Calibration: run the target window to completion, assemble calibration, then run `spine.backtest calib`. Compare fitted and observed ratios described in `PLAN.md`/`ROADMAP.md`.
- Backtest engine: run `.venv/bin/python -m pytest -q tests/test_backtest.py`, then the full suite. For behavior-preserving refactors, compare `backtest.json` rows before and after to the tolerance required by `ROADMAP.md`.
- Summary/dashboard contract: run `spine.summarize`, full pytest, serve the site, and manually inspect live/backtest tabs at desktop and phone width.
- Writeup numbers: run `spine.writeup_tables`; do not hand-type changed numeric tables. Regenerate with `spine.render_writeup`.
- Workflow changes: validate YAML, run each changed shell command locally where safe, and observe the scheduled-run acceptance criteria in `ROADMAP.md` when applicable.

Do not claim live refresh or Pages deployment success from local tests alone.

