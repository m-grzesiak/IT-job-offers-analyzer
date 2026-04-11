"""Tests for it_job_offers_analyzer.analyzer — pure function tests."""

import pytest

from it_job_offers_analyzer.analyzer import (
    KEYWORDS_EXTRA_BENEFITS,
    KEYWORDS_SICK,
    KEYWORDS_VACATION,
    detect_outliers,
    extract_salaries,
    fmt,
    midpoint,
    normalize_monthly,
    percentile,
    search_keywords,
    strip_html,
)


# ---------------------------------------------------------------------------
# midpoint
# ---------------------------------------------------------------------------


class TestMidpoint:
    @pytest.mark.parametrize(
        "lo, hi, expected",
        [
            (10000, 20000, 15000.0),
            (0, 0, 0.0),
            (100, 100, 100.0),
            (0.5, 1.5, 1.0),
            (15000, 25000, 20000.0),
        ],
    )
    def test_midpoint(self, lo, hi, expected):
        assert midpoint(lo, hi) == expected


# ---------------------------------------------------------------------------
# normalize_monthly — boundary tests are critical
# ---------------------------------------------------------------------------


class TestNormalizeMonthly:
    @pytest.mark.parametrize(
        "salary, expected",
        [
            # Hourly bracket: < 500
            (0, 0),
            (100, 100 * 168),
            (150, 150 * 168),
            (499, 499 * 168),
            (499.99, 499.99 * 168),
            # Daily bracket: 500–1499
            (500, 500 * 21),
            (750, 750 * 21),
            (1499, 1499 * 21),
            (1499.99, 1499.99 * 21),
            # Monthly bracket: 1500–100000
            (1500, 1500),
            (25000, 25000),
            (50000, 50000),
            (100000, 100000),
            # Yearly bracket: > 100000
            (100001, 100001 / 12),
            (240000, 240000 / 12),
            (360000, 360000 / 12),
        ],
    )
    def test_normalize(self, salary, expected):
        assert normalize_monthly(salary) == pytest.approx(expected)

    def test_boundary_500_is_daily(self):
        """Exactly 500 should be treated as daily, not hourly."""
        assert normalize_monthly(500) == 500 * 21

    def test_boundary_1500_is_monthly(self):
        """Exactly 1500 should be treated as monthly."""
        assert normalize_monthly(1500) == 1500

    def test_boundary_100000_is_monthly(self):
        """Exactly 100000 should be treated as monthly (not yearly)."""
        assert normalize_monthly(100000) == 100000

    def test_boundary_100001_is_yearly(self):
        """100001 should be treated as yearly."""
        assert normalize_monthly(100001) == pytest.approx(100001 / 12)


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_single_item(self):
        assert percentile([5000], 50) == 5000

    def test_single_item_any_percentile(self):
        assert percentile([5000], 0) == 5000
        assert percentile([5000], 100) == 5000

    def test_two_items_p50(self):
        assert percentile([1000, 2000], 50) == 1500.0

    def test_two_items_p0(self):
        assert percentile([1000, 2000], 0) == 1000

    def test_two_items_p100(self):
        assert percentile([1000, 2000], 100) == 2000

    def test_interpolation(self):
        values = [10, 20, 30, 40, 50]
        assert percentile(values, 25) == 20.0
        assert percentile(values, 50) == 30.0
        assert percentile(values, 75) == 40.0

    def test_larger_dataset(self):
        values = list(range(1, 101))  # 1..100
        assert percentile(values, 50) == pytest.approx(50.5)
        assert percentile(values, 10) == pytest.approx(10.9)


# ---------------------------------------------------------------------------
# extract_salaries
# ---------------------------------------------------------------------------


class TestExtractSalaries:
    def test_basic_extraction(self, make_offer):
        offers = [make_offer(employment_types=[{
            "type": "b2b",
            "salary_from": 20000,
            "salary_to": 30000,
            "currency": "PLN",
            "unit": "monthly",
            "gross": False,
        }])]
        result = extract_salaries(offers, "b2b")
        assert len(result) == 1
        lo, hi, offer = result[0]
        assert lo == 20000
        assert hi == 30000

    def test_skips_offers_without_salary(self, make_offer):
        offers = [make_offer(employment_types=[{
            "type": "b2b",
            "salary_from": None,
            "salary_to": None,
            "currency": "PLN",
            "unit": "monthly",
            "gross": False,
        }])]
        assert extract_salaries(offers, "b2b") == []

    def test_filters_by_employment_type(self, make_offer):
        offers = [make_offer(employment_types=[
            {"type": "b2b", "salary_from": 20000, "salary_to": 30000, "currency": "PLN", "unit": "monthly",
             "gross": False},
            {"type": "permanent", "salary_from": 15000, "salary_to": 22000, "currency": "PLN", "unit": "monthly",
             "gross": True},
        ])]
        b2b = extract_salaries(offers, "b2b")
        assert len(b2b) == 1
        assert b2b[0][0] == 20000

        perm = extract_salaries(offers, "permanent")
        assert len(perm) == 1
        assert perm[0][0] == 15000

    def test_prefers_pln_currency(self, make_offer):
        offers = [make_offer(employment_types=[
            {"type": "b2b", "salary_from": 5000, "salary_to": 8000, "currency": "EUR", "unit": "monthly",
             "gross": False},
            {"type": "b2b", "salary_from": 20000, "salary_to": 30000, "currency": "PLN", "unit": "monthly",
             "gross": False},
        ])]
        result = extract_salaries(offers, "b2b")
        assert len(result) == 1
        assert result[0][0] == 20000  # PLN entry preferred

    def test_normalizes_salary_values(self, make_offer):
        """Hourly rate (< 500) should be normalized to monthly."""
        offers = [make_offer(employment_types=[{
            "type": "b2b",
            "salary_from": 100,
            "salary_to": 200,
            "currency": "PLN",
            "unit": "hourly",
            "gross": False,
        }])]
        result = extract_salaries(offers, "b2b")
        assert result[0][0] == 100 * 168
        assert result[0][1] == 200 * 168

    def test_no_employment_type_filter(self, make_offer):
        """None employment_type extracts all types."""
        offers = [make_offer(employment_types=[
            {"type": "b2b", "salary_from": 20000, "salary_to": 30000, "currency": "PLN", "unit": "monthly",
             "gross": False},
        ])]
        result = extract_salaries(offers, None)
        assert len(result) == 1

    def test_empty_offers_list(self):
        assert extract_salaries([], "b2b") == []


