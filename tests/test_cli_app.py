"""Tests for it_job_offers_analyzer.cli.app — dispatch routing."""

from unittest.mock import MagicMock, patch

import pytest

from it_job_offers_analyzer.cli.app import dispatch
from it_job_offers_analyzer.cli.cancel import CancelledError


# Disable CancellableOperation for all dispatch tests (no terminal I/O).
@pytest.fixture(autouse=True)
def _no_cancel():
    mock_op = MagicMock()
    mock_op.__enter__ = MagicMock(return_value=mock_op)
    mock_op.__exit__ = MagicMock(return_value=False)
    with patch("it_job_offers_analyzer.cli.app.CancellableOperation", return_value=mock_op):
        yield mock_op


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_empty_input_returns_true(self, capture_console):
        assert dispatch("") is True

    def test_whitespace_returns_true(self, capture_console):
        assert dispatch("   ") is True

    def test_non_slash_input_shows_hint(self, capture_console):
        result = dispatch("hello world")
        assert result is True
        assert "/help" in capture_console.getvalue()

    def test_quit_returns_false(self, capture_console):
        assert dispatch("/quit") is False

    def test_unknown_command_shows_error(self, capture_console):
        result = dispatch("/nonexistent")
        assert result is True
        output = capture_console.getvalue()
        assert "Unknown command" in output

    @patch("it_job_offers_analyzer.cli.app.commands")
    def test_analyze_dispatches_correctly(self, mock_cmds, capture_console):
        mock_cmds.cmd_analyze = MagicMock()
        # Re-register for this test
        from it_job_offers_analyzer.cli.app import COMMAND_REGISTRY
        COMMAND_REGISTRY["/analyze"] = (mock_cmds.cmd_analyze, True)
        dispatch("/analyze Kraków python")
        mock_cmds.cmd_analyze.assert_called_once_with("Kraków python")

    @patch("it_job_offers_analyzer.cli.app.commands")
    def test_help_dispatches_without_args(self, mock_cmds, capture_console):
        mock_cmds.cmd_help = MagicMock()
        from it_job_offers_analyzer.cli.app import COMMAND_REGISTRY
        COMMAND_REGISTRY["/help"] = (mock_cmds.cmd_help, True)
        dispatch("/help")
        mock_cmds.cmd_help.assert_called_once_with("")

    def test_cancelled_error_caught(self, _no_cancel, capture_console):
        """CancelledError during command execution should be caught."""

        def raise_cancel(args):
            raise CancelledError()

        from it_job_offers_analyzer.cli.app import COMMAND_REGISTRY
        original = COMMAND_REGISTRY.get("/analyze")
        COMMAND_REGISTRY["/analyze"] = (raise_cancel, True)
        try:
            result = dispatch("/analyze test")
            assert result is True
            assert "cancelled" in capture_console.getvalue().lower()
        finally:
            if original:
                COMMAND_REGISTRY["/analyze"] = original

    def test_command_case_insensitive(self, capture_console):
        """Commands should be case-insensitive (/HELP -> /help)."""
        result = dispatch("/QUIT")
        assert result is False
