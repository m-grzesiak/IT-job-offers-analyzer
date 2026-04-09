#!/usr/bin/env python3
"""
IT Offers Analyzer — Interactive CLI
=====================================
Interactive interface for scraping and analyzing IT job offers from justjoin.it.
Commands auto-fetch data when needed and cache results in session.
"""

import os
import select
import statistics
import sys
import termios
import threading
import time
import tty
from collections import Counter
from types import SimpleNamespace

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

import analyzer
import scrapper

# ─── Theme ────────────────────────────────────────────────────────────────────

THEME = Theme({
    "info": "dim cyan",
    "warn": "yellow",
    "error": "bold red",
    "success": "bold green",
    "accent": "bold cyan",
    "muted": "dim",
    "salary": "bold white",
    "header": "bold magenta",
})

console = Console(theme=THEME)

# ─── State ────────────────────────────────────────────────────────────────────

state = {
    "offers": [],
    "city": None,
    "category": None,
    "experience": None,
    "workplace": None,
    "has_details": False,
}

# ─── Cancellation ────────────────────────────────────────────────────────────


class CancelledError(Exception):
    """Raised when the user cancels an operation with ESC."""
    pass


_current_op = None


class CancellableOperation:
    """Context manager that listens for ESC key to cancel the current operation."""

    def __init__(self):
        self._cancel_event = threading.Event()
        self._thread = None
        self._old_settings = None

    def __enter__(self):
        try:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            self._thread = threading.Thread(target=self._listen, daemon=True)
            self._thread.start()
        except Exception:
            pass
        return self

    def __exit__(self, *args):
        self._cancel_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if self._old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass

    def _listen(self):
        try:
            while not self._cancel_event.is_set():
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    if self._cancel_event.is_set():
                        return
                    ch = sys.stdin.read(1)
                    if ch == '\x1b':
                        self._cancel_event.set()
                        return
        except Exception:
            pass

    @property
    def cancelled(self):
        return self._cancel_event.is_set()


def check_cancel():
    """Raise CancelledError if the current operation was cancelled via ESC."""
    if _current_op and _current_op.cancelled:
        raise CancelledError()


def _cancel_aware_sleep(seconds):
    """Sleep that can be interrupted by ESC cancellation."""
    if _current_op:
        if _current_op._cancel_event.wait(timeout=seconds):
            raise CancelledError()
    else:
        time.sleep(seconds)


class CancellableProgress(Progress):
    """Progress display that shows 'Press ESC to cancel' below the progress bars."""

    def get_renderables(self):
        yield from super().get_renderables()
        if not self.finished:
            yield Text("  Press ESC to cancel", style="dim")


# ─── Constants ────────────────────────────────────────────────────────────────

CMD_ANALYZE  = "/analyze"
CMD_TOP      = "/top"
CMD_OUTLIERS = "/outliers"
CMD_BENEFITS = "/benefits"
CMD_SHOW     = "/show"
CMD_STATUS   = "/status"
CMD_HELP     = "/help"
CMD_QUIT     = "/quit"

HISTORY_PATH = os.path.expanduser("~/.it-offers-analyzer-history")

CITIES = [
    "Warszawa", "Kraków", "Wrocław", "Gdańsk", "Poznań", "Łódź",
    "Katowice", "Szczecin", "Lublin", "Bydgoszcz", "Białystok",
    "Gdynia", "Rzeszów", "Toruń", "Kielce", "Olsztyn", "Opole",
    "Gliwice", "Częstochowa",
]

BASE_STAGES = [
    (CITIES, "city"),
    (scrapper.CATEGORIES, "category"),
    (scrapper.EXPERIENCE_LEVELS, "experience"),
]

COMMAND_STAGES = {
    CMD_ANALYZE: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_TOP: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
        ([f">P{p}" for p in analyzer.PERCENTILES], "percentile threshold"),
    ],
    CMD_OUTLIERS: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_BENEFITS: BASE_STAGES + [
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_SHOW:    [],  # company names completed dynamically
    CMD_STATUS:  [],
    CMD_HELP:    [],
    CMD_QUIT:    [],
}

COMMAND_DESCRIPTIONS = {
    CMD_ANALYZE:  "salary analysis with filters",
    CMD_TOP:      "top companies by median salary",
    CMD_OUTLIERS: "offers outside the normal range",
    CMD_BENEFITS: "B2B benefits in offer descriptions",
    CMD_SHOW:     "offer details for a company",
    CMD_STATUS:   "summary of loaded data",
    CMD_HELP:     "list available commands",
    CMD_QUIT:     "exit the program",
}


