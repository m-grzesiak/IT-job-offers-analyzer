"""ESC-key cancellation for long-running operations."""

import select
import sys
import termios
import threading
import time
import tty

from rich.progress import Progress
from rich.text import Text


class CancelledError(Exception):
    """Raised when the user cancels an operation with ESC."""


_current_op: "CancellableOperation | None" = None


class CancellableOperation:
    """Context manager that listens for ESC key to cancel the current operation.

    Automatically registers/unregisters itself as the active operation on
    enter/exit, so callers don't need to manage the global manually.
    """

    def __init__(self):
        self._cancel_event = threading.Event()
        self._thread = None
        self._old_settings = None

    def __enter__(self):
        global _current_op
        _current_op = self
        try:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            self._thread = threading.Thread(target=self._listen, daemon=True)
            self._thread.start()
        except Exception:
            pass
        return self

    def __exit__(self, *args):
        global _current_op
        _current_op = None
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
                    if ch == "\x1b":
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


def cancel_aware_sleep(seconds: float):
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
