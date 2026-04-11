"""Tests for it_job_offers_analyzer.scrapper — pure functions + mocked HTTP."""

from it_job_offers_analyzer.scrapper import (
    BASE_URL,
    OFFER_URL_TEMPLATE,
    build_params,
    build_url,
    fetch_detail,
    fetch_page,
    iter_pages,
    transform_offer,
)


# ---------------------------------------------------------------------------
# build_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_basic_params(self):
        url = build_url({"city": "Krakow", "itemsCount": 100})
        assert url.startswith(BASE_URL + "?")
        assert "city=Krakow" in url
        assert "itemsCount=100" in url

    def test_filters_none_values(self):
        url = build_url({"city": "Krakow", "experience": None})
        assert "experience" not in url
        assert "city=Krakow" in url

    def test_empty_dict(self):
        url = build_url({})
        assert url == f"{BASE_URL}?"

    def test_list_values_doseq(self):
        url = build_url({"categories": ["python", "java"]})
        assert "categories=python" in url
        assert "categories=java" in url


# ---------------------------------------------------------------------------
# build_params
# ---------------------------------------------------------------------------


class TestBuildParams:
    def test_base_params_always_present(self):
        params = build_params()
        assert params["itemsCount"] == 100
        assert params["sortBy"] == "publishedAt"
        assert params["orderBy"] == "descending"

    def test_city_param(self):
        params = build_params(city="Krakow")
        assert params["city"] == "Krakow"

    def test_category_param(self):
        params = build_params(category="python")
        assert params["categories"] == "python"

    def test_experience_param(self):
        params = build_params(experience="senior")
        assert params["experienceLevels"] == "senior"

    def test_workplace_param(self):
        params = build_params(workplace="remote")
        assert params["workplaceType"] == "remote"

    def test_employment_param(self):
        params = build_params(employment="b2b")
        assert params["employmentTypes"] == "b2b"

    def test_with_salary(self):
        params = build_params(with_salary=True)
        assert params["withSalary"] == "true"

    def test_without_salary_no_key(self):
        params = build_params(with_salary=False)
        assert "withSalary" not in params

    def test_all_params(self):
        params = build_params(
            city="Krakow",
            category="python",
            experience="senior",
            workplace="remote",
            employment="b2b",
            working_time="full_time",
            keyword="django",
            with_salary=True,
        )
        assert params["city"] == "Krakow"
        assert params["categories"] == "python"
        assert params["experienceLevels"] == "senior"
        assert params["workplaceType"] == "remote"
        assert params["employmentTypes"] == "b2b"
        assert params["workingTimes"] == "full_time"
        assert params["keyword"] == "django"
        assert params["withSalary"] == "true"


# ---------------------------------------------------------------------------
# transform_offer
# ---------------------------------------------------------------------------


class TestTransformOffer:
    def test_field_mapping(self, make_raw_offer):
        raw = make_raw_offer()
        result = transform_offer(raw)
        assert result["title"] == "Senior Python Developer"
        assert result["company_name"] == "Acme Corp"
        assert result["city"] == "Krakow"
        assert result["experience_level"] == "senior"
        assert result["workplace_type"] == "remote"
        assert result["working_time"] == "full_time"

    def test_url_from_slug(self, make_raw_offer):
        raw = make_raw_offer(slug="my-test-slug")
        result = transform_offer(raw)
        assert result["url"] == OFFER_URL_TEMPLATE.format(slug="my-test-slug")

    def test_employment_types_mapped(self, make_raw_offer):
        raw = make_raw_offer(employment_types=[{
            "type": "b2b",
            "from": 20000,
            "to": 30000,
            "currency": "pln",
            "unit": "monthly",
            "gross": False,
        }])
        result = transform_offer(raw)
        et = result["employment_types"][0]
        assert et["salary_from"] == 20000
        assert et["salary_to"] == 30000
        assert et["currency"] == "pln"
        assert et["type"] == "b2b"

    def test_body_included_when_provided(self, make_raw_offer):
        raw = make_raw_offer()
        result = transform_offer(raw, body="<p>Description</p>")
        assert result["body"] == "<p>Description</p>"

    def test_body_absent_when_none(self, make_raw_offer):
        raw = make_raw_offer()
        result = transform_offer(raw, body=None)
        assert "body" not in result

    def test_missing_optional_fields(self):
        raw = {"slug": "s", "employmentTypes": []}
        result = transform_offer(raw)
        assert result["title"] is None
        assert result["company_name"] is None
        assert result["employment_types"] == []
        assert result["languages"] == []

    def test_multiple_employment_types(self, make_raw_offer):
        raw = make_raw_offer(employment_types=[
            {"type": "b2b", "from": 20000, "to": 30000, "currency": "pln", "unit": "monthly", "gross": False},
            {"type": "permanent", "from": 15000, "to": 22000, "currency": "pln", "unit": "monthly", "gross": True},
        ])
        result = transform_offer(raw)
        assert len(result["employment_types"]) == 2


