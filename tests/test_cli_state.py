"""Tests for it_job_offers_analyzer.cli.state — FilterArgs + SessionState."""

from it_job_offers_analyzer.cli.state import FilterArgs, SessionState


# ---------------------------------------------------------------------------
# FilterArgs
# ---------------------------------------------------------------------------


class TestFilterArgs:
    def test_defaults_all_none(self):
        args = FilterArgs()
        assert args.city is None
        assert args.category is None
        assert args.experience is None
        assert args.workplace is None
        assert args.emp_type is None
        assert args.top_percentile is None

    def test_construction_with_values(self):
        args = FilterArgs(city="Kraków", category="python", experience="senior")
        assert args.city == "Kraków"
        assert args.category == "python"
        assert args.experience == "senior"


# ---------------------------------------------------------------------------
# SessionState.needs_scrape
# ---------------------------------------------------------------------------


class TestNeedsScrape:
    def test_true_when_no_offers(self):
        state = SessionState()
        assert state.needs_scrape(FilterArgs(city="Kraków", category="python")) is True

    def test_true_when_city_changes(self):
        state = SessionState(offers=[{"x": 1}], city="Kraków", category="python")
        assert state.needs_scrape(FilterArgs(city="Warszawa")) is True

    def test_true_when_category_changes(self):
        state = SessionState(offers=[{"x": 1}], city="Kraków", category="python")
        assert state.needs_scrape(FilterArgs(category="java")) is True

    def test_true_when_experience_changes(self):
        state = SessionState(offers=[{"x": 1}], city="Kraków", experience="senior")
        assert state.needs_scrape(FilterArgs(experience="junior")) is True

    def test_true_when_workplace_changes(self):
        state = SessionState(offers=[{"x": 1}], workplace="remote")
        assert state.needs_scrape(FilterArgs(workplace="office")) is True

    def test_true_when_details_needed(self):
        state = SessionState(offers=[{"x": 1}], has_details=False)
        assert state.needs_scrape(FilterArgs(), need_details=True) is True

    def test_false_when_details_already_present(self):
        state = SessionState(offers=[{"x": 1}], has_details=True)
        assert state.needs_scrape(FilterArgs(), need_details=True) is False

    def test_false_when_cached_matches(self):
        state = SessionState(
            offers=[{"x": 1}], city="Kraków", category="python",
            experience="senior", workplace="remote",
        )
        args = FilterArgs(city="Kraków", category="python", experience="senior", workplace="remote")
        assert state.needs_scrape(args) is False

    def test_false_when_args_none_uses_cached(self):
        """None filter args mean 'use whatever is cached' — no rescrape."""
        state = SessionState(offers=[{"x": 1}], city="Kraków", category="python")
        assert state.needs_scrape(FilterArgs()) is False

    def test_false_partial_match(self):
        """Providing only city that matches cached city — no rescrape."""
        state = SessionState(offers=[{"x": 1}], city="Kraków", category="python")
        assert state.needs_scrape(FilterArgs(city="Kraków")) is False


# ---------------------------------------------------------------------------
# SessionState.reset
# ---------------------------------------------------------------------------


class TestSessionStateReset:
    def test_reset_clears_everything(self):
        state = SessionState(
            offers=[{"x": 1}], city="Kraków", category="python",
            experience="senior", workplace="remote", has_details=True,
        )
        state.reset()
        assert state.offers == []
        assert state.city is None
        assert state.category is None
        assert state.experience is None
        assert state.workplace is None
        assert state.has_details is False
