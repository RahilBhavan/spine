# Constraints and non-goals

- Python 3.12. Fetchers use only the standard library; NumPy is isolated to the backtest.
- Static site, no build step, no backend, no database. Plotly from jsDelivr is the only browser dependency.
- Public, unauthenticated endpoints only. Never add or commit credentials.
- `data/` is generated. Raw integers that can exceed JavaScript precision remain strings.
- Long jobs checkpoint under ignored `data/cache/`, stop successfully on their time budget, and resume on rerun.
- Generated writeup numbers must trace to scripts and JSON artifacts.
- Current depth is a proxy for unavailable paid historical depth; stress multipliers and sensitivity analysis expose that limitation.
- Tier C (Coinbase as a backstop liquidator) is a hypothetical scenario, not an observed fact.
- The model is deepest for cbBTC and WETH; dashboard coverage is broader than backtest evidence.
- Avoid frameworks, classes, ORMs, CLI packages, and duplicated helpers unless the project contract is deliberately revised.
- Do not rewrite Git history, deploy, or change production/publication state without explicit approval.