class SmartCompleter(Completer):
    """Context-aware completer that suggests parameters stage-by-stage."""

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        parts = text.split()

        # Stage 0: completing the command itself
        if not parts or (len(parts) == 1 and not text.endswith(" ")):
            prefix = parts[0] if parts else ""
            for cmd in COMMAND_STAGES:
                if cmd.startswith(prefix):
                    yield Completion(
                        cmd,
                        start_position=-len(prefix),
                        display_meta=COMMAND_DESCRIPTIONS.get(cmd, ""),
                    )
            return

        cmd = parts[0].lower()

        # /show — complete with company names from loaded data
        if cmd == CMD_SHOW:
            query = " ".join(parts[1:]) if text.endswith(" ") or len(parts) > 1 else ""
            if not text.endswith(" ") and len(parts) > 1:
                query = " ".join(parts[1:])
            yield from self._complete_companies(query, text, parts)
            return

        # Staged completion for other commands
        stages = COMMAND_STAGES.get(cmd, [])
        if not stages:
            return

        used = set(parts[1:]) if text.endswith(" ") else set(parts[1:-1])
        current_word = "" if text.endswith(" ") else (parts[-1] if len(parts) > 1 else "")

        for candidates, meta in stages:
            if any(u in candidates for u in used):
                continue
            for c in candidates:
                if c in used:
                    continue
                if c.lower().startswith(current_word.lower()):
                    yield Completion(
                        c,
                        start_position=-len(current_word),
                        display_meta=meta,
                    )
            return

    def _complete_companies(self, query, text, parts):
        """Complete company names from loaded offers."""
        if not state["offers"]:
            return

        # Everything typed after "/show "
        cmd_len = len(parts[0]) + 1
        after_cmd = text[cmd_len:] if len(text) > cmd_len else ""

        seen = set()
        for o in state["offers"]:
            name = o.get("company_name", "")
            if name in seen:
                continue
            seen.add(name)
            if name.lower().startswith(after_cmd.lower()):
                yield Completion(
                    name,
                    start_position=-len(after_cmd),
                    display_meta="company",
                )


completer = SmartCompleter()


# ─── Argument parsing & data management ──────────────────────────────────────


def _parse_args(args_str):
    """Parse mixed scrape filters + analysis flags from command arguments."""
    parts = args_str.split() if args_str else []

    city = None
    category = None
    experience = None
    workplace = None
    emp_type = None
    rest = []

    top_percentile = None

    for p in parts:
        if p.startswith(">P") and p[2:].isdigit():
            top_percentile = int(p[2:])
        elif p.startswith(">") and p[1:].isdigit():
            top_percentile = int(p[1:])
        elif p in scrapper.CATEGORIES:
            category = p
        elif p in scrapper.EXPERIENCE_LEVELS:
            experience = p
        elif p in scrapper.WORKPLACE_TYPES:
            workplace = p
        elif p in scrapper.EMPLOYMENT_TYPES:
            emp_type = p
        elif not p.startswith("-"):
            matched_city = next((c for c in CITIES if c.lower() == p.lower()), None)
            if matched_city and city is None:
                city = matched_city
            else:
                rest.append(p)

    return SimpleNamespace(
        city=city, category=category, experience=experience,
        workplace=workplace, emp_type=emp_type, rest=" ".join(rest),
        top_percentile=top_percentile,
    )


def _needs_scrape(args, need_details=False):
    """Check if scraping is needed based on current cache vs requested filters."""
    if not state["offers"]:
        return True
    if args.city and args.city != state["city"]:
        return True
    if args.category and args.category != state["category"]:
        return True
    if args.experience and args.experience != state["experience"]:
        return True
    if args.workplace and args.workplace != state["workplace"]:
        return True
    if need_details and not state["has_details"]:
        return True
    return False


def _ensure_data(args, need_details=False):
    """Ensure offers are loaded, scraping if necessary."""
    if not _needs_scrape(args, need_details):
        return True

    city = args.city or state["city"]
    category = args.category or state["category"]
    experience = args.experience or state["experience"]
    workplace = args.workplace or state["workplace"]

    if not city:
        console.print("  [error]Specify city, e.g.: /analyze Kraków python senior b2b[/]")
        return False

    return _scrape(city, category, experience, workplace, need_details)


