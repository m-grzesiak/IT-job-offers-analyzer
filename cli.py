#!/usr/bin/env python3
"""
IT Offers Analyzer — Interactive CLI
=====================================
Interactive interface for scraping and analyzing IT job offers from justjoin.it.
Commands auto-fetch data when needed and cache results in session.
"""

import os
import statistics
import time
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
    "has_details": False,
}

# ─── Constants ────────────────────────────────────────────────────────────────

HISTORY_PATH = os.path.expanduser("~/.it-offers-analyzer-history")

CITIES = [
    "Warszawa", "Kraków", "Wrocław", "Gdańsk", "Poznań", "Łódź",
    "Katowice", "Szczecin", "Lublin", "Bydgoszcz", "Białystok",
    "Gdynia", "Rzeszów", "Toruń", "Kielce", "Olsztyn", "Opole",
    "Gliwice", "Częstochowa",
]

SCRAPE_STAGES = [
    (CITIES, "city"),
    (scrapper.CATEGORIES, "category"),
    (scrapper.EXPERIENCE_LEVELS, "experience"),
]

COMMAND_STAGES = {
    "/analyze": SCRAPE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
    ],
    "/top": SCRAPE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        ([f">P{p}" for p in analyzer.PERCENTILES], "percentile threshold"),
    ],
    "/outliers": SCRAPE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
    ],
    "/benefits": SCRAPE_STAGES,
    "/show": [],  # company names completed dynamically
    "/status": [],
    "/help": [],
    "/quit": [],
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
                        display_meta="command",
                    )
            return

        cmd = parts[0].lower()

        # /show — complete with company names from loaded data
        if cmd == "/show":
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

        seen = set()
        if len(parts) > 1:
            partial = " ".join(parts[1:])
            if text.endswith(" "):
                partial += " "
        else:
            partial = ""

        for o in state["offers"]:
            name = o.get("company_name", "")
            if name in seen:
                continue
            seen.add(name)
            if name.lower().startswith(partial.lower().strip()):
                yield Completion(
                    name,
                    start_position=-len(partial.rstrip()),
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
        emp_type=emp_type, rest=" ".join(rest),
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

    if not city:
        console.print("  [error]Specify city, e.g.: /analyze Kraków python senior b2b[/]")
        return False

    return _scrape(city, category, experience, need_details)


def _scrape(city, category, experience, fetch_details):
    """Scrape offers with progress. Returns True on success."""
    console.print()
    console.print("  [accent]Scraping justjoin.it...[/]")
    filters = [city]
    if category:
        filters.append(category)
    if experience:
        filters.append(experience)
    console.print(f"  [muted]Filters: {' / '.join(filters)}[/]")
    console.print()

    try:
        with Progress(
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

            all_offers = []
            cursor = 0

            while True:
                data = scrapper.fetch_page(params, cursor)
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
                time.sleep(0.3)

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
                    time.sleep(0.15)
                state["offers"] = results
                state["has_details"] = True
            else:
                state["offers"] = [offer for _, offer in all_offers]
                state["has_details"] = False

        state["city"] = city
        state["category"] = category
        state["experience"] = experience

        console.print()
        console.print(f"  [success]Fetched {len(state['offers'])} offers[/]")
        console.print()
        return True

    except Exception as e:
        console.print(f"  [error]Scraping error: {e}[/]")
        return False


# ─── Display helpers ─────────────────────────────────────────────────────────


def fmt_salary(val: float) -> str:
    return f"{val:,.0f} PLN"


def make_summary_table(salaries, total_offers):
    """Build a Rich table with salary analysis summary."""
    clean, outliers = analyzer.detect_outliers(salaries)
    active = salaries

    midpoints = sorted([(lo + hi) / 2 for lo, hi, _ in active])
    lows = sorted([lo for lo, _, _ in active])
    highs = sorted([hi for _, hi, _ in active])

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
    outlier_label = str(len(outliers))

    table.add_row("Total offers", str(total_offers))
    table.add_row("With salary", str(len(salaries)))
    table.add_row("Without salary", str(no_salary))
    table.add_row("Outliers", outlier_label)
    table.add_row("", "")
    table.add_row("Median — lower", fmt_salary(med_low))
    table.add_row("Median — upper", fmt_salary(med_high))
    table.add_row("Median — mid", fmt_salary(med_mid))

    return table, midpoints, outliers


def make_percentile_table(midpoints):
    """Build a Rich table with percentile data."""
    table = Table(
        title="Percentiles (mid-range)",
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


def make_distribution_table(midpoints):
    """Build salary distribution table."""
    pvals = [analyzer.percentile(midpoints, p) for p in analyzer.PERCENTILES]

    brackets = [(0, pvals[0], f"< P{analyzer.PERCENTILES[0]}")]
    for i in range(1, len(pvals)):
        brackets.append((pvals[i - 1], pvals[i], f"P{analyzer.PERCENTILES[i - 1]}–P{analyzer.PERCENTILES[i]}"))
    brackets.append((pvals[-1], float("inf"), f"> P{analyzer.PERCENTILES[-1]}"))

    table = Table(
        title="Salary Distribution",
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
        ("/analyze [city] [cat] [exp] [type]", "Salary analysis"),
        ("/top [city] [cat] [exp] [type] [>P75]", "Companies above percentile (default >P90)"),
        ("/outliers [city] [cat] [exp] [type]", "Show detected outliers"),
        ("/benefits [city] [cat] [exp]", "B2B benefits (auto-fetches details)"),
        ("/show <company>", "Show offers for a company"),
        ("/status", "Current data status"),
        ("/help", "Show this help"),
        ("/quit", "Exit"),
    ]

    for cmd, desc in commands:
        help_table.add_row(cmd, desc)

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
    result = make_summary_table(salaries, total_offers)
    if not result:
        return
    summary_table, midpoints, outliers = result

    label = args.emp_type.upper() if args.emp_type else "all types"
    console.print()
    console.print(Panel(
        summary_table,
        title=f"[bold]Summary — {label}[/]",
        border_style="magenta",
        padding=(1, 2),
    ))

    console.print()
    console.print(make_percentile_table(midpoints))
    console.print()
    console.print(make_distribution_table(midpoints))
    console.print()


def cmd_top(args_str: str):
    """Show companies above P90."""
    args = _parse_args(args_str)
    if not _ensure_data(args):
        return

    salaries = analyzer.extract_salaries(state["offers"], args.emp_type)
    active = salaries

    midpoints = sorted([(lo + hi) / 2 for lo, hi, _ in active])
    if len(midpoints) < 10:
        console.print("  [warn]Not enough data[/]")
        return

    pct = args.top_percentile or 90
    threshold = analyzer.percentile(midpoints, pct)

    above = [(lo, hi, o) for lo, hi, o in active if (lo + hi) / 2 > threshold]
    above.sort(key=lambda x: (x[0] + x[1]) / 2, reverse=True)

    if not above:
        console.print(f"  [muted]No offers > P{pct}[/]")
        return

    company_counts = Counter(o["company_name"] for _, _, o in above)

    summary = Table(
        title=f"Companies > P{pct} ({fmt_salary(threshold)})",
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
        title=f"Offer details > P{pct}",
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

    for o in matches:
        for et in o.get("employment_types", []):
            sfrom = et.get("salary_from")
            sto = et.get("salary_to")
            if sfrom is not None:
                lo = analyzer.normalize_monthly(sfrom)
                hi = analyzer.normalize_monthly(sto)
                table.add_row(
                    o["title"], o.get("experience_level", ""),
                    o.get("city", ""), o.get("workplace_type", ""),
                    fmt_salary(lo), fmt_salary(hi), et.get("type", ""),
                )
                break
        else:
            table.add_row(
                o["title"], o.get("experience_level", ""),
                o.get("city", ""), o.get("workplace_type", ""),
                "[dim]-[/]", "[dim]-[/]", "",
            )

    console.print()
    console.print(table)
    console.print()


# ─── Command router ──────────────────────────────────────────────────────────

COMMANDS = {
    "/help": (cmd_help, ""),
    "/status": (cmd_status, ""),
    "/analyze": (cmd_analyze, "args"),
    "/top": (cmd_top, "args"),
    "/outliers": (cmd_outliers, "args"),
    "/benefits": (cmd_benefits, "args"),
    "/show": (cmd_show, "args"),
    "/quit": (None, ""),
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

    if cmd == "/quit":
        return False

    if cmd in COMMANDS:
        func, sig = COMMANDS[cmd]
        if func:
            func(args_str) if sig == "args" else func()
    else:
        console.print(f"  [error]Unknown command: {cmd}[/]")
        console.print("  [muted]Type /help to see available commands[/]")

    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

BANNER = """[bold magenta]
  IT Job Offers Analyzer[/]
  [dim]v0.1[/]
"""


def main():
    console.print(BANNER)
    console.print("  [muted]Type[/] [accent]/help[/] [muted]to see commands[/]")
    console.print()

    session = PromptSession(
        history=FileHistory(HISTORY_PATH),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
    )

    while True:
        try:
            user_input = session.prompt(
                [("class:prompt", "❯ ")],
                style=_prompt_style(),
            )
            if not dispatch(user_input):
                console.print("  [muted]Goodbye![/]")
                break
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [muted]Goodbye![/]")
            break


def _prompt_style():
    from prompt_toolkit.styles import Style as PTStyle
    return PTStyle.from_dict({
        "prompt": "ansicyan bold",
    })


if __name__ == "__main__":
    main()
