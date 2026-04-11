"""Tests for it_job_offers_analyzer.cli.parsing — parse_args + parse_compare_args."""

from it_job_offers_analyzer.cli.parsing import parse_args, parse_compare_args
from it_job_offers_analyzer.cli.state import FilterArgs


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_empty_string(self):
        result = parse_args("")
        assert result == FilterArgs()

    def test_city_recognized(self):
        result = parse_args("Kraków")
        assert result.city == "Kraków"

    def test_city_case_insensitive(self):
        result = parse_args("kraków")
        assert result.city == "Kraków"

    def test_category_recognized(self):
        result = parse_args("python")
        assert result.category == "python"

    def test_experience_recognized(self):
        result = parse_args("senior")
        assert result.experience == "senior"

    def test_workplace_recognized(self):
        result = parse_args("remote")
        assert result.workplace == "remote"

    def test_employment_type_recognized(self):
        result = parse_args("b2b")
        assert result.emp_type == "b2b"

    def test_full_args(self):
        result = parse_args("Kraków python senior remote b2b")
        assert result.city == "Kraków"
        assert result.category == "python"
        assert result.experience == "senior"
        assert result.workplace == "remote"
        assert result.emp_type == "b2b"

    def test_order_independent(self):
        r1 = parse_args("python Kraków senior b2b")
        r2 = parse_args("Kraków python senior b2b")
        assert r1.city == r2.city
        assert r1.category == r2.category

    def test_percentile_with_p(self):
        result = parse_args(">P90")
        assert result.top_percentile == 90

    def test_percentile_without_p(self):
        result = parse_args(">75")
        assert result.top_percentile == 75

    def test_percentile_with_other_args(self):
        result = parse_args("Kraków python b2b >P80")
        assert result.top_percentile == 80
        assert result.city == "Kraków"
        assert result.category == "python"

    def test_unknown_arg_returns_none(self, capture_console):
        result = parse_args("nonexistent_token")
        assert result is None

    def test_unknown_prints_warning(self, capture_console):
        parse_args("nonexistent_token")
        output = capture_console.getvalue()
        assert "Unknown argument" in output

    def test_did_you_mean_suggestion(self, capture_console):
        parse_args("pytho")
        output = capture_console.getvalue()
        assert "python" in output

    def test_flag_args_ignored(self):
        """Args starting with - are silently ignored, not treated as unknown."""
        result = parse_args("-v")
        assert result is not None

    def test_warszawa_case_insensitive(self):
        result = parse_args("warszawa")
        assert result.city == "Warszawa"

    def test_c_level_experience(self):
        result = parse_args("c_level")
        assert result.experience == "c_level"


# ---------------------------------------------------------------------------
# parse_compare_args
# ---------------------------------------------------------------------------


class TestParseCompareArgs:
    def test_two_cities(self, capture_console):
        result = parse_compare_args("Kraków Warszawa python senior b2b")
        assert result is not None
        axis_name, axis_values, filters = result
        assert axis_name == "city"
        assert "Kraków" in axis_values
        assert "Warszawa" in axis_values
        assert filters.category == "python"
        assert filters.experience == "senior"
        assert filters.emp_type == "b2b"

    def test_two_categories(self, capture_console):
        result = parse_compare_args("Kraków python java senior")
        assert result is not None
        axis_name, axis_values, filters = result
        assert axis_name == "category"
        assert set(axis_values) == {"python", "java"}
        assert filters.city == "Kraków"
        assert filters.experience == "senior"

    def test_two_experience_levels(self, capture_console):
        result = parse_compare_args("Kraków python junior senior b2b")
        assert result is not None
        axis_name, axis_values, _ = result
        assert axis_name == "experience"
        assert set(axis_values) == {"junior", "senior"}

    def test_two_employment_types(self, capture_console):
        result = parse_compare_args("Kraków python senior b2b permanent")
        assert result is not None
        axis_name, axis_values, _ = result
        assert axis_name == "employment"
        assert set(axis_values) == {"b2b", "permanent"}

    def test_two_workplace_types(self, capture_console):
        result = parse_compare_args("Kraków python remote office b2b")
        assert result is not None
        axis_name, axis_values, _ = result
        assert axis_name == "workplace"
        assert set(axis_values) == {"remote", "office"}

    def test_empty_args_returns_none(self, capture_console):
        result = parse_compare_args("")
        assert result is None

    def test_no_multi_group_returns_none(self, capture_console):
        result = parse_compare_args("Kraków python senior")
        assert result is None
        output = capture_console.getvalue()
        assert "multiple values" in output.lower() or "Provide" in output

    def test_multiple_axes_returns_none(self, capture_console):
        """Two cities AND two categories → error."""
        result = parse_compare_args("Kraków Warszawa python java")
        assert result is None
        output = capture_console.getvalue()
        assert "Multiple" in output or "multiple" in output

    def test_unknown_token_returns_none(self, capture_console):
        result = parse_compare_args("Kraków Warszawa unknown_token")
        assert result is None
        output = capture_console.getvalue()
        assert "Unknown" in output

    def test_three_cities(self, capture_console):
        result = parse_compare_args("Kraków Warszawa Wrocław python senior")
        assert result is not None
        axis_name, axis_values, _ = result
        assert axis_name == "city"
        assert len(axis_values) == 3

    def test_single_values_become_filters(self, capture_console):
        result = parse_compare_args("Kraków Warszawa python senior b2b remote")
        assert result is not None
        _, _, filters = result
        assert filters.category == "python"
        assert filters.experience == "senior"
        assert filters.emp_type == "b2b"
        assert filters.workplace == "remote"
