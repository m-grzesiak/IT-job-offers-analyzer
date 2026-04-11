"""Tests for it_job_offers_analyzer.cli.display — SalaryStats, formatting, tables."""

import pytest
from rich.table import Table

from it_job_offers_analyzer.cli.display import (
    SalaryStats,
    fmt_delta,
    fmt_salary,
    make_distribution_table,
    make_percentile_table,
    make_summary_table,
    print_bar_chart,
)


# ---------------------------------------------------------------------------
# fmt_salary
# ---------------------------------------------------------------------------


class TestFmtSalary:
    @pytest.mark.parametrize(
        "val, expected",
        [
            (0, "0 PLN"),
            (999, "999 PLN"),
            (25000, "25 000 PLN"),
            (1234567, "1 234 567 PLN"),
            (10000.7, "10 001 PLN"),
        ],
    )
    def test_format(self, val, expected):
        assert fmt_salary(val) == expected

    def test_uses_space_separator(self):
        result = fmt_salary(1000000)
        assert "," not in result
        assert " " in result


# ---------------------------------------------------------------------------
# fmt_delta
# ---------------------------------------------------------------------------


class TestFmtDelta:
    def test_positive_delta(self):
        result = fmt_delta(5000)
        assert "+5 000 PLN" in result
        assert "green" in result

    def test_negative_delta(self):
        result = fmt_delta(-3000)
        assert "-3 000 PLN" in result
        assert "red" in result

    def test_zero_delta(self):
        result = fmt_delta(0)
        assert "0 PLN" in result
        assert "dim" in result

    def test_positive_uses_space_separator(self):
        result = fmt_delta(10000)
        assert "," not in result


# ---------------------------------------------------------------------------
# SalaryStats
# ---------------------------------------------------------------------------


class TestSalaryStats:
    def test_compute_returns_none_for_empty(self):
        assert SalaryStats.compute([]) is None

    def test_compute_single_offer(self, make_offer):
        salaries = [(20000, 30000, make_offer())]
        stats = SalaryStats.compute(salaries)
        assert stats is not None
        assert stats.count == 1
        assert stats.median_low == 20000
        assert stats.median_high == 30000
        assert stats.median_mid == 25000

    def test_compute_multiple_offers(self, make_offer):
        salaries = [
            (15000, 25000, make_offer()),
            (20000, 30000, make_offer()),
            (25000, 35000, make_offer()),
        ]
        stats = SalaryStats.compute(salaries)
        assert stats.count == 3
        assert stats.median_low == 20000
        assert stats.median_high == 30000
        assert stats.median_mid == 25000  # midpoints: 20000, 25000, 30000

    def test_midpoints_sorted(self, make_offer):
        salaries = [
            (30000, 40000, make_offer()),
            (10000, 20000, make_offer()),
            (20000, 30000, make_offer()),
        ]
        stats = SalaryStats.compute(salaries)
        assert stats.midpoints == sorted(stats.midpoints)

    def test_compute_with_salary_tuples(self, salary_tuples):
        stats = SalaryStats.compute(salary_tuples)
        assert stats.count == 10
        assert stats.midpoints == sorted(stats.midpoints)


# ---------------------------------------------------------------------------
# Table builders — smoke tests
# ---------------------------------------------------------------------------


class TestTableBuilders:
    def test_make_summary_table(self, make_offer):
        salaries = [(20000, 30000, make_offer())]
        stats = SalaryStats.compute(salaries)
        table = make_summary_table(stats, total_offers=5)
        assert isinstance(table, Table)

    def test_make_percentile_table(self):
        midpoints = sorted([15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 55000, 60000])
        table = make_percentile_table(midpoints)
        assert isinstance(table, Table)

    def test_make_distribution_table(self):
        midpoints = sorted([15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 55000, 60000])
        table = make_distribution_table(midpoints)
        assert isinstance(table, Table)

    def test_percentile_table_with_title(self):
        midpoints = sorted([10000, 20000, 30000, 40000, 50000])
        table = make_percentile_table(midpoints, title="Custom Title")
        assert table.title == "Custom Title"

    def test_distribution_table_with_title(self):
        midpoints = sorted([10000, 20000, 30000, 40000, 50000])
        table = make_distribution_table(midpoints, title="Custom Title")
        assert table.title == "Custom Title"


# ---------------------------------------------------------------------------
# print_bar_chart — smoke test
# ---------------------------------------------------------------------------


class TestPrintBarChart:
    def test_does_not_crash_with_data(self, capture_console):
        items = [("Junior", 15000.0), ("Senior", 30000.0)]
        print_bar_chart(items)

    def test_does_not_crash_with_empty(self, capture_console):
        print_bar_chart([])
