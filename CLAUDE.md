# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool for scraping and analyzing IT job offers from justjoin.it (Polish job board). Distributed as a PyPI package (`itjobs`).

## Setup & Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .   # editable install — includes rich, prompt_toolkit
```

**Interactive CLI** (primary interface):
```bash
itjobs
# Commands auto-fetch data when needed:
#   /analyze Kraków python senior b2b
#   /top b2b >P75        (top companies above P75)
#   /benefits Kraków python senior  (auto-fetches offer details)
```

## Architecture

Python package `it_job_offers_analyzer/` with two core modules and a `cli/` subpackage:

- **`scrapper.py`** — Scrapes justjoin.it REST API (`/api/candidate-api/offers`). Handles pagination, optional detail fetching (full HTML descriptions via per-slug endpoint). Uses only stdlib (`urllib`, `json`). Output: list of offer dicts.

- **`analyzer.py`** — Statistical salary analysis. Normalizes salaries to monthly PLN using magnitude heuristics (the API's unit field is unreliable). IQR-based outlier detection. Percentile distribution. B2B benefits keyword search against HTML offer bodies. Uses only stdlib (`statistics`, `re`).

- **`cli/`** — Interactive REPL built with `rich` + `prompt_toolkit`. Split into focused modules:
  - `app.py` — REPL loop, command dispatch, welcome screen
  - `commands.py` — all `/command` implementations
  - `display.py` — Rich console/theme, `SalaryStats` view-model, table builders, formatting helpers
  - `scraping.py` — CLI scraping orchestration with progress bars (`ensure_data`, `scrape_groups`)
  - `state.py` — `SessionState` cache and `FilterArgs` dataclass
  - `parsing.py` — argument parsing for commands (`parse_args`, `parse_compare_args`)
  - `completer.py` — context-aware tab completion and key bindings
  - `cancel.py` — ESC-key cancellation infrastructure (`CancellableOperation`)
  - `constants.py` — cities, command metadata, banner

Entry point (defined in `pyproject.toml`):
- `itjobs` → `it_job_offers_analyzer.cli:main`

## Key Design Decisions

- Salary normalization (`analyzer.normalize_monthly`) uses value magnitude to detect hourly/daily/monthly/yearly rates instead of trusting the API's unit field.
- The scraper uses raw `urllib` (no `requests` dependency) with browser-like headers.
- `cli/scraping.py` re-implements the scraping loop from `scrapper.scrape()` to hook into `rich.Progress` — changes to pagination/fetching logic may need updating in both `scrapper.scrape()` and `cli/scraping.py`.
- Detail fetching (per-offer HTTP requests) is slow and required for benefits analysis. In the CLI, `/benefits` triggers this automatically. In the standalone scraper, use `--fetch-details`.
- `/top` accepts a `>P{n}` argument to set the percentile threshold (e.g. `/top b2b >P75`); defaults to P90.
- `SessionState` in `cli/state.py` caches offers per session — re-scraping only happens when filters change or details are newly needed.
- `SalaryStats` dataclass in `cli/display.py` extracts the repeated median/midpoint computation used across multiple commands.
- `scrape_groups()` in `cli/scraping.py` is the shared scraping loop for multi-group commands (`/progression`, `/compare`).

## Building & Publishing

```bash
pip install build twine
python -m build              # produces dist/*.tar.gz and dist/*.whl
twine upload dist/*          # publish to PyPI (requires ~/.pypirc or token)
```
