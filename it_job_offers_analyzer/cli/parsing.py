"""Argument parsing for CLI commands."""

from .constants import CITIES
from .display import console
from .state import FilterArgs
from .. import scrapper


def parse_args(args_str: str) -> FilterArgs | None:
    """Parse mixed scrape filters + analysis flags from command arguments.

    Returns FilterArgs on success, None on parse error (unknown arguments).
    """
    parts = args_str.split() if args_str else []

    city = None
    category = None
    experience = None
    workplace = None
    emp_type = None
    top_percentile = None
    unknown = []

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
                unknown.append(p)

    if unknown:
        _report_unknown(unknown)
        return None

    return FilterArgs(
        city=city, category=category, experience=experience,
        workplace=workplace, emp_type=emp_type, top_percentile=top_percentile,
    )


def parse_compare_args(args_str: str) -> tuple[str, list[str], FilterArgs] | None:
    """Parse /compare arguments: detect the comparison axis and common filters.

    Returns (axis_name, axis_values, common_filters) or None on error.
    axis_name is one of: "city", "category", "experience", "employment", "workplace".
    """
    parts = args_str.split() if args_str else []
    if not parts:
        console.print("  [error]Usage: /compare <values...> [filters...][/]")
        console.print("  [muted]e.g. /compare Krak\u00f3w Warszawa python senior b2b[/]")
        console.print("  [muted]     /compare Krak\u00f3w python java senior[/]")
        return None

    cities, categories, experiences, employments, workplaces, unknown = (
        [], [], [], [], [], [],
    )

    for p in parts:
        matched_city = next((c for c in CITIES if c.lower() == p.lower()), None)
        if matched_city:
            cities.append(matched_city)
        elif p in scrapper.CATEGORIES:
            categories.append(p)
        elif p in scrapper.EXPERIENCE_LEVELS:
            experiences.append(p)
        elif p in scrapper.EMPLOYMENT_TYPES:
            employments.append(p)
        elif p in scrapper.WORKPLACE_TYPES:
            workplaces.append(p)
        else:
            unknown.append(p)

    if unknown:
        for token in unknown:
            console.print(f'  [warn]Unknown argument: "{token}"[/]')
        return None

    # The group with multiple values is the comparison axis
    groups = [
        ("city", cities),
        ("category", categories),
        ("experience", experiences),
        ("employment", employments),
        ("workplace", workplaces),
    ]
    multi_groups = [(name, vals) for name, vals in groups if len(vals) > 1]

    if len(multi_groups) == 0:
        console.print("  [error]Provide multiple values for the axis you want to compare[/]")
        console.print("  [muted]e.g. /compare Krak\u00f3w Warszawa python senior b2b[/]")
        console.print("  [muted]     /compare Krak\u00f3w python java senior[/]")
        return None

    if len(multi_groups) > 1:
        names = [n for n, _ in multi_groups]
        console.print(f"  [error]Multiple comparison axes detected: {', '.join(names)}[/]")
        console.print("  [muted]Only one group can have multiple values[/]")
        return None

    axis_name, axis_values = multi_groups[0]

    # Single values become common filters
    filters = FilterArgs(
        city=cities[0] if len(cities) == 1 else None,
        category=categories[0] if len(categories) == 1 else None,
        experience=experiences[0] if len(experiences) == 1 else None,
        workplace=workplaces[0] if len(workplaces) == 1 else None,
        emp_type=employments[0] if len(employments) == 1 else None,
    )

    return axis_name, axis_values, filters


def _report_unknown(tokens: list[str]):
    """Report unrecognized tokens with did-you-mean suggestions."""
    all_known = (
            set(scrapper.CATEGORIES)
            | set(scrapper.EXPERIENCE_LEVELS)
            | set(scrapper.WORKPLACE_TYPES)
            | set(scrapper.EMPLOYMENT_TYPES)
            | {c.lower() for c in CITIES}
    )
    for token in tokens:
        console.print(f'  [warn]Unknown argument: "{token}"[/]')
        close = [k for k in all_known if k.startswith(token.lower())]
        if close:
            console.print(f"  [muted]Did you mean: {', '.join(close[:5])}?[/]")
