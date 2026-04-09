# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool for scraping and analyzing IT job offers from justjoin.it (Polish job board). Three-module Python app with no build system or tests.

## Setup & Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # rich, prompt_toolkit
```

**Interactive CLI** (primary interface):
```bash
python cli.py
```

**Standalone scraper** (outputs JSON to stdout or file):
```bash
python scrapper.py --city Warszawa --category python --experience senior
python scrapper.py --city Kraków --output offers.json --fetch-details
```

**Standalone analyzer** (reads scraper JSON output):
```bash
python analyzer.py offers.json --type b2b --exclude-outliers --show-top
python analyzer.py offers.json --benefits   # requires --fetch-details from scraper
```

## Architecture

Three modules, no package structure — all files live in the project root:

- **`scrapper.py`** — Scrapes justjoin.it REST API (`/api/candidate-api/offers`). Handles pagination, optional detail fetching (full HTML descriptions via per-slug endpoint). Uses only stdlib (`urllib`, `json`). Output: list of offer dicts.

- **`analyzer.py`** — Statistical salary analysis. Normalizes salaries to monthly PLN using magnitude heuristics (the API's unit field is unreliable). IQR-based outlier detection. Percentile distribution. B2B benefits keyword search against HTML offer bodies. Uses only stdlib (`statistics`, `re`).

- **`cli.py`** — Interactive REPL built with `rich` + `prompt_toolkit`. Slash-command interface (`/scrape`, `/analyze`, `/top`, `/benefits`, `/show`, etc.) with context-aware tab completion. Maintains in-memory state (`state` dict) of loaded offers. Re-uses `scrapper` and `analyzer` functions directly — duplicates some scraping logic inline for progress bar integration.

## Key Design Decisions

- Salary normalization (`analyzer.normalize_monthly`) uses value magnitude to detect hourly/daily/monthly/yearly rates instead of trusting the API's unit field.
- The scraper uses raw `urllib` (no `requests` dependency) with browser-like headers.
- `cli.py` re-implements the scraping loop from `scrapper.scrape()` to hook into `rich.Progress` — changes to scraping logic may need updating in both places.
- The `--fetch-details` / `--details` flag triggers per-offer HTTP requests (slow) and is required for benefits analysis.
