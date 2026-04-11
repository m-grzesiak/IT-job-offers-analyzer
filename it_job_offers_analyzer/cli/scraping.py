"""CLI-specific scraping orchestration with Rich progress bars."""

from collections.abc import Callable

from rich.progress import BarColumn, MofNCompleteColumn, SpinnerColumn, TextColumn
from rich.style import Style

from .cancel import CancellableProgress, CancelledError, cancel_aware_sleep, check_cancel
from .display import C_CYAN, C_GREEN, C_PINK, C_PURPLE, console
from .state import FilterArgs, state
from .. import scrapper

_PROGRESS_BAR = BarColumn(
    complete_style=Style(color=C_PURPLE),
    finished_style=Style(color=C_GREEN),
    pulse_style=Style(color=C_PINK),
)


def ensure_data(args: FilterArgs, need_details: bool = False) -> bool:
    """Ensure offers are loaded, scraping if necessary.

    Returns True when data is ready, False on failure.
    """
    if not state.needs_scrape(args, need_details):
        return True

    city = args.city or state.city
    category = args.category or state.category
    experience = args.experience or state.experience
    workplace = args.workplace or state.workplace

    if not city:
        console.print("  [error]Specify city, e.g.: /analyze Krak\u00f3w python senior b2b[/]")
        return False
    if not category:
        console.print("  [error]Specify category, e.g.: /analyze Krak\u00f3w python senior b2b[/]")
        return False

    return _scrape(city, category, experience, workplace, need_details)


def require_data() -> bool:
    """Check that offers are loaded. Prints an error and returns False if not."""
    if not state.offers:
        console.print("  [error]No data. Run /analyze first, e.g.: /analyze Krak\u00f3w python senior[/]")
        return False
    return True


def scrape_groups(
        group_values: list[str],
        build_params_fn: Callable[[str], tuple[str, str, str | None, str | None]],
        label_fn: Callable[[str], str] | None = None,
) -> dict[str, list[dict]] | None:
    """Scrape multiple groups with a shared progress display.

    Used by /progression (experience levels) and /compare (any axis).

    Args:
        group_values: Values to iterate over (e.g., experience levels, city names).
        build_params_fn: value -> (city, category, experience, workplace) tuple.
        label_fn: value -> display label. Defaults to value itself.

    Returns:
        Dict mapping each value to its list of offers, or None if cancelled.
    """
    if label_fn is None:
        label_fn = str

    result = {}
    try:
        with CancellableProgress(
                SpinnerColumn(style=C_CYAN),
                TextColumn("[progress.description]{task.description}"),
                _PROGRESS_BAR,
                MofNCompleteColumn(),
                console=console,
        ) as progress:
            for val in group_values:
                label = label_fn(val)
                task = progress.add_task(f"{label}...", total=None)
                city, category, experience, workplace = build_params_fn(val)
                offers = _scrape_single(city, category, experience, workplace, progress, task)
                result[val] = offers
                cancel_aware_sleep(0.3)
    except CancelledError:
        console.print("\n  [warn]Operation cancelled[/]")
        return None

    return result


# ---- Internal helpers ----


def _scrape(city, category, experience, workplace, fetch_details) -> bool:
    """Scrape offers with progress. Updates session state. Returns True on success."""
    filters = [city]
    if category:
        filters.append(category)
    if experience:
        filters.append(experience)
    if workplace:
        filters.append(workplace)
    filter_label = " · ".join(filters)

    console.print()
    try:
        params = scrapper.build_params(
            city=city, category=category, experience=experience, workplace=workplace,
        )

        with CancellableProgress(
                SpinnerColumn(style=C_CYAN),
                TextColumn("[progress.description]{task.description}"),
                _PROGRESS_BAR,
                MofNCompleteColumn(),
                console=console,
        ) as progress:
            task = progress.add_task(
                f"[bold {C_CYAN}]justjoin.it[/] [dim]›[/] {filter_label}",
                total=None,
            )

            all_offers = []
            for batch, total, is_last in scrapper.iter_pages(params):
                check_cancel()
                if progress.tasks[task].total is None:
                    progress.update(task, total=total)
                all_offers.extend(batch)
                progress.update(task, completed=len(all_offers))
                if is_last:
                    break
                cancel_aware_sleep(0.3)

            if fetch_details:
                detail_task = progress.add_task(
                    "Fetching descriptions...", total=len(all_offers),
                )
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
                    cancel_aware_sleep(0.15)
                state.offers = results
                state.has_details = True
            else:
                state.offers = [offer for _, offer in all_offers]
                state.has_details = False

        state.city = city
        state.category = category
        state.experience = experience
        state.workplace = workplace

        console.print()
        console.print(f"  [success]Fetched {len(state.offers)} offers[/]")
        console.print()
        return True

    except CancelledError:
        raise
    except Exception as e:
        console.print(f"  [error]Scraping error: {e}[/]")
        return False


def _scrape_single(city, category, experience, workplace, progress, task_id) -> list[dict]:
    """Scrape offers for a single filter combination, updating a shared progress task."""
    params = scrapper.build_params(
        city=city, category=category, experience=experience, workplace=workplace,
    )
    all_offers = []
    for batch, total, is_last in scrapper.iter_pages(params):
        check_cancel()
        if progress.tasks[task_id].total is None:
            progress.update(task_id, total=total)
        all_offers.extend(batch)
        progress.update(task_id, completed=len(all_offers))
        if is_last:
            break
        cancel_aware_sleep(0.3)
    return [offer for _, offer in all_offers]
