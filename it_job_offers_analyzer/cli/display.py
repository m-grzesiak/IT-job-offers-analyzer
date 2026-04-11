"""Rich console, theme, and shared display builders."""

import statistics
from dataclasses import dataclass

import rich.box as box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from .. import analyzer

# ---- Modern color palette (Dracula-inspired) ----

C_PURPLE = "#bd93f9"
C_CYAN = "#8be9fd"
C_GREEN = "#50fa7b"
C_PINK = "#ff79c6"
C_ORANGE = "#ffb86c"
C_RED = "#ff5555"
C_FG = "#f8f8f2"
C_BORDER = "#6272a4"
C_BG = "#44475a"
S_TITLE = f"bold {C_PURPLE}"

THEME = Theme({
    "info": "dim cyan",
    "warn": C_ORANGE,
    "error": f"bold {C_RED}",
    "success": f"bold {C_GREEN}",
    "accent": f"bold {C_CYAN}",
    "muted": "dim",
    "salary": C_FG,
    "header": S_TITLE,
    "highlight": C_PINK,
    "label": C_CYAN,
})

console = Console(theme=THEME)


# ---- Component factories ----


def make_table(title: str = "", **kwargs) -> Table:
    """Create a table with standard modern styling (rounded, purple title, gray border, zebra stripes)."""
    defaults = {"box": box.ROUNDED, "border_style": C_BORDER, "header_style": f"bold {C_CYAN}",
                "caption_style": C_BORDER}
    if title:
        defaults["title"] = title
        defaults["title_style"] = S_TITLE
    defaults.update(kwargs)
    return Table(**defaults)


def make_panel(content, title: str = "", icon: str = "", **kwargs) -> Panel:
    """Create a panel with standard modern styling (rounded, purple border)."""
    defaults: dict = {"box": box.ROUNDED, "border_style": C_PURPLE, "padding": (1, 2)}
    label = f"{icon} {title}" if icon else title
    if label:
        defaults["title"] = f"[{S_TITLE}] {label} [/]"
    defaults.update(kwargs)
    return Panel(content, **defaults)


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
    """Format a salary delta with color and trend arrow."""
    if delta > 0:
        return f"[{C_GREEN}]\u25b2 +{delta:,.0f} PLN[/]".replace(",", " ")
    if delta < 0:
        return f"[{C_RED}]\u25bc {delta:,.0f} PLN[/]".replace(",", " ")
    return f"[dim]\u25cf 0 PLN[/]"


# ---- Tags / pills ----

_TAG_COLORS = {
    "b2b": C_CYAN,
    "permanent": C_GREEN,
    "mandate": C_ORANGE,
    "internship": C_PINK,
    "remote": C_PURPLE,
    "hybrid": C_ORANGE,
    "office": C_BORDER,
    "junior": C_GREEN,
    "mid": C_CYAN,
    "senior": C_ORANGE,
    "c_level": C_PINK,
}


def print_hint(*commands: str, desc: str = ""):
    """Print a 'Try: ...' footer with consistently styled commands.

    Usage:
        print_hint("/top >P75", "/outliers", "/show <company>")
        print_hint("/show <company>", desc="to see all offers for a given company")
    """
    parts = f" [muted]\u00b7[/] ".join(f"[accent]{cmd}[/]" for cmd in commands)
    if desc:
        console.print(f"  [muted]Try:[/] {parts} [muted]{desc}[/]")
    else:
        console.print(f"  [muted]Try:[/] {parts}")


def fmt_tag(text: str) -> str:
    """Format a value as a colored pill/badge."""
    if not text or text == "-":
        return f"[dim]{text or '-'}[/]"
    color = _TAG_COLORS.get(text.lower(), C_BORDER)
    return f"[{color}]{text}[/]"


# ---- Gradient bar visualization ----

_BAR_GRADIENT = [C_GREEN, C_CYAN, C_PURPLE, C_PINK]


