"""Command implementations for the interactive CLI."""

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone

from rich.table import Table

from .constants import (
    CITIES,
    COMMAND_DESCRIPTIONS,
    COMMAND_SYNTAX,
)
from .display import (
    C_BORDER,
    C_CYAN,
    C_GREEN,
    C_ORANGE,
    SalaryStats,
    console,
    fmt_delta,
    fmt_salary,
    fmt_tag,
    make_distribution_table,
    make_panel,
    make_percentile_table,
    make_summary_table,
    make_table,
    print_bar_chart,
    print_hint,
)
from .parsing import parse_args, parse_compare_args
from .scraping import ensure_data, require_data, scrape_groups
from .state import state
from .. import analyzer
from .. import scrapper


# ---- Informational commands ----


def cmd_help():
    """Show help with parameter details."""
    help_table = Table(show_header=False, box=None, padding=(0, 2))
    help_table.add_column("cmd", style=f"bold {C_CYAN}", no_wrap=True)
    help_table.add_column("desc")
    for cmd in sorted(COMMAND_SYNTAX):
        help_table.add_row(COMMAND_SYNTAX[cmd], COMMAND_DESCRIPTIONS[cmd])

    console.print()
    console.print(make_panel(
        help_table,
        "Commands", icon="\u25c6",
        border_style=C_BORDER,
        expand=False,
    ))
    console.print()

    params_table = Table(show_header=True, box=None, padding=(0, 2))
    params_table.add_column("Parameter", style=f"bold {C_ORANGE}", no_wrap=True)
    params_table.add_column("Values", style="dim")
    params_table.add_row("\\[city]", ", ".join(CITIES[:8]) + ", \u2026")
    params_table.add_row("\\[cat]", ", ".join(scrapper.CATEGORIES[:10]) + ", \u2026")
    params_table.add_row("\\[exp]", ", ".join(scrapper.EXPERIENCE_LEVELS))
    params_table.add_row("\\[workplace]", ", ".join(scrapper.WORKPLACE_TYPES))
    params_table.add_row("\\[type]", ", ".join(scrapper.EMPLOYMENT_TYPES))
    params_table.add_row(
        "\\[>P75]",
        "percentile threshold: " + ", ".join(f">P{p}" for p in analyzer.PERCENTILES),
    )
    params_table.add_row("\\[days]", "number of days for /recent (default: 3)")
    params_table.add_row("<company>", "company name [bold](required)[/]")

    console.print(make_panel(
        params_table,
        "Parameters", icon="\u25c6",
        subtitle=f"[{C_BORDER}] \\[brackets] = optional   <angle> = required [/]",
        border_style=C_BORDER,
        expand=False,
    ))
    console.print()

    compare_table = Table(show_header=False, box=None, padding=(0, 2))
    compare_table.add_column("example", style=f"bold {C_CYAN}", no_wrap=True)
    compare_table.add_column("desc", style="dim")
    compare_table.add_row("/compare Krak\u00f3w Warszawa python senior b2b", "compare 2 cities")
    compare_table.add_row("/compare Krak\u00f3w Warszawa Wroc\u0142aw python senior", "compare 3 cities")
    compare_table.add_row("/compare Krak\u00f3w python java senior b2b", "compare categories")
    compare_table.add_row("/compare Krak\u00f3w python senior b2b permanent", "compare employment types")
    compare_table.add_row("/compare Krak\u00f3w python junior senior b2b", "compare experience levels")
    compare_table.add_row("/compare Krak\u00f3w python remote office b2b", "compare workplace types")

    console.print(make_panel(
        compare_table,
        "/compare \u2014 examples", icon="\u25b8",
        subtitle=f"[{C_BORDER}] pass 2+ values from one group \u00b7 rest are filters [/]",
        border_style=C_BORDER,
        expand=False,
    ))
    console.print()

    recent_table = Table(show_header=False, box=None, padding=(0, 2))
    recent_table.add_column("example", style=f"bold {C_CYAN}", no_wrap=True)
    recent_table.add_column("desc", style="dim")
    recent_table.add_row("/recent Krak\u00f3w python senior", "last 3 days (default)")
    recent_table.add_row("/recent 7 Krak\u00f3w python", "last 7 days")
    recent_table.add_row("/recent 1 b2b", "last 24h, B2B only")

    console.print(make_panel(
        recent_table,
        "/recent \u2014 examples", icon="\u25b8",
        subtitle=f"[{C_BORDER}] \\[days] defaults to 3 \u00b7 shows per-day chart + offer list [/]",
        border_style=C_BORDER,
        expand=False,
    ))
    console.print()


