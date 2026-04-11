"""Shared fixtures for the IT Job Offers Analyzer test suite."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from it_job_offers_analyzer.cli.state import state


# ---------------------------------------------------------------------------
# Offer factories
# ---------------------------------------------------------------------------


@pytest.fixture
def make_raw_offer():
    """Factory for raw API offer dicts (camelCase keys, from/to salary)."""

    def _make(
            slug="test-offer-1",
            title="Senior Python Developer",
            company_name="Acme Corp",
            city="Krakow",
            street="ul. Testowa 1",
            experience_level="senior",
            workplace_type="remote",
            working_time="full_time",
            employment_types=None,
            languages=None,
            published_at="2025-01-01T12:00:00Z",
            expired_at="2025-02-01T12:00:00Z",
    ):
        if employment_types is None:
            employment_types = [
                {
                    "type": "b2b",
                    "from": 20000,
                    "to": 30000,
                    "currency": "pln",
                    "unit": "monthly",
                    "gross": False,
                }
            ]
        return {
            "slug": slug,
            "title": title,
            "companyName": company_name,
            "city": city,
            "street": street,
            "experienceLevel": experience_level,
            "workplaceType": workplace_type,
            "workingTime": working_time,
            "employmentTypes": employment_types,
            "languages": languages or [],
            "publishedAt": published_at,
            "expiredAt": expired_at,
        }

    return _make


@pytest.fixture
def make_offer():
    """Factory for transformed offer dicts (snake_case, salary_from/salary_to)."""

    def _make(
            title="Senior Python Developer",
            company_name="Acme Corp",
            city="Krakow",
            experience_level="senior",
            workplace_type="remote",
            employment_types=None,
            body=None,
            url="https://justjoin.it/job-offer/test-offer-1",
            published_at="2025-01-01T12:00:00Z",
    ):
        if employment_types is None:
            employment_types = [
                {
                    "type": "b2b",
                    "salary_from": 20000,
                    "salary_to": 30000,
                    "currency": "PLN",
                    "unit": "monthly",
                    "gross": False,
                }
            ]
        offer = {
            "title": title,
            "company_name": company_name,
            "city": city,
            "street": "ul. Testowa 1",
            "experience_level": experience_level,
            "workplace_type": workplace_type,
            "working_time": "full_time",
            "employment_types": employment_types,
            "languages": [],
            "published_at": published_at,
            "expired_at": "2025-02-01T12:00:00Z",
            "url": url,
        }
        if body is not None:
            offer["body"] = body
        return offer

    return _make


@pytest.fixture
def salary_tuples(make_offer):
    """10 salary tuples spanning a realistic range for analyzer tests."""
    data = [
        (15000, 20000),
        (18000, 25000),
        (20000, 28000),
        (22000, 30000),
        (24000, 32000),
        (25000, 35000),
        (28000, 38000),
        (30000, 40000),
        (35000, 45000),
        (40000, 55000),
    ]
    return [
        (lo, hi, make_offer(company_name=f"Company {i}", title=f"Dev {i}"))
        for i, (lo, hi) in enumerate(data)
    ]


# ---------------------------------------------------------------------------
# API response factory
# ---------------------------------------------------------------------------


@pytest.fixture
def make_api_response():
    """Factory for paginated justjoin.it API responses."""

    def _make(raw_offers, total_items, next_cursor=None):
        meta = {"totalItems": total_items, "next": {}}
        if next_cursor is not None:
            meta["next"]["cursor"] = next_cursor
        return {"data": raw_offers, "meta": meta}

    return _make


# ---------------------------------------------------------------------------
# Mocked urllib
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_urlopen():
    """Patch urllib.request.urlopen to return sequenced JSON responses.

    Usage:
        def test_something(mock_urlopen):
            mock_urlopen([response_dict_1, response_dict_2])
            # now fetch_page / fetch_detail will consume these in order
    """

    def _setup(responses):
        call_idx = [0]

        def side_effect(req, **kwargs):
            data = responses[call_idx[0]]
            call_idx[0] += 1
            body = json.dumps(data).encode("utf-8")
            resp = MagicMock()
            resp.read.return_value = body
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        patcher = patch(
            "it_job_offers_analyzer.scrapper.urllib.request.urlopen",
            side_effect=side_effect,
        )
        mock = patcher.start()
        return mock, patcher

    patchers = []

    def setup(responses):
        mock, patcher = _setup(responses)
        patchers.append(patcher)
        return mock

    yield setup

    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# Session state reset
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_state():
    """Reset the global SessionState before and after each test."""
    state.reset()
    yield state
    state.reset()


# ---------------------------------------------------------------------------
# Console output capture
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_console():
    """Replace the shared Rich console with one that captures to StringIO."""
    from it_job_offers_analyzer.cli.display import THEME

    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120, theme=THEME)
    with (
        patch("it_job_offers_analyzer.cli.commands.console", test_console),
        patch("it_job_offers_analyzer.cli.display.console", test_console),
        patch("it_job_offers_analyzer.cli.scraping.console", test_console),
        patch("it_job_offers_analyzer.cli.parsing.console", test_console),
        patch("it_job_offers_analyzer.cli.app.console", test_console),
    ):
        yield buf
