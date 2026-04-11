"""Rich console, theme, and shared display builders."""

import statistics
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

from .. import analyzer

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


# ---- Salary statistics view-model ----


@dataclass
class SalaryStats:
    """Pre-computed salary statistics for display.

    Eliminates the repeated lows/highs/mids/median computation that was
    duplicated across cmd_analyze, cmd_progression, cmd_compare, and cmd_show.
    """

    count: int
    median_low: float
    median_high: float
    median_mid: float
    midpoints: list[float]

    @classmethod
    def compute(cls, salaries: list[tuple[float, float, dict]]) -> "SalaryStats | None":
        """Compute stats from analyzer-produced salary tuples. Returns None if empty."""
        if not salaries:
            return None
        lows = sorted(lo for lo, _, _ in salaries)
        highs = sorted(hi for _, hi, _ in salaries)
        mids = sorted(analyzer.midpoint(lo, hi) for lo, hi, _ in salaries)
        return cls(
            count=len(salaries),
            median_low=statistics.median(lows),
            median_high=statistics.median(highs),
            median_mid=statistics.median(mids),
            midpoints=mids,
        )


# ---- Formatting helpers ----


def fmt_salary(val: float) -> str:
    """Format salary with Polish-style space separators."""
    return f"{val:,.0f} PLN".replace(",", " ")


def fmt_delta(delta: float) -> str:
    """Format a salary delta with color: green for positive, red for negative."""
    if delta > 0:
        return f"[green]+{delta:,.0f} PLN[/]".replace(",", " ")
    if delta < 0:
        return f"[red]{delta:,.0f} PLN[/]".replace(",", " ")
    return "[dim]0 PLN[/]"


# ---- Table builders ----


def make_summary_table(stats: SalaryStats, total_offers: int) -> Table:
    """Build a Rich table with salary analysis summary."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="dim")
    table.add_column("value", style="bold white")

    table.add_row("Total offers", str(total_offers))
    table.add_row("With salary", str(stats.count))
    table.add_row("Without salary", str(total_offers - stats.count))
    table.add_row("", "")
    table.add_row("Median \u2014 lower", fmt_salary(stats.median_low))
    table.add_row("Median \u2014 upper", fmt_salary(stats.median_high))
    table.add_row("Median \u2014 mid", fmt_salary(stats.median_mid))

    return table


def make_percentile_table(midpoints: list[float], title: str = "Percentiles (mid-range)") -> Table:
    """Build a Rich table with percentile data and visual bars."""
    table = Table(
        title=title,
        title_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Percentile", justify="right", style="accent")
    table.add_column("Amount", justify="right", style="salary")
    table.add_column("Offers \u2264", justify="right", style="muted")
    table.add_column("", min_width=25)

    max_val = max(midpoints)
    for p in analyzer.PERCENTILES:
        val = analyzer.percentile(midpoints, p)
        count = sum(1 for m in midpoints if m <= val)
        bar_ratio = val / max_val if max_val else 0
        bar_len = int(bar_ratio * 20)
        bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
        table.add_row(f"P{p}", fmt_salary(val), str(count), f"[cyan]{bar}[/]")

    return table


def make_distribution_table(midpoints: list[float], title: str = "Salary Distribution") -> Table:
    """Build salary distribution table with brackets and visual bars."""
    pvals = [analyzer.percentile(midpoints, p) for p in analyzer.PERCENTILES]

    brackets = [(0, pvals[0], f"< P{analyzer.PERCENTILES[0]}")]
    for i in range(1, len(pvals)):
        brackets.append((pvals[i - 1], pvals[i], f"P{analyzer.PERCENTILES[i - 1]}\u2013P{analyzer.PERCENTILES[i]}"))
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
        bar = "\u2588" * bar_len

        hi_str = fmt_salary(hi) if hi != float("inf") else "\u221e"
        range_str = f"{fmt_salary(lo)} \u2013 {hi_str}"

        color = "green" if pct > 20 else "cyan" if pct > 10 else "dim"
        table.add_row(label, range_str, str(count), f"{pct:.1f}%", f"[{color}]{bar}[/]")

    return table


def print_bar_chart(items: list[tuple[str, float]], bar_width: int = 35, fmt_fn=None):
    """Print a horizontal bar chart of labeled values."""
    if not items:
        return
    if fmt_fn is None:
        fmt_fn = fmt_salary
    max_val = max(v for _, v in items)
    max_label = max(len(label) for label, _ in items)
    console.print()
    for label, value in items:
        bar_len = int(value / max_val * bar_width) if max_val else 0
        bar = "\u2588" * bar_len
        console.print(f"  {label:>{max_label}}  [cyan]{bar}[/] {fmt_fn(value)}")