def cmd_status():
    """Show current session state."""
    console.print()
    if not state.offers:
        console.print("  [muted]No offers loaded. Run a command like /analyze Krak\u00f3w python senior[/]")
    else:
        has_salary = sum(
            1 for o in state.offers
            if any(et.get("salary_from") for et in o.get("employment_types", []))
        )
        has_body = sum(1 for o in state.offers if o.get("body"))

        info = Table(show_header=False, box=None, padding=(0, 2))
        info.add_column("k", style="dim")
        info.add_column("v", style="bold")
        info.add_row("Offers", str(len(state.offers)))
        info.add_row("With salary", str(has_salary))
        info.add_row("With description", str(has_body))
        if state.city:
            info.add_row("City", state.city)
        if state.category:
            info.add_row("Category", state.category)
        if state.experience:
            info.add_row("Experience", state.experience)
        if state.workplace:
            info.add_row("Workplace", state.workplace)

        console.print(make_panel(info, "Status", icon="\u25cf", border_style=C_BORDER))
    console.print()


def cmd_clear():
    """Clear screen and reset session state."""
    from .app import show_welcome  # local import to avoid circular dependency

    state.reset()
    console.clear()
    show_welcome()


# ---- Analysis commands ----


def cmd_analyze(args_str: str):
    """Salary analysis with percentile and distribution tables."""
    args = parse_args(args_str)
    if args is None or not ensure_data(args):
        return

    total_offers = len(state.offers)
    types_to_show = [args.emp_type] if args.emp_type else scrapper.EMPLOYMENT_TYPES

    any_data = False
    for et in types_to_show:
        salaries = analyzer.extract_salaries(state.offers, et)
        stats = SalaryStats.compute(salaries)
        if not stats:
            continue
        any_data = True
        label = et.upper() if et else "all types"
        console.print()
        console.print(make_panel(make_summary_table(stats, total_offers), f"Summary \u2014 {label}", icon="\u25cf"))
        console.print()
        console.print(make_percentile_table(stats.midpoints, f"Percentiles \u2014 {label}"))
        console.print()
        console.print(make_distribution_table(stats.midpoints, f"Salary Distribution \u2014 {label}"))

    if not any_data:
        console.print("  [warn]No offers with salary data[/]")
        return

    console.print()
    print_hint("/top >P75", "/outliers", "/show <company>")
    console.print()


def cmd_top(args_str: str):
    """Show companies above a percentile threshold."""
    args = parse_args(args_str)
    if args is None or not ensure_data(args):
        return

    pct = args.top_percentile or 90
    types_to_show = [args.emp_type] if args.emp_type else scrapper.EMPLOYMENT_TYPES

    any_data = False
    for et in types_to_show:
        salaries = analyzer.extract_salaries(state.offers, et)
        if not salaries:
            continue
        any_data = True
        label = et.upper() if et else "all"
        _print_top_for_type(salaries, pct, label)

    if not any_data:
        console.print("  [warn]No offers with salary data[/]")
        return

    console.print()
    print_hint("/show <company>", desc="to see all offers for a given company")
    console.print()


def cmd_outliers(args_str: str):
    """Show detected salary outliers."""
    args = parse_args(args_str)
    if args is None or not ensure_data(args):
        return

    salaries = analyzer.extract_salaries(state.offers, args.emp_type)
    _, outliers = analyzer.detect_outliers(salaries)

    if not outliers:
        console.print("  [success]No outliers[/]")
        return

    table = make_table(
        f"\u26a0 Detected outliers ({len(outliers)})",
        title_style=f"bold {C_ORANGE}",
        border_style=C_ORANGE,
    )
    table.add_column("Mid", justify="right")
    table.add_column("From", justify="right")
    table.add_column("To", justify="right")
    table.add_column("Company")
    table.add_column("Title")

    for lo, hi, offer in sorted(outliers, key=lambda x: analyzer.midpoint(x[0], x[1]), reverse=True):
        mid = analyzer.midpoint(lo, hi)
        table.add_row(
            fmt_salary(mid), fmt_salary(lo), fmt_salary(hi),
            offer["company_name"], offer["title"],
        )

    console.print()
    console.print(table)
    console.print()
    print_hint("/show <company>", desc="to see all offers for a given company")
    console.print()