def _scrape(city, category, experience, workplace, fetch_details):
    """Scrape offers with progress. Returns True on success."""
    console.print()
    console.print("  [accent]Scraping justjoin.it...[/]")
    filters = [city]
    if category:
        filters.append(category)
    if experience:
        filters.append(experience)
    if workplace:
        filters.append(workplace)
    console.print(f"  [muted]Filters: {' / '.join(filters)}[/]")
    console.print()

    try:
        with CancellableProgress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                console=console,
        ) as progress:
            task = progress.add_task("Fetching offers...", total=None)

            params = {
                "itemsCount": scrapper.PAGE_SIZE,
                "sortBy": "publishedAt",
                "orderBy": "descending",
            }
            if city:
                params["city"] = city
            if category:
                params["categories"] = category
            if experience:
                params["experienceLevels"] = experience
            if workplace:
                params["workplaceType"] = workplace

            all_offers = []
            cursor = 0

            while True:
                data = scrapper.fetch_page(params, cursor)
                check_cancel()
                offers = data.get("data", [])
                meta = data.get("meta", {})
                total_items = meta.get("totalItems", 0)

                if progress.tasks[task].total is None:
                    progress.update(task, total=total_items)

                if not offers:
                    break

                for raw in offers:
                    all_offers.append((raw.get("slug", ""), scrapper.transform_offer(raw)))

                progress.update(task, completed=len(all_offers))

                next_info = meta.get("next", {})
                next_cursor = next_info.get("cursor")
                if next_cursor is None or next_cursor <= cursor:
                    break
                cursor = next_cursor
                _cancel_aware_sleep(0.3)

            progress.update(task, completed=len(all_offers))

            if fetch_details:
                detail_task = progress.add_task("Fetching descriptions...", total=len(all_offers))
                results = []
                for i, (slug, offer) in enumerate(all_offers):
                    try:
                        body = scrapper.fetch_detail(slug)
                        offer["body"] = body
                    except Exception:
                        pass
                    results.append(offer)
                    progress.update(detail_task, completed=i + 1)
                    check_cancel()
                    _cancel_aware_sleep(0.15)
                state["offers"] = results
                state["has_details"] = True
            else:
                state["offers"] = [offer for _, offer in all_offers]
                state["has_details"] = False

        state["city"] = city
        state["category"] = category
        state["experience"] = experience
        state["workplace"] = workplace

        console.print()
        console.print(f"  [success]Fetched {len(state['offers'])} offers[/]")
        console.print()
        return True

    except CancelledError:
        raise
    except Exception as e:
        console.print(f"  [error]Scraping error: {e}[/]")
        return False


# ─── Display helpers ─────────────────────────────────────────────────────────


def fmt_salary(val: float) -> str:
    return f"{val:,.0f} PLN"


def make_summary_table(salaries, total_offers):
    """Build a Rich table with salary analysis summary."""
    midpoints = sorted([(lo + hi) / 2 for lo, hi, _ in salaries])
    lows = sorted([lo for lo, _, _ in salaries])
    highs = sorted([hi for _, hi, _ in salaries])

    if not midpoints:
        return None

    med_low = statistics.median(lows)
    med_high = statistics.median(highs)
    med_mid = statistics.median(midpoints)

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("key", style="dim")
    table.add_column("value", style="bold white")

    no_salary = total_offers - len(salaries)

    table.add_row("Total offers", str(total_offers))
    table.add_row("With salary", str(len(salaries)))
    table.add_row("Without salary", str(no_salary))
    table.add_row("", "")
    table.add_row("Median — lower", fmt_salary(med_low))
    table.add_row("Median — upper", fmt_salary(med_high))
    table.add_row("Median — mid", fmt_salary(med_mid))

    return table, midpoints


