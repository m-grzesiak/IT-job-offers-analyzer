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

Python package `it_job_offers_analyzer/` with three modules:

- **`scrapper.py`** — Scrapes justjoin.it REST API (`/api/candidate-api/offers`). Handles pagination, optional detail fetching (full HTML descriptions via per-slug endpoint). Uses only stdlib (`urllib`, `json`). Output: list of offer dicts.

- **`analyzer.py`** — Statistical salary analysis. Normalizes salaries to monthly PLN using magnitude heuristics (the API's unit field is unreliable). IQR-based outlier detection. Percentile distribution. B2B benefits keyword search against HTML offer bodies. Uses only stdlib (`statistics`, `re`).

- **`cli.py`** — Interactive REPL built with `rich` + `prompt_toolkit`. Slash-command interface (`/analyze`, `/top`, `/benefits`, `/show`, etc.) with context-aware tab completion. Commands auto-scrape when needed and cache results in session — no separate scrape step required. CLI history is persisted to `~/.itjobs-history`.

Entry point (defined in `pyproject.toml`):
- `itjobs` → `it_job_offers_analyzer.cli:main`

## Key Design Decisions

- Salary normalization (`analyzer.normalize_monthly`) uses value magnitude to detect hourly/daily/monthly/yearly rates instead of trusting the API's unit field.
- The scraper uses raw `urllib` (no `requests` dependency) with browser-like headers.
- `cli.py` re-implements the scraping loop from `scrapper.scrape()` inline to hook into `rich.Progress` — changes to pagination/fetching logic may need updating in both `scrapper.scrape()` and `cli._scrape()`.
- Detail fetching (per-offer HTTP requests) is slow and required for benefits analysis. In the CLI, `/benefits` triggers this automatically. In the standalone scraper, use `--fetch-details`.
- `/top` accepts a `>P{n}` argument to set the percentile threshold (e.g. `/top b2b >P75`); defaults to P90.
- The session cache (`state` dict in `cli.py`) is checked before each command — re-scraping only happens when filters change or details are newly needed.

## Building & Publishing

```bash
pip install build twine
python -m build              # produces dist/*.tar.gz and dist/*.whl
twine upload dist/*          # publish to PyPI (requires ~/.pypirc or token)
```
