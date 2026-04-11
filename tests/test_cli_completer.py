"""Tests for it_job_offers_analyzer.cli.completer — SmartCompleter tab completion."""

import pytest
from prompt_toolkit.document import Document

from it_job_offers_analyzer.cli.completer import SmartCompleter
from it_job_offers_analyzer.cli.constants import COMMAND_STAGES


@pytest.fixture
def comp():
    return SmartCompleter()


def _get_completions(completer, text):
    """Helper: get completion texts for given input."""
    doc = Document(text, len(text))
    return [c.text for c in completer.get_completions(doc, None)]


# ---------------------------------------------------------------------------
# Command completion (stage 0)
# ---------------------------------------------------------------------------


class TestCommandCompletion:
    def test_empty_input_suggests_all_commands(self, comp):
        completions = _get_completions(comp, "")
        for cmd in COMMAND_STAGES:
            assert cmd in completions

    def test_partial_analyze(self, comp):
        completions = _get_completions(comp, "/ana")
        assert "/analyze" in completions

    def test_partial_top(self, comp):
        completions = _get_completions(comp, "/to")
        assert "/top" in completions

    def test_no_match(self, comp):
        completions = _get_completions(comp, "/zzz")
        assert completions == []


# ---------------------------------------------------------------------------
# Stage-by-stage completion for /analyze
# ---------------------------------------------------------------------------


class TestAnalyzeCompletion:
    def test_first_stage_cities(self, comp):
        completions = _get_completions(comp, "/analyze ")
        assert "Kraków" in completions
        assert "Warszawa" in completions

    def test_second_stage_categories(self, comp):
        completions = _get_completions(comp, "/analyze Kraków ")
        assert "python" in completions
        assert "java" in completions

    def test_third_stage_experience(self, comp):
        completions = _get_completions(comp, "/analyze Kraków python ")
        assert "senior" in completions
        assert "junior" in completions

    def test_partial_word_filters(self, comp):
        completions = _get_completions(comp, "/analyze Kraków pyt")
        assert "python" in completions
        assert "java" not in completions

    def test_used_values_not_re_suggested(self, comp):
        """Once a city is used, the city stage is skipped."""
        completions = _get_completions(comp, "/analyze Kraków python senior ")
        # City stage was used (Kraków), category (python), experience (senior)
        # Next should be employment type or workplace
        assert "Kraków" not in completions


# ---------------------------------------------------------------------------
# /show — company name completion
# ---------------------------------------------------------------------------


class TestShowCompletion:
    def test_completes_company_names(self, comp, clean_state, make_offer):
        clean_state.offers = [
            make_offer(company_name="Revolut"),
            make_offer(company_name="Allegro"),
        ]
        completions = _get_completions(comp, "/show ")
        assert "Revolut" in completions
        assert "Allegro" in completions

    def test_partial_company_name(self, comp, clean_state, make_offer):
        clean_state.offers = [
            make_offer(company_name="Revolut"),
            make_offer(company_name="Allegro"),
        ]
        completions = _get_completions(comp, "/show Rev")
        assert "Revolut" in completions
        assert "Allegro" not in completions

    def test_no_offers_no_completions(self, comp, clean_state):
        completions = _get_completions(comp, "/show ")
        assert completions == []


# ---------------------------------------------------------------------------
# /compare — any-stage mode
# ---------------------------------------------------------------------------


class TestCompareCompletion:
    def test_offers_all_groups(self, comp):
        completions = _get_completions(comp, "/compare ")
        # Should offer cities, categories, experience, employment, workplace
        assert "Kraków" in completions
        assert "python" in completions
        assert "senior" in completions
        assert "b2b" in completions
        assert "remote" in completions

    def test_allows_multiple_from_same_group(self, comp):
        completions = _get_completions(comp, "/compare Kraków ")
        # Kraków is used, but other cities should still be available
        assert "Warszawa" in completions

    def test_used_value_not_suggested(self, comp):
        completions = _get_completions(comp, "/compare Kraków ")
        assert "Kraków" not in completions
