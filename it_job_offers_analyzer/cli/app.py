"""Main REPL loop and command dispatch."""

import os
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from rich.panel import Panel
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
from .display import console

# ---- Command registry ----

COMMAND_REGISTRY: dict[str, tuple] = {
    "/help":        (commands.cmd_help, False),
    "/status":      (commands.cmd_status, False),
    "/clear":       (commands.cmd_clear, False),
    "/companies":   (commands.cmd_companies, False),
    "/analyze":     (commands.cmd_analyze, True),
    "/top":         (commands.cmd_top, True),
    "/outliers":    (commands.cmd_outliers, True),
    "/benefits":    (commands.cmd_benefits, True),
    "/show":        (commands.cmd_show, True),
    "/recent":      (commands.cmd_recent, True),
    "/progression": (commands.cmd_progression, True),
    "/compare":     (commands.cmd_compare, True),
}


# ---- Welcome screen ----


def show_welcome():
    """Show welcome screen with quick-start commands."""
    console.print(BANNER, highlight=False)

    quick = Table(show_header=False, box=None, padding=(0, 2))
    quick.add_column("cmd", style="bold cyan", min_width=16)
    quick.add_column("desc", style="dim")

    for cmd in (CMD_ANALYZE, CMD_TOP, CMD_RECENT, CMD_PROGRESSION, CMD_COMPARE, CMD_BENEFITS, CMD_HELP):
        quick.add_row(cmd, COMMAND_DESCRIPTIONS[cmd])

    console.print(Panel(
        quick,
        title="[bold]Quick start[/]",
        subtitle="[dim]Tab for auto-complete \u00b7 ESC to cancel[/]",
        border_style="dim",
        padding=(1, 2),
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


# ---- Entry point ----


def main():
    prompt_style = PTStyle.from_dict({"prompt": "ansicyan bold"})

    show_welcome()

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
