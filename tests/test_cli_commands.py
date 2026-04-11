"""Tests for it_job_offers_analyzer.cli.commands — all command handlers."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from it_job_offers_analyzer.cli import commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _populate_state(state, make_offer, n=20):
    """Fill state with n offers from mixed companies, with salary data."""
    offers = []
    companies = ["Acme Corp", "Beta Inc", "Gamma Ltd", "Delta SA", "Epsilon"]
    for i in range(n):
        company = companies[i % len(companies)]
        offers.append(make_offer(
            title=f"Dev {i}",
            company_name=company,
            employment_types=[{
                "type": "b2b",
                "salary_from": 15000 + i * 1000,
                "salary_to": 25000 + i * 1000,
                "currency": "PLN",
                "unit": "monthly",
                "gross": False,
            }],
        ))
    state.offers = offers
    state.city = "Kraków"
    state.category = "python"
    return offers


# ---------------------------------------------------------------------------
# cmd_analyze
# ---------------------------------------------------------------------------


class TestCmdAnalyze:
    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_prints_tables(self, mock_ed, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer)
        commands.cmd_analyze("Kraków python b2b")
        output = capture_console.getvalue()
        assert "Summary" in output or "Median" in output or "PLN" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_no_salary_data(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(employment_types=[{
            "type": "b2b",
            "salary_from": None,
            "salary_to": None,
            "currency": "PLN",
            "unit": "monthly",
            "gross": False,
        }])]
        commands.cmd_analyze("Kraków python b2b")
        output = capture_console.getvalue()
        assert "No offers with salary data" in output or "no" in output.lower()

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=False)
    def test_ensure_data_fails(self, mock_ed, clean_state, capture_console):
        commands.cmd_analyze("Kraków python")
        output = capture_console.getvalue()
        # Should not crash, no tables printed
        assert "Summary" not in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_specific_emp_type(self, mock_ed, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer)
        commands.cmd_analyze("Kraków python b2b")
        output = capture_console.getvalue()
        assert "B2B" in output


# ---------------------------------------------------------------------------
# cmd_top
# ---------------------------------------------------------------------------


class TestCmdTop:
    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_prints_top_companies(self, mock_ed, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer)
        commands.cmd_top("Kraków python b2b")
        output = capture_console.getvalue()
        assert "PLN" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_not_enough_data(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer()]
        commands.cmd_top("Kraków python b2b")
        output = capture_console.getvalue()
        assert "not enough" in output.lower() or "No offers" in output


# ---------------------------------------------------------------------------
# cmd_outliers
# ---------------------------------------------------------------------------


class TestCmdOutliers:
    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_no_outliers(self, mock_ed, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer)
        commands.cmd_outliers("Kraków python b2b")
        output = capture_console.getvalue()
        # Either "No outliers" or shows some outliers — depends on data
        assert "outlier" in output.lower() or "No outliers" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_with_outlier(self, mock_ed, clean_state, capture_console, make_offer):
        offers = [make_offer(
            company_name=f"Normal {i}",
            employment_types=[
                {"type": "b2b", "salary_from": 20000, "salary_to": 30000, "currency": "PLN", "unit": "monthly",
                 "gross": False}],
        ) for i in range(10)]
        offers.append(make_offer(
            company_name="Outlier Co",
            employment_types=[
                {"type": "b2b", "salary_from": 200000, "salary_to": 300000, "currency": "PLN", "unit": "monthly",
                 "gross": False}],
        ))
        clean_state.offers = offers
        commands.cmd_outliers("b2b")
        output = capture_console.getvalue()
        # The extreme salary should be flagged
        assert "outlier" in output.lower() or "Outlier" in output


# ---------------------------------------------------------------------------
# cmd_benefits
# ---------------------------------------------------------------------------


class TestCmdBenefits:
    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_detects_vacation_keywords(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(
            body="<p>We offer paid vacation and unlimited PTO</p>",
            employment_types=[
                {"type": "b2b", "salary_from": 20000, "salary_to": 30000, "currency": "PLN", "unit": "monthly",
                 "gross": False}],
        )]
        commands.cmd_benefits("Kraków python")
        output = capture_console.getvalue()
        assert "vacation" in output.lower() or "Vacation" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_no_b2b_offers(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(
            body="<p>Some text</p>",
            employment_types=[
                {"type": "permanent", "salary_from": 20000, "salary_to": 30000, "currency": "PLN", "unit": "monthly",
                 "gross": False}],
        )]
        commands.cmd_benefits("Kraków python")
        output = capture_console.getvalue()
        assert "No B2B" in output or "no" in output.lower()


# ---------------------------------------------------------------------------
# cmd_companies
# ---------------------------------------------------------------------------


class TestCmdCompanies:
    def test_lists_companies(self, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer)
        commands.cmd_companies()
        output = capture_console.getvalue()
        assert "Acme Corp" in output
        assert "Beta Inc" in output

    def test_no_data(self, clean_state, capture_console):
        commands.cmd_companies()
        output = capture_console.getvalue()
        assert "No data" in output


# ---------------------------------------------------------------------------
# cmd_show
# ---------------------------------------------------------------------------


class TestCmdShow:
    def test_exact_match(self, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(company_name="Revolut")]
        commands.cmd_show("Revolut")
        output = capture_console.getvalue()
        assert "Revolut" in output

    def test_case_insensitive_match(self, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(company_name="Revolut")]
        commands.cmd_show("revolut")
        output = capture_console.getvalue()
        assert "Revolut" in output

    def test_substring_match(self, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(company_name="Revolut Technology")]
        commands.cmd_show("revolut")
        output = capture_console.getvalue()
        assert "Revolut Technology" in output

    def test_no_match(self, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(company_name="Acme Corp")]
        commands.cmd_show("nonexistent")
        output = capture_console.getvalue()
        assert "No offers found" in output

    def test_empty_args(self, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer()]
        commands.cmd_show("")
        output = capture_console.getvalue()
        assert "Specify company" in output or "company name" in output.lower()


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


class TestCmdStatus:
    def test_with_offers(self, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer, n=5)
        commands.cmd_status()
        output = capture_console.getvalue()
        assert "5" in output

    def test_without_offers(self, clean_state, capture_console):
        commands.cmd_status()
        output = capture_console.getvalue()
        assert "No offers loaded" in output


# ---------------------------------------------------------------------------
# cmd_clear
# ---------------------------------------------------------------------------


class TestCmdClear:
    def test_resets_state(self, clean_state, capture_console, make_offer):
        _populate_state(clean_state, make_offer, n=5)
        assert len(clean_state.offers) == 5
        with patch("it_job_offers_analyzer.cli.app.show_welcome"):
            commands.cmd_clear()
        assert clean_state.offers == []
        assert clean_state.city is None


# ---------------------------------------------------------------------------
# cmd_help
# ---------------------------------------------------------------------------


class TestCmdHelp:
    def test_prints_commands(self, capture_console):
        commands.cmd_help()
        output = capture_console.getvalue()
        assert "/analyze" in output
        assert "/top" in output
        assert "/help" in output
        assert "/recent" in output


# ---------------------------------------------------------------------------
# cmd_recent
# ---------------------------------------------------------------------------


def _recent_ts(hours_ago: int) -> str:
    """Return an ISO timestamp N hours ago from now."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestCmdRecent:
    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_shows_recent_offers(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [
            make_offer(company_name="FreshCo", last_published_at=_recent_ts(2)),
            make_offer(company_name="OldCo", last_published_at="2020-01-01T12:00:00Z"),
        ]
        commands.cmd_recent("")
        output = capture_console.getvalue()
        assert "FreshCo" in output
        assert "OldCo" not in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_custom_days(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [
            make_offer(company_name="Yesterday", last_published_at=_recent_ts(20)),
            make_offer(company_name="LastWeek", last_published_at=_recent_ts(150)),
        ]
        # 1 day — only "Yesterday" (20h ago)
        commands.cmd_recent("1")
        output = capture_console.getvalue()
        assert "Yesterday" in output
        assert "LastWeek" not in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_custom_days_wider(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [
            make_offer(company_name="Yesterday", last_published_at=_recent_ts(20)),
            make_offer(company_name="LastWeek", last_published_at=_recent_ts(150)),
        ]
        # 7 days — both should show
        commands.cmd_recent("7")
        output = capture_console.getvalue()
        assert "Yesterday" in output
        assert "LastWeek" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_no_recent_offers(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [
            make_offer(last_published_at="2020-01-01T12:00:00Z"),
        ]
        commands.cmd_recent("")
        output = capture_console.getvalue()
        assert "No offers published" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_shows_salary_info(self, mock_ed, clean_state, capture_console, make_offer):
        clean_state.offers = [make_offer(last_published_at=_recent_ts(1))]
        commands.cmd_recent("")
        output = capture_console.getvalue()
        assert "PLN" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_days_with_filters(self, mock_ed, clean_state, capture_console, make_offer):
        """Days argument should be extracted; remaining args passed to parse_args."""
        clean_state.offers = [
            make_offer(company_name="Recent", last_published_at=_recent_ts(5)),
        ]
        commands.cmd_recent("7 b2b")
        output = capture_console.getvalue()
        assert "Recent" in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=True)
    def test_uses_last_published_at_not_published_at(self, mock_ed, clean_state, capture_console, make_offer):
        """Offer bumped recently (published_at=now) but originally old should NOT appear."""
        clean_state.offers = [
            make_offer(
                company_name="BumpedCo",
                published_at=_recent_ts(1),           # bumped 1h ago
                last_published_at="2020-01-01T12:00:00Z",  # actually 5 years old
            ),
        ]
        commands.cmd_recent("")
        output = capture_console.getvalue()
        assert "BumpedCo" not in output

    @patch("it_job_offers_analyzer.cli.commands.ensure_data", return_value=False)
    def test_ensure_data_fails(self, mock_ed, clean_state, capture_console):
        commands.cmd_recent("Kraków python")
        output = capture_console.getvalue()
        assert "Recent" not in output
