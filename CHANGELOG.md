# Changelog

## v1.1.0 (2026-09-23)

- Refresh job publishes generated data to an orphan `data` branch, so `main` gets only human commits.
- Alert and gauge share one boundary: a market at exactly 10% distance to capacity is red and opens the alert; zero capacity reads as distance 0.0.
- `summarize` fails before writing anything when positions files are missing.
- Independence disclaimer on the dashboard, writeup and README, and a note on who funds the loans.
- Link previews, favicon and social card; staleness notice when data is over 12 hours old; charts draw on scroll; accessibility fixes; weekly link check.
