"""Tab-completion and key bindings for the interactive prompt."""

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings

from .constants import CMD_COMPARE, CMD_SHOW, COMMAND_DESCRIPTIONS, COMMAND_STAGES
from .state import state


class SmartCompleter(Completer):
    """Context-aware completer that suggests parameters stage-by-stage."""

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        parts = text.split()

        # Stage 0: completing the command itself
        if not parts or (len(parts) == 1 and not text.endswith(" ")):
            prefix = parts[0] if parts else ""
            for cmd in sorted(COMMAND_STAGES):
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
            yield from self._complete_companies(text, parts)
            return

        stages = COMMAND_STAGES.get(cmd, [])
        if not stages:
            return

        used = set(parts[1:]) if text.endswith(" ") else set(parts[1:-1])
        current_word = "" if text.endswith(" ") else (parts[-1] if len(parts) > 1 else "")

        # /compare allows multiple values from any group (comparison axis)
        if cmd == CMD_COMPARE:
            yield from self._complete_any_stage(stages, used, current_word)
            return

        yield from self._complete_next_stage(stages, used, current_word)

    def _complete_companies(self, text: str, parts: list[str]):
        """Complete company names from loaded offers."""
        if not state.offers:
            return

        cmd_len = len(parts[0]) + 1
        after_cmd = text[cmd_len:] if len(text) > cmd_len else ""

        seen = set()
        for o in state.offers:
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

    def _complete_any_stage(self, stages, used, current_word):
        """Complete from any stage (for /compare which allows multiple values per group)."""
        for candidates, meta in stages:
            for c in candidates:
                if c in used:
                    continue
                if c.lower().startswith(current_word.lower()):
                    yield Completion(c, start_position=-len(current_word), display_meta=meta)

    def _complete_next_stage(self, stages, used, current_word):
        """Complete the next unfilled stage only."""
        for candidates, meta in stages:
            if any(u in candidates for u in used):
                continue
            for c in candidates:
                if c in used:
                    continue
                if c.lower().startswith(current_word.lower()):
                    yield Completion(c, start_position=-len(current_word), display_meta=meta)
            return


completer = SmartCompleter()

bindings = KeyBindings()


@bindings.add("enter", filter=has_completions)
def accept_completion(event):
    """Enter accepts the selected completion instead of submitting the line."""
    event.current_buffer.complete_state = None