def gradient_bar(ratio: float, width: int = 20, char: str = "\u2501", empty_char: str = "\u2500") -> str:
    """Create a gradient-colored bar (green -> cyan -> purple -> pink)."""
    filled = int(ratio * width)
    empty = width - filled
    if filled == 0:
        return f"[{C_BG}]{empty_char * width}[/]"

    # Group consecutive same-color characters for efficiency
    segments: list[str] = []
    prev_color = None
    count = 0
    for i in range(filled):
        color_idx = min(int(i / width * len(_BAR_GRADIENT)), len(_BAR_GRADIENT) - 1)
        color = _BAR_GRADIENT[color_idx]
        if color == prev_color:
            count += 1
        else:
            if prev_color is not None:
                segments.append(f"[{prev_color}]{char * count}[/]")
            prev_color = color
            count = 1
    if prev_color is not None:
        segments.append(f"[{prev_color}]{char * count}[/]")

    if empty > 0:
        segments.append(f"[{C_BG}]{empty_char * empty}[/]")

    return "".join(segments)


# ---- Table builders ----


def make_summary_table(stats: SalaryStats, total_offers: int) -> Table:
    """Build a Rich table with salary analysis summary."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style=C_FG)
    table.add_column("value", style="bold white", justify="right")

    table.add_row("Total offers", str(total_offers))
    table.add_row("With salary", str(stats.count))
    table.add_row("Without salary", str(total_offers - stats.count))
    table.add_row("", "")
    table.add_row("Median \u2014 lower", fmt_salary(stats.median_low))
    table.add_row("Median \u2014 upper", fmt_salary(stats.median_high))
    table.add_row("[bold]Median \u2014 mid[/]", f"[bold {C_PINK}]{fmt_salary(stats.median_mid)}[/]")

    return table


def make_percentile_table(midpoints: list[float], title: str = "Percentiles (mid-range)") -> Table:
    """Build a Rich table with percentile data and visual bars."""
    table = make_table(title, row_styles=None)
    table.add_column("Percentile", justify="right", style="accent")
    table.add_column("Amount", justify="right")
    table.add_column("Offers \u2264", justify="right")
    table.add_column("Scale", min_width=25)

    max_val = max(midpoints)
    for p in analyzer.PERCENTILES:
        val = analyzer.percentile(midpoints, p)
        count = sum(1 for m in midpoints if m <= val)
        bar_ratio = val / max_val if max_val else 0
        # Highlight the median (P50) row
        style = f"bold on {C_BG}" if p == 50 else None
        table.add_row(f"P{p}", fmt_salary(val), str(count), gradient_bar(bar_ratio, 22), style=style)

    return table


def make_distribution_table(midpoints: list[float], title: str = "Salary Distribution") -> Table:
    """Build salary distribution table with brackets and visual bars."""
    pvals = [analyzer.percentile(midpoints, p) for p in analyzer.PERCENTILES]

    brackets = [(0, pvals[0], f"< P{analyzer.PERCENTILES[0]}")]
    for i in range(1, len(pvals)):
        brackets.append((pvals[i - 1], pvals[i], f"P{analyzer.PERCENTILES[i - 1]}\u2013P{analyzer.PERCENTILES[i]}"))
    brackets.append((pvals[-1], float("inf"), f"> P{analyzer.PERCENTILES[-1]}"))

    table = make_table(title, row_styles=None)
    table.add_column("Bracket", justify="right", style="accent")
    table.add_column("Range", justify="right")
    table.add_column("Offers", justify="right")
    table.add_column("%", justify="right")
    table.add_column("Distribution", min_width=25)

    total = len(midpoints)
    for lo, hi, label in brackets:
        count = sum(1 for m in midpoints if lo < m <= hi) if lo > 0 else sum(1 for m in midpoints if m <= hi)
        pct = count / total * 100 if total else 0

        hi_str = fmt_salary(hi) if hi != float("inf") else "\u221e"
        range_str = f"{fmt_salary(lo)} \u2013 {hi_str}"

        color = C_GREEN if pct > 20 else C_CYAN if pct > 10 else C_BORDER
        bar_len = int(pct / 100 * 25)
        bar = f"[{color}]{'\u2588' * bar_len}[/]" if bar_len else ""
        table.add_row(label, range_str, str(count), f"{pct:.1f}%", bar)

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
        ratio = value / max_val if max_val else 0
        bar = gradient_bar(ratio, bar_width, char="\u2588", empty_char=" ")
        console.print(f"  {label:>{max_label}}  {bar} [bold]{fmt_fn(value)}[/]")