# ---------------------------------------------------------------------------
# detect_outliers
# ---------------------------------------------------------------------------


class TestDetectOutliers:
    def test_fewer_than_4_returns_all_clean(self, make_offer):
        tuples = [(20000, 30000, make_offer()) for _ in range(3)]
        clean, outliers = detect_outliers(tuples)
        assert len(clean) == 3
        assert len(outliers) == 0

    def test_single_item(self, make_offer):
        tuples = [(20000, 30000, make_offer())]
        clean, outliers = detect_outliers(tuples)
        assert len(clean) == 1
        assert len(outliers) == 0

    def test_empty_list(self):
        clean, outliers = detect_outliers([])
        assert clean == []
        assert outliers == []

    def test_all_same_values(self, make_offer):
        """When all midpoints are identical, IQR=0 and nothing is an outlier."""
        tuples = [(20000, 30000, make_offer()) for _ in range(10)]
        clean, outliers = detect_outliers(tuples)
        assert len(clean) == 10
        assert len(outliers) == 0

    def test_extreme_outlier_detected(self, make_offer):
        """One offer with wildly different salary should be flagged."""
        tuples = [(20000, 30000, make_offer(company_name=f"Normal {i}")) for i in range(9)]
        tuples.append((200000, 300000, make_offer(company_name="Outlier")))
        clean, outliers = detect_outliers(tuples)
        assert len(outliers) >= 1
        outlier_companies = [o["company_name"] for _, _, o in outliers]
        assert "Outlier" in outlier_companies

    def test_no_outliers_tight_range(self, salary_tuples):
        """A reasonable salary range should produce few or no outliers."""
        clean, outliers = detect_outliers(salary_tuples)
        assert len(clean) + len(outliers) == len(salary_tuples)


# ---------------------------------------------------------------------------
# strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_removes_tags(self):
        assert "hello" in strip_html("<p>Hello</p>")

    def test_decodes_nbsp(self):
        result = strip_html("hello&nbsp;world")
        assert "hello world" in result

    def test_decodes_amp(self):
        result = strip_html("a&amp;b")
        assert "a&b" in result

    def test_lowercases(self):
        result = strip_html("<b>HELLO World</b>")
        assert result.strip() == "hello world"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_nested_tags(self):
        result = strip_html("<div><p><b>text</b></p></div>")
        assert "text" in result


# ---------------------------------------------------------------------------
# search_keywords
# ---------------------------------------------------------------------------


class TestSearchKeywords:
    def test_finds_matching_keywords(self):
        text = "we offer unlimited pto and paid vacation days"
        found = search_keywords(text, KEYWORDS_VACATION)
        assert "pto" in found
        assert "vacation" in found

    def test_no_match_returns_empty(self):
        text = "competitive salary and health insurance"
        found = search_keywords(text, KEYWORDS_VACATION)
        assert found == []

    def test_substring_match(self):
        """Keywords use substring matching (k in text)."""
        text = "urlop wypoczynkowy 26 dni"
        found = search_keywords(text, KEYWORDS_VACATION)
        assert "urlop" in found

    def test_sick_leave_keywords(self):
        text = "paid sick leave and medical leave available"
        found = search_keywords(text, KEYWORDS_SICK)
        assert "sick leave" in found
        assert "medical leave" in found

    def test_extra_benefits_keywords(self):
        text = "kafeteria mybenefit budget for development"
        found = search_keywords(text, KEYWORDS_EXTRA_BENEFITS)
        assert "kafeteria" in found
        assert "mybenefit" in found
        assert "budget for development" in found


# ---------------------------------------------------------------------------
# fmt
# ---------------------------------------------------------------------------


class TestFmt:
    @pytest.mark.parametrize(
        "val, expected",
        [
            (0, "0 PLN"),
            (25000, "25,000 PLN"),
            (1234567, "1,234,567 PLN"),
            (999, "999 PLN"),
            (10000.7, "10,001 PLN"),
        ],
    )
    def test_format(self, val, expected):
        assert fmt(val) == expected
