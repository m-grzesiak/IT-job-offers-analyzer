# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool for scraping and analyzing IT job offers from justjoin.it (Polish job board). Distributed as a PyPI package (`itjobs`).

## Setup & Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .   # editable install — includes rich, prompt_toolkit
```

**Run tests:**
```bash
pip install -e .[test]
pytest
```

**Interactive CLI** (primary interface):
```bash
itjobs
# Commands auto-fetch data when needed:
#   /analyze Kraków python senior b2b
#   /top b2b >P75        (top companies above P75)
#   /benefits Kraków python senior  (auto-fetches offer details)
#   /recent 7 Kraków python         (offers from last 7 days)
```

## Architecture

Python package `it_job_offers_analyzer/` with two core modules and a `cli/` subpackage:

- **`scrapper.py`** — Scrapes justjoin.it REST API (`/api/candidate-api/offers`). Handles pagination via `iter_pages()` generator, optional detail fetching (full HTML descriptions via `fetch_detail(slug)`). Uses only stdlib (`urllib`, `json`). Exports constants: `CATEGORIES`, `EXPERIENCE_LEVELS`, `WORKPLACE_TYPES`, `EMPLOYMENT_TYPES`.

- **`analyzer.py`** — Statistical salary analysis. Normalizes salaries to monthly PLN using magnitude heuristics (the API's unit field is unreliable). IQR-based outlier detection. Percentile distribution. B2B benefits keyword search against HTML offer bodies. Uses only stdlib (`statistics`, `re`).

- **`cli/`** — Interactive REPL built with `rich` + `prompt_toolkit`. Split into focused modules:
  - `app.py` — REPL loop, command dispatch, welcome screen, auto-update check via PyPI
  - `commands.py` — all `/command` implementations (`cmd_analyze`, `cmd_top`, `cmd_outliers`, `cmd_benefits`, `cmd_progression`, `cmd_compare`, `cmd_recent`, `cmd_companies`, `cmd_show`, `cmd_help`, `cmd_status`, `cmd_clear`)
  - `display.py` — Rich console/theme, `SalaryStats` view-model, table builders, formatting helpers (`fmt_salary`, `fmt_delta`, `print_bar_chart`)
  - `scraping.py` — CLI scraping orchestration with progress bars (`ensure_data`, `require_data`, `scrape_groups`)
  - `state.py` — `SessionState` cache and `FilterArgs` dataclass
  - `parsing.py` — argument parsing for commands (`parse_args`, `parse_compare_args`) with did-you-mean suggestions
  - `completer.py` — context-aware tab completion and key bindings
  - `cancel.py` — ESC-key cancellation infrastructure (`CancellableOperation`, `CancellableProgress`, `check_cancel`, `cancel_aware_sleep`)
  - `constants.py` — cities, command metadata (`COMMAND_DESCRIPTIONS`, `COMMAND_SYNTAX`, `COMMAND_STAGES`), banner

- **`tests/`** — pytest suite with per-module test files (`test_analyzer.py`, `test_scrapper.py`, `test_cli_*.py`). Uses `conftest.py` for shared fixtures.

Entry point (defined in `pyproject.toml`):
- `itjobs` → `it_job_offers_analyzer.cli:main`

## Key Design Decisions

- Salary normalization (`analyzer.normalize_monthly`) uses value magnitude to detect hourly/daily/monthly/yearly rates instead of trusting the API's unit field.
- The scraper uses raw `urllib` (no `requests` dependency) with browser-like headers.
- `cli/scraping.py` re-implements the scraping loop from `scrapper.iter_pages()` to hook into `rich.Progress` — changes to pagination/fetching logic may need updating in both `scrapper.py` and `cli/scraping.py`.
- Detail fetching (per-offer HTTP requests) is slow and required for benefits analysis. In the CLI, `/benefits` triggers this automatically. In the standalone scraper, use `--fetch-details`.
- `/top` accepts a `>P{n}` argument to set the percentile threshold (e.g. `/top b2b >P75`); defaults to P90.
- `/recent` accepts a bare number for days (e.g. `/recent 7`); defaults to 3. Uses `last_published_at` to filter by real publication date.
- `SessionState` in `cli/state.py` caches offers per session — re-scraping only happens when filters change or details are newly needed.
- `SalaryStats` dataclass in `cli/display.py` extracts the repeated median/midpoint computation used across multiple commands.
- `scrape_groups()` in `cli/scraping.py` is the shared scraping loop for multi-group commands (`/progression`, `/compare`).
- `/show` uses tiered matching (exact → startswith → substring) for company names and shows vs-median delta columns.
- Auto-update check runs in a background thread on startup, queries PyPI, and shows a notice if a newer version exists.
- Command history is persisted to `~/.itjobs-history` and auto-cleared when older than 30 days.

## Building & Publishing

```bash
pip install build twine
python -m build              # produces dist/*.tar.gz and dist/*.whl
twine upload dist/*          # publish to PyPI (requires ~/.pypirc or token)
```