def cmd_benefits(args_str: str):
    """Analyze B2B benefits (vacation, sick leave, extras)."""
    args = parse_args(args_str)
    if args is None or not ensure_data(args, need_details=True):
        return

    b2b_with_body = [
        o for o in state.offers
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
    console.print(make_panel(summary, "B2B Benefits", icon="\u25c6"))

    if with_any:
        table = make_table("Offers with benefits")
        table.add_column("Company", max_width=28)
        table.add_column("Vacation", style=C_GREEN)
        table.add_column("Sick leave", style=C_ORANGE)
        table.add_column("Extras", style=C_CYAN)
        table.add_column("Title", max_width=40)

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
    print_hint("/show <company>", desc="to see offer details")
    console.print()


# ---- Multi-group commands ----


def cmd_progression(args_str: str):
    """Show salary progression across experience levels."""
    args = parse_args(args_str)
    if args is None:
        return

    city = args.city or state.city
    category = args.category or state.category
    workplace = args.workplace or state.workplace
    emp_type = args.emp_type

    if not city:
        console.print("  [error]Specify city, e.g.: /progression Krak\u00f3w python b2b[/]")
        return
    if not category:
        console.print("  [error]Specify category, e.g.: /progression Krak\u00f3w python b2b[/]")
        return

    if args.experience:
        console.print("  [warn]Experience level ignored \u2014 /progression tests all levels[/]")

    filters = [city, category]
    if emp_type:
        filters.append(emp_type)
    if workplace:
        filters.append(workplace)
    console.print()
    filter_label = " [dim]·[/] ".join(f"[bold]{f}[/]" for f in filters)
    console.rule(f"[bold {C_CYAN}]Salary Progression[/]", style=C_BORDER)
    console.print(f"  {filter_label}")
    console.print()

    group_data = scrape_groups(
        scrapper.EXPERIENCE_LEVELS,
        build_params_fn=lambda level: (city, category, level, workplace),
        label_fn=lambda v: v.replace("_", " ").title(),
    )
    if group_data is None:
        return

    rows = []
    prev_mid = None
    for level in scrapper.EXPERIENCE_LEVELS:
        offers = group_data[level]
        salaries = analyzer.extract_salaries(offers, emp_type)
        stats = SalaryStats.compute(salaries)
        label = level.replace("_", " ").title()
        if not stats:
            rows.append((label, len(offers), 0, None, None, None, None))
            continue
        delta = stats.median_mid - prev_mid if prev_mid is not None else None
        rows.append((label, len(offers), stats.count, stats.median_low, stats.median_high, stats.median_mid, delta))
        prev_mid = stats.median_mid

    if all(row[3] is None for row in rows):
        console.print("  [warn]No salary data for any experience level[/]")
        return

    type_label = f" / {emp_type.upper()}" if emp_type else ""
    table = make_table(f"Salary Progression \u2014 {city} / {category}{type_label}")
    table.add_column("Level")
    table.add_column("Offers", justify="right", style="muted")
    table.add_column("With salary", justify="right", style="muted")
    table.add_column("Median From", justify="right")
    table.add_column("Median Mid", justify="right")
    table.add_column("Median To", justify="right")
    table.add_column("Delta", justify="right")

    for label, total, with_sal, med_lo, med_hi, med_mid, delta in rows:
        if med_mid is None:
            table.add_row(label, str(total), "0", "\u2014", "\u2014", "\u2014", "")
        else:
            delta_str = fmt_delta(delta) if delta is not None else "[dim]\u2014[/]"
            table.add_row(
                label, str(total), str(with_sal),
                fmt_salary(med_lo), fmt_salary(med_mid), fmt_salary(med_hi),
                delta_str,
            )

    console.print()
    console.print(table)

    chart_items = [(label, med_mid) for label, _, _, _, _, med_mid, _ in rows if med_mid is not None]
    print_bar_chart(chart_items)
    console.print()
    print_hint("/compare", "/analyze", desc="to dig deeper")
    console.print()


def cmd_compare(args_str: str):
    """Compare salaries across cities, categories, or employment types."""
    result = parse_compare_args(args_str)
    if result is None:
        return

    axis_name, axis_values, filters = result

    need_city = axis_name != "city"
    need_category = axis_name != "category"

    if need_city and not filters.city and not state.city:
        console.print("  [error]Specify city, e.g.: /compare python java Krak\u00f3w senior b2b[/]")
        return
    if need_category and not filters.category and not state.category:
        console.print("  [error]Specify category, e.g.: /compare Krak\u00f3w Warszawa python senior b2b[/]")
        return

    base_city = filters.city or state.city
    base_category = filters.category or state.category

    filter_parts = []
    if base_city and axis_name != "city":
        filter_parts.append(base_city)
    if base_category and axis_name != "category":
        filter_parts.append(base_category)
    if filters.experience and axis_name != "experience":
        filter_parts.append(filters.experience)
    if filters.emp_type and axis_name != "employment":
        filter_parts.append(filters.emp_type)
    if filters.workplace and axis_name != "workplace":
        filter_parts.append(filters.workplace)

    axis_label = axis_name.replace("employment", "type")
    console.print()
    values_str = f" [{C_BORDER}]vs[/] ".join(f"[bold]{v}[/]" for v in axis_values)
    console.rule(f"[bold {C_CYAN}]Compare by {axis_label}[/]", style=C_BORDER)
    console.print(f"  {values_str}")
    if filter_parts:
        filter_label = " [dim]·[/] ".join(f"[bold]{f}[/]" for f in filter_parts)
        console.print(f"  [dim]Filters:[/] {filter_label}")
    console.print()

    def build_params(val):
        return (
            val if axis_name == "city" else base_city,
            val if axis_name == "category" else base_category,
            val if axis_name == "experience" else filters.experience,
            val if axis_name == "workplace" else filters.workplace,
        )

    group_data = scrape_groups(
        axis_values,
        build_params_fn=build_params,
        label_fn=lambda v: v.replace("_", " ").title() if axis_name == "experience" else v,
    )
    if group_data is None:
        return

    emp_type = filters.emp_type
    rows = []
    for val in axis_values:
        offers = group_data[val]
        salaries = analyzer.extract_salaries(offers, emp_type)
        stats = SalaryStats.compute(salaries)
        if not stats:
            rows.append((val, len(offers), 0, None, None, None))
            continue
        rows.append((val, len(offers), stats.count, stats.median_low, stats.median_high, stats.median_mid))

    if all(row[3] is None for row in rows):
        console.print("  [warn]No salary data for any group[/]")
        return

    type_label = f" / {emp_type.upper()}" if emp_type else ""
    title = f"Compare by {axis_label}{type_label}"
    if filter_parts:
        title += f" \u2014 {' / '.join(filter_parts)}"

    table = make_table(title)
    table.add_column(axis_label.title())
    table.add_column("Offers", justify="right", style="muted")
    table.add_column("With salary", justify="right", style="muted")
    table.add_column("Median From", justify="right")
    table.add_column("Median Mid", justify="right")
    table.add_column("Median To", justify="right")

    for val, total, with_sal, med_lo, med_hi, med_mid in rows:
        label = val.replace("_", " ").title() if axis_name == "experience" else val
        if med_mid is None:
            table.add_row(label, str(total), "0", "\u2014", "\u2014", "\u2014")
        else:
            table.add_row(
                label, str(total), str(with_sal),
                fmt_salary(med_lo), fmt_salary(med_mid), fmt_salary(med_hi),
            )

    console.print()
    console.print(table)

    chart_items = [
        (val.replace("_", " ").title() if axis_name == "experience" else val, med_mid)
        for val, _, _, _, _, med_mid in rows
        if med_mid is not None
    ]
    print_bar_chart(chart_items)
    console.print()
    print_hint("/analyze", "/show <company>", desc="to dig deeper")
    console.print()


# ---- Data browsing commands ----


def cmd_recent(args_str: str):
    """Show recently published offers."""
    # Extract days argument (bare number) before standard parsing
    parts = args_str.split() if args_str else []
    days = 3
    remaining = []
    for p in parts:
        if p.isdigit():
            days = int(p)
        else:
            remaining.append(p)

    if days < 1:
        days = 1

    args = parse_args(" ".join(remaining))
    if args is None or not ensure_data(args):
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    recent = []
    for o in state.offers:
        pub = o.get("last_published_at") or o.get("published_at")
        if not pub:
            continue
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt >= cutoff:
                recent.append((dt, o))
        except (ValueError, TypeError):
            continue

    if not recent:
        console.print(f"  [warn]No offers published in the last {days} day(s)[/]")
        return

    recent.sort(key=lambda x: x[0], reverse=True)
    total = len(state.offers)

    # Per-day distribution
    day_counts: dict[str, int] = {}
    for dt, _ in recent:
        label = dt.strftime("%b %d")
        day_counts[label] = day_counts.get(label, 0) + 1
    chart_items = list(day_counts.items())

    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("k", style="dim")
    summary.add_column("v", style="bold")
    summary.add_row("Period", f"last {days} day(s)")
    summary.add_row("Recent offers", f"{len(recent)} of {total}")

    console.print()
    console.print(make_panel(summary, "Recent Offers", icon="\u25cf"))

    if len(chart_items) > 1:
        print_bar_chart(chart_items, fmt_fn=lambda v: f"{int(v)} offers")

    console.print()

    # Offer table
    table = make_table(f"Offers from last {days} day(s)")
    table.add_column("Age", no_wrap=True)
    table.add_column("Company", max_width=25)
    table.add_column("Title", max_width=35)
    table.add_column("Level")
    table.add_column("From/mo", justify="right")
    table.add_column("To/mo", justify="right")
    table.add_column("Type")
    table.add_column("Link", style="dim", no_wrap=True)

    for dt, o in recent:
        age = now - dt
        total_secs = age.total_seconds()
        if total_secs < 3600:
            time_str = f"[bold {C_GREEN}]{int(total_secs / 60)}m ago[/]"
        elif total_secs < 43200:
            time_str = f"[{C_CYAN}]{int(total_secs / 3600)}h ago[/]"
        elif total_secs < 86400:
            time_str = f"[{C_ORANGE}]{int(total_secs / 3600)}h ago[/]"
        else:
            time_str = f"[dim]{age.days}d ago[/]"

        ets = o.get("employment_types", [])
        sal_from_str = "[dim]-[/]"
        sal_to_str = "[dim]-[/]"
        type_str = ""

        pln_entries = [
            et for et in ets
            if (et.get("currency") or "").upper() == "PLN"
               and et.get("salary_from") is not None
        ]
        if pln_entries:
            et = pln_entries[0]
            sal_from_str = fmt_salary(analyzer.normalize_monthly(et["salary_from"]))
            sal_to_str = fmt_salary(analyzer.normalize_monthly(et["salary_to"]))
            type_str = et.get("type", "")
        else:
            types = "/".join(dict.fromkeys(
                filter(None, (et.get("type") for et in ets))
            ))
            type_str = types or "-"

        table.add_row(
            time_str,
            o.get("company_name", ""),
            o.get("title", ""),
            fmt_tag(o.get("experience_level", "")),
            sal_from_str,
            sal_to_str,
            fmt_tag(type_str),
            o.get("url", ""),
        )

    table.caption = f"{len(recent)} offers \u00b7 last {days} day(s)"
    console.print(table)
    console.print()
    print_hint("/show <company>", "/analyze", desc="to dig deeper")
    console.print()


def cmd_companies():
    """List companies in loaded data, sorted by number of offers."""
    if not require_data():
        return

    counts = Counter(o.get("company_name", "?") for o in state.offers)

    table = make_table(f"Companies ({len(counts)})")
    table.add_column("#", justify="right", style="muted")
    table.add_column("Company")
    table.add_column("Offers", justify="right", style="accent")

    for i, (company, count) in enumerate(counts.most_common(), 1):
        table.add_row(str(i), company, str(count))

    console.print()
    console.print(table)
    console.print()
    print_hint("/show <company>", desc="to see offer details")
    console.print()


def cmd_show(args_str: str):
    """Show offers from a specific company."""
    if not require_data():
        return

    query = args_str.strip().lower() if args_str else ""
    if not query:
        console.print("  [error]Specify company name: /show Revolut[/]")
        return

    # Tiered matching: exact -> startswith -> substring
    matches = [o for o in state.offers if o.get("company_name", "").lower() == query]
    if not matches:
        matches = [o for o in state.offers if o.get("company_name", "").lower().startswith(query)]
    if not matches:
        matches = [o for o in state.offers if query in o.get("company_name", "").lower()]

    if not matches:
        console.print(f'  [warn]No offers found for "{args_str.strip()}"[/]')
        return

    # Compute medians per employment type for delta columns
    medians = {}
    for et_type in scrapper.EMPLOYMENT_TYPES:
        salaries = analyzer.extract_salaries(state.offers, et_type)
        if salaries:
            lows = sorted(lo for lo, _, _ in salaries)
            highs = sorted(hi for _, hi, _ in salaries)
            medians[et_type] = (statistics.median(lows), statistics.median(highs))

    table = make_table(f"{matches[0]['company_name']} \u2014 {len(matches)} offers")
    table.add_column("Title")
    table.add_column("Level")
    table.add_column("City")
    table.add_column("Workplace")
    table.add_column("From/mo", justify="right")
    table.add_column("vs median", justify="right")
    table.add_column("To/mo", justify="right")
    table.add_column("vs median", justify="right")
    table.add_column("Type")
    table.add_column("Link", style="dim", no_wrap=True)

    for o in matches:
        ets = o.get("employment_types", [])
        pln_by_type = {
            et.get("type"): et for et in ets
            if (et.get("currency") or "").upper() == "PLN" and et.get("salary_from") is not None
        }
        url = o.get("url", "")
        if pln_by_type:
            for et_type, et in pln_by_type.items():
                sal_from = analyzer.normalize_monthly(et["salary_from"])
                sal_to = analyzer.normalize_monthly(et["salary_to"])
                delta_from = ""
                delta_to = ""
                if et_type in medians:
                    med_lo, med_hi = medians[et_type]
                    delta_from = fmt_delta(sal_from - med_lo)
                    delta_to = fmt_delta(sal_to - med_hi)
                table.add_row(
                    o["title"], fmt_tag(o.get("experience_level", "")),
                    o.get("city", ""), fmt_tag(o.get("workplace_type", "")),
                    fmt_salary(sal_from), delta_from,
                    fmt_salary(sal_to), delta_to,
                    fmt_tag(et_type or ""),
                    url,
                )
        else:
            types = "/".join(dict.fromkeys(filter(None, (et.get("type") for et in ets))))
            table.add_row(
                o["title"], fmt_tag(o.get("experience_level", "")),
                o.get("city", ""), fmt_tag(o.get("workplace_type", "")),
                "[dim]-[/]", "", "[dim]-[/]", "",
                fmt_tag(types or "-"),
                url,
            )

    console.print()
    console.print(table)
    console.print()


# ---- Internal helpers ----


def _print_top_for_type(salaries, pct: int, label: str):
    """Print top-companies tables for a single employment type."""
    midpoints = sorted(analyzer.midpoint(lo, hi) for lo, hi, _ in salaries)
    if len(midpoints) < 10:
        console.print(f"  [muted]{label}: not enough data[/]")
        return

    threshold = analyzer.percentile(midpoints, pct)
    above = [(lo, hi, o) for lo, hi, o in salaries if analyzer.midpoint(lo, hi) > threshold]
    above.sort(key=lambda x: analyzer.midpoint(x[0], x[1]), reverse=True)

    if not above:
        console.print(f"  [muted]{label}: no offers > P{pct}[/]")
        return

    company_counts = Counter(o["company_name"] for _, _, o in above)

    summary = make_table(f"Companies > P{pct} ({fmt_salary(threshold)}) \u2014 {label}")
    summary.add_column("Company")
    summary.add_column("Offers", justify="right", style="accent")
    summary.add_column("Min", justify="right")
    summary.add_column("Max", justify="right")

    for company, count in company_counts.most_common():
        mids = [analyzer.midpoint(lo, hi) for lo, hi, o in above if o["company_name"] == company]
        summary.add_row(company, str(count), fmt_salary(min(mids)), fmt_salary(max(mids)))

    console.print()
    console.print(summary)

    detail = make_table(f"Offer details > P{pct} \u2014 {label}")
    detail.add_column("Mid", justify="right")
    detail.add_column("From", justify="right")
    detail.add_column("To", justify="right")
    detail.add_column("Company")
    detail.add_column("Title")

    for lo, hi, offer in above:
        mid = analyzer.midpoint(lo, hi)
        detail.add_row(
            fmt_salary(mid), fmt_salary(lo), fmt_salary(hi),
            offer["company_name"], offer["title"],
        )

    detail.caption = f"{len(above)} offers above P{pct} threshold"
    console.print()
    console.print(detail)