# ---------------------------------------------------------------------------
# fetch_page (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchPage:
    def test_returns_parsed_json(self, mock_urlopen, make_raw_offer, make_api_response):
        raw = make_raw_offer()
        response = make_api_response([raw], total_items=1)
        mock = mock_urlopen([response])

        result = fetch_page({"itemsCount": 100}, cursor=0)
        assert result["data"][0]["title"] == "Senior Python Developer"
        assert result["meta"]["totalItems"] == 1

    def test_sends_correct_headers(self, mock_urlopen, make_api_response):
        mock = mock_urlopen([make_api_response([], 0)])
        fetch_page({"itemsCount": 100}, cursor=0)

        call_args = mock.call_args
        req = call_args[0][0]
        assert "Mozilla" in req.get_header("User-agent")
        assert req.get_header("Accept") == "application/json"
        assert req.get_header("Referer") == "https://justjoin.it/"

    def test_cursor_in_url(self, mock_urlopen, make_api_response):
        mock = mock_urlopen([make_api_response([], 0)])
        fetch_page({"itemsCount": 100}, cursor=200)

        call_args = mock.call_args
        req = call_args[0][0]
        assert "from=200" in req.full_url


# ---------------------------------------------------------------------------
# fetch_detail (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchDetail:
    def test_returns_body(self, mock_urlopen):
        mock_urlopen([{"body": "<p>Job description</p>"}])
        result = fetch_detail("test-slug")
        assert result == "<p>Job description</p>"

    def test_missing_body_returns_empty(self, mock_urlopen):
        mock_urlopen([{"title": "some offer"}])
        result = fetch_detail("test-slug")
        assert result == ""

    def test_slug_in_url(self, mock_urlopen):
        mock = mock_urlopen([{"body": ""}])
        fetch_detail("my-special-slug")

        call_args = mock.call_args
        req = call_args[0][0]
        assert "my-special-slug" in req.full_url


# ---------------------------------------------------------------------------
# iter_pages (mocked HTTP)
# ---------------------------------------------------------------------------


class TestIterPages:
    def test_single_page(self, mock_urlopen, make_raw_offer, make_api_response):
        raw = make_raw_offer(slug="offer-1")
        response = make_api_response([raw], total_items=1, next_cursor=None)
        mock_urlopen([response])

        pages = list(iter_pages({"itemsCount": 100}))
        assert len(pages) == 1
        batch, total, is_last = pages[0]
        assert total == 1
        assert is_last is True
        assert len(batch) == 1
        assert batch[0][0] == "offer-1"  # slug

    def test_two_pages(self, mock_urlopen, make_raw_offer, make_api_response):
        raw1 = make_raw_offer(slug="offer-1")
        raw2 = make_raw_offer(slug="offer-2")
        page1 = make_api_response([raw1], total_items=2, next_cursor=100)
        page2 = make_api_response([raw2], total_items=2, next_cursor=None)
        mock_urlopen([page1, page2])

        pages = list(iter_pages({"itemsCount": 100}))
        assert len(pages) == 2
        assert pages[0][2] is False  # not last
        assert pages[1][2] is True  # last

    def test_empty_response(self, mock_urlopen, make_api_response):
        response = make_api_response([], total_items=0, next_cursor=None)
        mock_urlopen([response])

        pages = list(iter_pages({"itemsCount": 100}))
        assert len(pages) == 1
        batch, total, is_last = pages[0]
        assert total == 0
        assert is_last is True
        assert batch == []

    def test_cursor_not_advancing_stops(self, mock_urlopen, make_raw_offer, make_api_response):
        """If next_cursor <= current cursor, pagination should stop."""
        raw = make_raw_offer()
        # next_cursor=0 which equals initial cursor=0
        response = make_api_response([raw], total_items=100, next_cursor=0)
        mock_urlopen([response])

        pages = list(iter_pages({"itemsCount": 100}))
        assert len(pages) == 1
        assert pages[0][2] is True  # is_last

    def test_transforms_offers(self, mock_urlopen, make_raw_offer, make_api_response):
        raw = make_raw_offer(title="Test Dev", company_name="TestCo")
        response = make_api_response([raw], total_items=1)
        mock_urlopen([response])

        pages = list(iter_pages({"itemsCount": 100}))
        slug, offer = pages[0][0][0]
        assert offer["title"] == "Test Dev"
        assert offer["company_name"] == "TestCo"
