"""Main REPL loop and command dispatch."""

import json
import os
import threading
import time
import urllib.request
from importlib.metadata import version as pkg_version

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from rich.table import Table

from . import commands
from .cancel import CancellableOperation, CancelledError
from .completer import bindings, completer
from .constants import (
    BANNER,
    CMD_ANALYZE,
    CMD_BENEFITS,
    CMD_COMPARE,
    CMD_HELP,
    CMD_PROGRESSION,
    CMD_QUIT,
    CMD_RECENT,
    CMD_TOP,
    COMMAND_DESCRIPTIONS,
    HISTORY_PATH,
)
from .display import C_BORDER, C_CYAN, C_PURPLE, console, make_panel

# ---- Command registry ----

COMMAND_REGISTRY: dict[str, tuple] = {
    "/help": (commands.cmd_help, False),
    "/status": (commands.cmd_status, False),
    "/clear": (commands.cmd_clear, False),
    "/companies": (commands.cmd_companies, False),
    "/analyze": (commands.cmd_analyze, True),
    "/top": (commands.cmd_top, True),
    "/outliers": (commands.cmd_outliers, True),
    "/benefits": (commands.cmd_benefits, True),
    "/show": (commands.cmd_show, True),
    "/recent": (commands.cmd_recent, True),
    "/progression": (commands.cmd_progression, True),
    "/compare": (commands.cmd_compare, True),
}


# ---- Welcome screen ----


def show_welcome(animate: bool = True):
    """Show welcome screen with quick-start commands."""
    if animate:
        for line in BANNER.split("\n"):
            if line.startswith("[/]"):
                line = line[3:]
            console.print(line, highlight=False)
            time.sleep(0.05)
    else:
        console.print(BANNER, highlight=False)

    quick = Table(show_header=False, box=None, padding=(0, 2))
    quick.add_column("cmd", style=f"bold {C_CYAN}", min_width=16)
    quick.add_column("desc", style="dim")

    for cmd in (CMD_ANALYZE, CMD_TOP, CMD_RECENT, CMD_PROGRESSION, CMD_COMPARE, CMD_BENEFITS, CMD_HELP):
        quick.add_row(f"  {cmd}", COMMAND_DESCRIPTIONS[cmd])

    console.print(make_panel(
        quick,
        "Quick start", icon="\u2726",
        subtitle=f"[{C_BORDER}] Tab \u00b7 auto-complete  \u2502  ESC \u00b7 cancel [/]",
        border_style=C_BORDER,
        width=76,
    ))
    console.print()
    console.print("  [muted]Try:[/] [accent]/analyze Krak\u00f3w python senior b2b[/]")
    console.print()


# ---- Dispatch ----


def dispatch(user_input: str) -> bool:
    """Route user input to the right command. Returns False to exit."""
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

    entry = COMMAND_REGISTRY.get(cmd)
    if not entry:
        console.print(f"  [error]Unknown command: {cmd}[/]")
        console.print("  [muted]Type /help to see available commands[/]")
        return True

    handler, takes_args = entry
    with CancellableOperation():
        try:
            handler(args_str) if takes_args else handler()
        except CancelledError:
            console.print("\n  [warn]Operation cancelled[/]")

    return True


# ---- Update check ----


def _check_for_update() -> str | None:
    """Check PyPI for a newer version. Returns new version string or None."""
    try:
        current = pkg_version("itjobs")
        req = urllib.request.Request(
            "https://pypi.org/pypi/itjobs/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest = data["info"]["version"]
        cur = tuple(int(x) for x in current.split("."))
        lat = tuple(int(x) for x in latest.split("."))
        if lat > cur:
            return latest
    except Exception:
        pass
    return None


# ---- Entry point ----


def main():
    prompt_style = PTStyle.from_dict({
        "prompt": f"fg:{C_PURPLE} bold",
        # Completion menu
        "completion-menu.completion": "bg:#282a36 fg:#f8f8f2",
        "completion-menu.completion.current": f"bg:#44475a fg:#f8f8f2 bold",
        "completion-menu.meta.completion": f"bg:#282a36 fg:{C_BORDER}",
        "completion-menu.meta.completion.current": f"bg:#44475a fg:{C_CYAN}",
        # Scrollbar
        "scrollbar.background": "bg:#282a36",
        "scrollbar.button": f"bg:{C_BORDER}",
        # Auto-suggest (history hints)
        "auto-suggest": f"fg:{C_BORDER}",
    })

    show_welcome()

    # Non-blocking update check — result shown before first prompt
    update_result: list[str | None] = [None]

    def _bg_check():
        update_result[0] = _check_for_update()

    update_thread = threading.Thread(target=_bg_check, daemon=True)
    update_thread.start()

    if os.path.exists(HISTORY_PATH):
        age_days = (time.time() - os.path.getmtime(HISTORY_PATH)) / 86400
        if age_days > 30:
            os.remove(HISTORY_PATH)

    session = PromptSession(
        history=FileHistory(HISTORY_PATH),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        key_bindings=bindings,
    )

    update_thread.join(timeout=2)
    if update_result[0]:
        console.print(
            f"  [#ffb86c]\u25b2 New version available: {update_result[0]}[/]"
            f"  [muted]\u2014  pip install --upgrade itjobs[/]"
        )
        console.print()

    while True:
        try:
            user_input = session.prompt(
                [("class:prompt", "\u276f ")],
                style=prompt_style,
            )
            if not dispatch(user_input):
                console.print("  [muted]Goodbye![/]")
                break
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [muted]Goodbye![/]")
            break