def make_percentile_table(midpoints, title="Percentiles (mid-range)"):
    """Build a Rich table with percentile data."""
    table = Table(
        title=title,
        title_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Percentile", justify="right", style="accent")
    table.add_column("Amount", justify="right", style="salary")
    table.add_column("Offers ≤", justify="right", style="muted")
    table.add_column("", min_width=25)

    max_val = max(midpoints)
    for p in analyzer.PERCENTILES:
        val = analyzer.percentile(midpoints, p)
        count = sum(1 for m in midpoints if m <= val)
        bar_ratio = val / max_val if max_val else 0
        bar_len = int(bar_ratio * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        table.add_row(f"P{p}", fmt_salary(val), str(count), f"[cyan]{bar}[/]")

    return table


def make_distribution_table(midpoints, title="Salary Distribution"):
    """Build salary distribution table."""
    pvals = [analyzer.percentile(midpoints, p) for p in analyzer.PERCENTILES]

    brackets = [(0, pvals[0], f"< P{analyzer.PERCENTILES[0]}")]
    for i in range(1, len(pvals)):
        brackets.append((pvals[i - 1], pvals[i], f"P{analyzer.PERCENTILES[i - 1]}–P{analyzer.PERCENTILES[i]}"))
    brackets.append((pvals[-1], float("inf"), f"> P{analyzer.PERCENTILES[-1]}"))

    table = Table(
        title=title,
        title_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Bracket", justify="right", style="accent")
    table.add_column("Range", justify="right")
    table.add_column("Offers", justify="right", style="salary")
    table.add_column("%", justify="right")
    table.add_column("", min_width=25)

    total = len(midpoints)
    for lo, hi, label in brackets:
        count = sum(1 for m in midpoints if lo < m <= hi) if lo > 0 else sum(1 for m in midpoints if m <= hi)
        pct = count / total * 100 if total else 0
        bar_len = int(pct / 100 * 25)
        bar = "█" * bar_len

        hi_str = fmt_salary(hi) if hi != float("inf") else "∞"
        range_str = f"{fmt_salary(lo)} – {hi_str}"

        color = "green" if pct > 20 else "cyan" if pct > 10 else "dim"
        table.add_row(label, range_str, str(count), f"{pct:.1f}%", f"[{color}]{bar}[/]")

    return table


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_help():
    """Show help."""
    help_table = Table(show_header=False, box=None, padding=(0, 2))
    help_table.add_column("cmd", style="bold cyan", min_width=38)
    help_table.add_column("desc")

    commands = [
        (f"{CMD_ANALYZE} [city] [cat] [exp] [workplace] [type]",    CMD_ANALYZE),
        (f"{CMD_TOP} [city] [cat] [exp] [workplace] [type] [>P75]", CMD_TOP),
        (f"{CMD_OUTLIERS} [city] [cat] [exp] [workplace] [type]",   CMD_OUTLIERS),
        (f"{CMD_BENEFITS} [city] [cat] [exp] [workplace]",          CMD_BENEFITS),
        (f"{CMD_SHOW} <company>",                                    CMD_SHOW),
        (CMD_STATUS,                                                 CMD_STATUS),
        (CMD_HELP,                                                   CMD_HELP),
        (CMD_QUIT,                                                   CMD_QUIT),
    ]

    for syntax, cmd in commands:
        help_table.add_row(syntax, COMMAND_DESCRIPTIONS[cmd])

    console.print()
    console.print(Panel(help_table, title="[bold]Commands[/]", border_style="dim", padding=(1, 2)))
    console.print()


def cmd_status():
    """Show current state."""
    console.print()
    if not state["offers"]:
        console.print("  [muted]No offers loaded. Run a command like /analyze Kraków python senior[/]")
    else:
        n = len(state["offers"])
        has_salary = sum(1 for o in state["offers"]
                         if any(et.get("salary_from") for et in o.get("employment_types", [])))
        has_body = sum(1 for o in state["offers"] if o.get("body"))

        info = Table(show_header=False, box=None, padding=(0, 2))
        info.add_column("k", style="dim")
        info.add_column("v", style="bold")
        info.add_row("Offers", str(n))
        info.add_row("With salary", str(has_salary))
        info.add_row("With description", str(has_body))
        if state["city"]:
            info.add_row("City", state["city"])
        if state["category"]:
            info.add_row("Category", state["category"])
        if state["experience"]:
            info.add_row("Experience", state["experience"])
        if state["workplace"]:
            info.add_row("Workplace", state["workplace"])

        console.print(Panel(info, title="[bold]Status[/]", border_style="dim", padding=(1, 2)))
    console.print()


def cmd_analyze(args_str: str):
    """Salary analysis."""
    args = _parse_args(args_str)
    if not _ensure_data(args):
        return

    salaries = analyzer.extract_salaries(state["offers"], args.emp_type)

    if not salaries:
        console.print("  [warn]No offers with salary data[/]")
        return

    total_offers = len(state["offers"])
    types_to_show = [args.emp_type] if args.emp_type else scrapper.EMPLOYMENT_TYPES

    for et in types_to_show:
        et_salaries = analyzer.extract_salaries(state["offers"], et) if et else salaries
        if not et_salaries:
            continue
        result = make_summary_table(et_salaries, total_offers)
        if not result:
            continue
        et_table, et_midpoints = result
        label = et.upper() if et else "all types"
        console.print()
        console.print(Panel(
            et_table,
            title=f"[bold]Summary — {label}[/]",
            border_style="magenta",
            padding=(1, 2),
        ))
        console.print()
        console.print(make_percentile_table(et_midpoints, f"Percentiles — {label}"))
        console.print()
        console.print(make_distribution_table(et_midpoints, f"Salary Distribution — {label}"))

    console.print()


def _print_top_for_type(salaries, pct: int, label: str):
    """Print top-companies tables for a single employment type."""
    midpoints = sorted([(lo + hi) / 2 for lo, hi, _ in salaries])
    if len(midpoints) < 10:
        console.print(f"  [muted]{label}: not enough data[/]")
        return

    threshold = analyzer.percentile(midpoints, pct)
    above = [(lo, hi, o) for lo, hi, o in salaries if (lo + hi) / 2 > threshold]
    above.sort(key=lambda x: (x[0] + x[1]) / 2, reverse=True)

    if not above:
        console.print(f"  [muted]{label}: no offers > P{pct}[/]")
        return

    company_counts = Counter(o["company_name"] for _, _, o in above)

    summary = Table(
        title=f"Companies > P{pct} ({fmt_salary(threshold)}) — {label}",
        title_style="bold magenta",
        border_style="dim",
    )
    summary.add_column("Company", style="bold")
    summary.add_column("Offers", justify="right", style="accent")
    summary.add_column("Min", justify="right")
    summary.add_column("Max", justify="right", style="salary")

    for company, count in company_counts.most_common():
        mids = [(lo + hi) / 2 for lo, hi, o in above if o["company_name"] == company]
        summary.add_row(company, str(count), fmt_salary(min(mids)), fmt_salary(max(mids)))

    console.print()
    console.print(summary)

    detail = Table(
        title=f"Offer details > P{pct} — {label}",
        title_style="bold magenta",
        border_style="dim",
    )
    detail.add_column("Mid", justify="right", style="salary")
    detail.add_column("From", justify="right")
    detail.add_column("To", justify="right")
    detail.add_column("Company", style="bold")
    detail.add_column("Title", style="dim")

    for lo, hi, offer in above:
        mid = (lo + hi) / 2
        detail.add_row(fmt_salary(mid), fmt_salary(lo), fmt_salary(hi),
                       offer["company_name"], offer["title"])

    console.print()
    console.print(detail)


def cmd_top(args_str: str):
    """Show companies above P90."""
    args = _parse_args(args_str)
    if not _ensure_data(args):
        return

    pct = args.top_percentile or 90
    types_to_show = [args.emp_type] if args.emp_type else scrapper.EMPLOYMENT_TYPES

    any_data = False
    for et in types_to_show:
        et_salaries = analyzer.extract_salaries(state["offers"], et)
        if not et_salaries:
            continue
        any_data = True
        label = et.upper() if et else "all"
        _print_top_for_type(et_salaries, pct, label)

    if not any_data:
        console.print("  [warn]No offers with salary data[/]")
        return

    console.print()
    console.print("  [muted]Use /show <company> to see all offers for a given company[/]")
    console.print()


def cmd_outliers(args_str: str):
    """Show detected outliers."""
    args = _parse_args(args_str)
    if not _ensure_data(args):
        return

    salaries = analyzer.extract_salaries(state["offers"], args.emp_type)
    _, outliers = analyzer.detect_outliers(salaries)

    if not outliers:
        console.print("  [success]No outliers[/]")
        return

    table = Table(
        title=f"Detected outliers ({len(outliers)})",
        title_style="bold yellow",
        border_style="yellow",
    )
    table.add_column("Mid", justify="right", style="salary")
    table.add_column("From", justify="right")
    table.add_column("To", justify="right")
    table.add_column("Company", style="bold")
    table.add_column("Title", style="dim")

    for lo, hi, offer in sorted(outliers, key=lambda x: (x[0] + x[1]) / 2, reverse=True):
        mid = (lo + hi) / 2
        table.add_row(fmt_salary(mid), fmt_salary(lo), fmt_salary(hi),
                      offer["company_name"], offer["title"])

    console.print()
    console.print(table)
    console.print()


def cmd_benefits(args_str: str):
    """Analyze B2B benefits."""
    args = _parse_args(args_str)
    if not _ensure_data(args, need_details=True):
        return

    b2b_with_body = [
        o for o in state["offers"]
        if o.get("body") and any(et.get("type") == "b2b" for et in o.get("employment_types", []))
    ]

    if not b2b_with_body:
        console.print("  [warn]No B2B offers with description[/]")
        return

    with_vac, with_sick, with_extra, with_any = [], [], [], []

    for offer in b2b_with_body:
        text = analyzer.strip_html(offer["body"])
        vac = analyzer.search_keywords(text, analyzer.KEYWORDS_VACATION)
        sick = analyzer.search_keywords(text, analyzer.KEYWORDS_SICK)
        extra = analyzer.search_keywords(text, analyzer.KEYWORDS_EXTRA_BENEFITS)
        if vac:
            with_vac.append((offer, vac))
        if sick:
            with_sick.append((offer, sick))
        if extra:
            with_extra.append((offer, extra))
        if vac or sick or extra:
            with_any.append((offer, vac, sick, extra))

    total = len(b2b_with_body)
    pct = lambda n: f"{n}/{total} ({n / total * 100:.1f}%)"

    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("k", style="dim")
    summary.add_column("v", style="bold")
    summary.add_row("B2B offers with desc", str(total))
    summary.add_row("Mentions vacation", pct(len(with_vac)))
    summary.add_row("Mentions sick leave", pct(len(with_sick)))
    summary.add_row("Cafeteria/extras", pct(len(with_extra)))

    console.print()
    console.print(Panel(summary, title="[bold]B2B Benefits[/]", border_style="magenta", padding=(1, 2)))

    if with_any:
        table = Table(
            title="Offers with benefits",
            title_style="bold magenta",
            border_style="dim",
        )
        table.add_column("Company", style="bold", max_width=28)
        table.add_column("Vacation", style="green")
        table.add_column("Sick leave", style="yellow")
        table.add_column("Extras", style="cyan")
        table.add_column("Title", style="dim", max_width=40)

        for offer, vac, sick, extra in with_any:
            table.add_row(
                offer["company_name"],
                ", ".join(vac) if vac else "-",
                ", ".join(sick) if sick else "-",
                ", ".join(extra) if extra else "-",
                offer["title"],
            )

        console.print()
        console.print(table)

    console.print()


def cmd_show(args_str: str):
    """Show offers from a specific company."""
    if not state["offers"]:
        console.print("  [error]No data. Run a command first, e.g.: /analyze Kraków python senior[/]")
        return

    query = args_str.strip().lower() if args_str else ""
    if not query:
        console.print("  [error]Specify company name: /show Revolut[/]")
        return

    matches = [o for o in state["offers"] if query in o.get("company_name", "").lower()]

    if not matches:
        console.print(f"  [warn]No offers found for \"{args_str.strip()}\"[/]")
        return

    table = Table(
        title=f"{matches[0]['company_name']} — {len(matches)} offers",
        title_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Title", style="bold")
    table.add_column("Level", style="accent")
    table.add_column("City")
    table.add_column("Workplace")
    table.add_column("From", justify="right")
    table.add_column("To", justify="right", style="salary")
    table.add_column("Type")
    table.add_column("Currency")

    for o in matches:
        has_salary = False
        for et in o.get("employment_types", []):
            sfrom = et.get("salary_from")
            sto = et.get("salary_to")
            et_type = et.get("type", "") or ""
            currency = (et.get("currency", "") or "").upper()
            if sfrom is not None:
                table.add_row(
                    o["title"], o.get("experience_level", ""),
                    o.get("city", ""), o.get("workplace_type", ""),
                    f"{sfrom:,.0f}", f"{sto:,.0f}", et_type, currency,
                )
                has_salary = True
        if not has_salary:
            types = "/".join(dict.fromkeys(filter(None, (et.get("type") for et in o.get("employment_types", [])))))
            table.add_row(
                o["title"], o.get("experience_level", ""),
                o.get("city", ""), o.get("workplace_type", ""),
                "[dim]-[/]", "[dim]-[/]", f"[dim]{types or '-'}[/]", "[dim]-[/]",
            )

    console.print()
    console.print(table)
    console.print()


# ─── Command router ──────────────────────────────────────────────────────────

COMMANDS = {
    CMD_HELP:     (cmd_help, ""),
    CMD_STATUS:   (cmd_status, ""),
    CMD_ANALYZE:  (cmd_analyze, "args"),
    CMD_TOP:      (cmd_top, "args"),
    CMD_OUTLIERS: (cmd_outliers, "args"),
    CMD_BENEFITS: (cmd_benefits, "args"),
    CMD_SHOW:     (cmd_show, "args"),
    CMD_QUIT:     (None, ""),
}


def dispatch(user_input: str):
    """Route user input to the right command."""
    stripped = user_input.strip()
    if not stripped:
        return True

    if not stripped.startswith("/"):
        console.print("  [muted]Type /help to see available commands[/]")
        return True

    parts = stripped.split(None, 1)
    cmd = parts[0].lower()
    args_str = parts[1] if len(parts) > 1 else ""

    if cmd == CMD_QUIT:
        return False

    if cmd in COMMANDS:
        func, sig = COMMANDS[cmd]
        if func:
            global _current_op
            with CancellableOperation() as op:
                _current_op = op
                try:
                    func(args_str) if sig == "args" else func()
                except CancelledError:
                    console.print("\n  [warn]Operation cancelled[/]")
                finally:
                    _current_op = None
    else:
        console.print(f"  [error]Unknown command: {cmd}[/]")
        console.print("  [muted]Type /help to see available commands[/]")

    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

BANNER = (
    "\n"
    "[bold magenta]"
    r"        __________   ____  ______________________  _____" "\n"
    r"       /  _/_  __/  / __ \/ ____/ ____/ ____/ __ \/ ___/" "\n"
    r"       / /  / /    / / / / /_  / /_  / __/ / /_/ /\__ \ " "\n"
    r"     _/ /  / /    / /_/ / __/ / __/ / /___/ _, _/___/ / " "\n"
    r"    /___/ /_/     \____/_/   /_/   /_____/_/ |_|/____/  " "\n"
    "[/]"
    "[bold cyan]"
    r"        ___    _   _____    ____  _______   __________ " "\n"
    r"       /   |  / | / /   |  / /\ \/ /__  /  / ____/ __ " "\\\n"
    r"      / /| | /  |/ / /| | / /  \  /  / /  / __/ / /_/ /" "\n"
    r"     / ___ |/ /|  / ___ |/ /___/ /  / /__/ /___/ _, _/ " "\n"
    r"    /_/  |_/_/ |_/_/  |_/_____/_/  /____/_____/_/ |_|  " "\n"
    "[/]"
    "[dim]    ───────────────────────────────────────────────────[/]\n"
    "[dim]    justjoin.it  ·  salary explorer  ·  v0.1[/]\n"
)


def _show_welcome():
    """Show welcome screen with quick-start commands."""
    console.print(BANNER, highlight=False)

    quick = Table(show_header=False, box=None, padding=(0, 2))
    quick.add_column("cmd", style="bold cyan", min_width=16)
    quick.add_column("desc", style="dim")

    for cmd in (CMD_ANALYZE, CMD_TOP, CMD_BENEFITS, CMD_HELP):
        quick.add_row(cmd, COMMAND_DESCRIPTIONS[cmd])

    console.print(Panel(
        quick,
        title="[bold]Quick start[/]",
        subtitle="[dim]Tab for auto-complete · ESC to cancel[/]",
        border_style="dim",
        padding=(1, 2),
        width=56,
    ))
    console.print()
    console.print("  [muted]Try:[/] [accent]/analyze Kraków python senior b2b[/]")
    console.print()


def main():
    from prompt_toolkit.styles import Style as PTStyle
    prompt_style = PTStyle.from_dict({"prompt": "ansicyan bold"})

    _show_welcome()

    session = PromptSession(
        history=FileHistory(HISTORY_PATH),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
    )

    while True:
        try:
            user_input = session.prompt(
                [("class:prompt", "❯ ")],
                style=prompt_style,
            )
            if not dispatch(user_input):
                console.print("  [muted]Goodbye![/]")
                break
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [muted]Goodbye![/]")
            break


if __name__ == "__main__":
    main()
