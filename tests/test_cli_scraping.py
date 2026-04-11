"""Tests for it_job_offers_analyzer.cli.scraping — mocked scraper integration."""

from unittest.mock import MagicMock, patch

import pytest

from it_job_offers_analyzer.cli.scraping import ensure_data, require_data, scrape_groups
from it_job_offers_analyzer.cli.state import FilterArgs


# All tests here need clean state and no real HTTP / terminal I/O.
# We mock the cancel infrastructure + scrapper module at the cli.scraping level.

@pytest.fixture(autouse=True)
def _no_cancel():
    """Disable cancellation infrastructure for all tests in this module."""
    mock_progress = MagicMock()
    mock_progress.__enter__ = MagicMock(return_value=mock_progress)
    mock_progress.__exit__ = MagicMock(return_value=False)
    mock_progress.add_task.return_value = 0

    # tasks[task_id].total needs to return None initially
    task_mock = MagicMock()
    task_mock.total = None
    mock_progress.tasks = MagicMock()
    mock_progress.tasks.__getitem__ = MagicMock(return_value=task_mock)

    with (
        patch("it_job_offers_analyzer.cli.scraping.CancellableProgress", return_value=mock_progress),
        patch("it_job_offers_analyzer.cli.scraping.cancel_aware_sleep"),
        patch("it_job_offers_analyzer.cli.scraping.check_cancel"),
    ):
        yield


# ---------------------------------------------------------------------------
# require_data
# ---------------------------------------------------------------------------


class TestRequireData:
    def test_true_when_offers_loaded(self, clean_state, capture_console):
        clean_state.offers = [{"title": "Test"}]
        assert require_data() is True

    def test_false_when_no_offers(self, clean_state, capture_console):
        assert require_data() is False

    def test_prints_error_when_no_offers(self, clean_state, capture_console):
        require_data()
        output = capture_console.getvalue()
        assert "No data" in output


# ---------------------------------------------------------------------------
# ensure_data
# ---------------------------------------------------------------------------


class TestEnsureData:
    def test_returns_true_when_cached(self, clean_state, capture_console):
        """If state already has matching data, no scrape needed."""
        clean_state.offers = [{"title": "Test"}]
        clean_state.city = "Kraków"
        clean_state.category = "python"
        args = FilterArgs(city="Kraków", category="python")
        assert ensure_data(args) is True

    def test_returns_false_when_no_city(self, clean_state, capture_console):
        args = FilterArgs(category="python")
        assert ensure_data(args) is False
        assert "city" in capture_console.getvalue().lower()

    def test_returns_false_when_no_category(self, clean_state, capture_console):
        args = FilterArgs(city="Kraków")
        assert ensure_data(args) is False
        assert "category" in capture_console.getvalue().lower()

    def test_scrapes_and_populates_state(self, clean_state, capture_console, make_raw_offer):
        """After scraping, state should have offers and filter values."""
        raw = make_raw_offer(slug="s1", title="Dev 1")
        batch = [("s1", {"title": "Dev 1", "company_name": "C"})]

        with patch(
                "it_job_offers_analyzer.cli.scraping.scrapper.iter_pages",
                return_value=iter([(batch, 1, True)]),
        ):
            args = FilterArgs(city="Kraków", category="python")
            result = ensure_data(args)

        assert result is True
        assert len(clean_state.offers) == 1
        assert clean_state.city == "Kraków"
        assert clean_state.category == "python"

    def test_scrape_with_details(self, clean_state, capture_console):
        """When need_details=True, fetch_detail should be called."""
        batch = [("slug-1", {"title": "Dev 1", "company_name": "C"})]

        with (
            patch(
                "it_job_offers_analyzer.cli.scraping.scrapper.iter_pages",
                return_value=iter([(batch, 1, True)]),
            ),
            patch(
                "it_job_offers_analyzer.cli.scraping.scrapper.fetch_detail",
                return_value="<p>body</p>",
            ) as mock_detail,
        ):
            args = FilterArgs(city="Kraków", category="python")
            result = ensure_data(args, need_details=True)

        assert result is True
        assert clean_state.has_details is True
        mock_detail.assert_called_once_with("slug-1")

    def test_uses_cached_city_if_not_in_args(self, clean_state, capture_console):
        """If args.city is None but state has a city, it should use cached city."""
        clean_state.city = "Kraków"
        clean_state.category = "python"
        # No offers → needs scrape, but city comes from state

        batch = [("s1", {"title": "Dev"})]
        with patch(
                "it_job_offers_analyzer.cli.scraping.scrapper.iter_pages",
                return_value=iter([(batch, 1, True)]),
        ):
            args = FilterArgs(category="java")  # different category, no city
            result = ensure_data(args)

        assert result is True
        assert clean_state.city == "Kraków"


# ---------------------------------------------------------------------------
# scrape_groups
# ---------------------------------------------------------------------------


class TestScrapeGroups:
    def test_returns_dict_per_group(self, clean_state, capture_console):
        batch_j = [("s1", {"title": "Junior Dev"})]
        batch_s = [("s2", {"title": "Senior Dev"})]

        call_count = [0]

        def fake_iter_pages(params):
            b = batch_j if call_count[0] == 0 else batch_s
            call_count[0] += 1
            yield b, 1, True

        with patch(
                "it_job_offers_analyzer.cli.scraping.scrapper.iter_pages",
                side_effect=fake_iter_pages,
        ):
            result = scrape_groups(
                ["junior", "senior"],
                build_params_fn=lambda v: ("Kraków", "python", v, None),
            )

        assert result is not None
        assert "junior" in result
        assert "senior" in result
        assert len(result["junior"]) == 1
        assert result["junior"][0]["title"] == "Junior Dev"

    def test_uses_label_fn(self, clean_state, capture_console):
        batch = [("s1", {"title": "Dev"})]

        with patch(
                "it_job_offers_analyzer.cli.scraping.scrapper.iter_pages",
                return_value=iter([(batch, 1, True)]),
        ):
            result = scrape_groups(
                ["junior"],
                build_params_fn=lambda v: ("Kraków", "python", v, None),
                label_fn=lambda v: v.upper(),
            )

        assert result is not None
        assert "junior" in result
