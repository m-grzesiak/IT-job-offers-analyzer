#!/usr/bin/env python3
"""
JustJoin.IT Job Offers Scraper
==============================
Scrapes job offers from justjoin.it using their internal REST API.
Supports filtering by city, category, experience level, workplace type,
employment type, keyword, and more.

Usage examples:
    python justjoin_scraper.py --city Warszawa
    python justjoin_scraper.py --city Kraków --category python --experience senior
    python justjoin_scraper.py --city Warszawa --category javascript --workplace remote --keyword react
    python justjoin_scraper.py --city Gdańsk --employment b2b --with-salary --limit 50
    python justjoin_scraper.py --city Wrocław --output offers.json
"""

import json
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "https://justjoin.it/api/candidate-api/offers"
DETAIL_URL_TEMPLATE = "https://justjoin.it/api/candidate-api/offers/{slug}"
OFFER_URL_TEMPLATE = "https://justjoin.it/job-offer/{slug}"
PAGE_SIZE = 100  # max items per request

CATEGORIES = [
    "javascript", "html", "php", "ruby", "python", "java", "net",
    "scala", "c", "mobile", "testing", "devops", "admin", "ux",
    "pm", "game", "analytics", "security", "data", "go", "support",
    "erp", "architecture", "other",
]

EXPERIENCE_LEVELS = ["junior", "mid", "senior", "c_level"]
WORKPLACE_TYPES = ["remote", "hybrid", "office"]
EMPLOYMENT_TYPES = ["b2b", "permanent", "mandate", "internship"]
WORKING_TIMES = ["full_time", "part_time", "freelance"]


def build_url(params: dict) -> str:
    """Build the API URL with query parameters, filtering out None values."""
    filtered = {k: v for k, v in params.items() if v is not None}
    query = urllib.parse.urlencode(filtered, doseq=True)
    return f"{BASE_URL}?{query}"


def fetch_page(params: dict, cursor: int = 0) -> dict:
    """Fetch a single page of offers from the API."""
    params["from"] = cursor
    url = build_url(params)

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://justjoin.it/",
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_detail(slug: str) -> str:
    """Fetch the full offer body (HTML) by slug."""
    url = DETAIL_URL_TEMPLATE.format(slug=slug)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://justjoin.it/",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("body", "")


def transform_offer(raw: dict, body: str | None = None) -> dict:
    """Transform a raw API offer into the desired output format."""
    # Build salary/employment info
    employment = []
    for et in raw.get("employmentTypes", []):
        entry = {
            "type": et.get("type"),
            "salary_from": et.get("from"),
            "salary_to": et.get("to"),
            "currency": et.get("currency"),
            "unit": et.get("unit"),
            "gross": et.get("gross"),
        }
        employment.append(entry)

    slug = raw.get("slug", "")

    result = {
        "title": raw.get("title"),
        "company_name": raw.get("companyName"),
        "city": raw.get("city"),
        "street": raw.get("street"),
        "experience_level": raw.get("experienceLevel"),
        "workplace_type": raw.get("workplaceType"),
        "working_time": raw.get("workingTime"),
        "employment_types": employment,
        "languages": raw.get("languages", []),
        "published_at": raw.get("publishedAt"),
        "expired_at": raw.get("expiredAt"),
        "url": OFFER_URL_TEMPLATE.format(slug=slug),
    }
    if body is not None:
        result["body"] = body
    return result


def build_params(city=None, category=None, experience=None, workplace=None,
                 employment=None, working_time=None, keyword=None, with_salary=False):
    """Build API query parameters from filters."""
    params = {
        "itemsCount": PAGE_SIZE,
        "sortBy": "publishedAt",
        "orderBy": "descending",
    }
    if city:
        params["city"] = city
    if category:
        params["categories"] = category
    if experience:
        params["experienceLevels"] = experience
    if workplace:
        params["workplaceType"] = workplace
    if employment:
        params["employmentTypes"] = employment
    if working_time:
        params["workingTimes"] = working_time
    if keyword:
        params["keyword"] = keyword
    if with_salary:
        params["withSalary"] = "true"
    return params


def iter_pages(params):
    """Yield (batch, total, is_last) for each page of offers.

    Each batch is a list of (slug, transformed_offer) tuples.
    Caller is responsible for rate-limiting between pages.
    """
    cursor = 0
    while True:
        data = fetch_page(params, cursor)
        raw_offers = data.get("data", [])
        meta = data.get("meta", {})
        total = meta.get("totalItems", 0)

        batch = [(raw.get("slug", ""), transform_offer(raw)) for raw in raw_offers]

        next_info = meta.get("next", {})
        next_cursor = next_info.get("cursor")
        is_last = not raw_offers or next_cursor is None or next_cursor <= cursor

        yield batch, total, is_last

        if is_last:
            break
        cursor = next_cursor


def scrape(args) -> list[dict]:
    """Main scraping logic with pagination."""
    params = build_params(
        city=args.city, category=args.category, experience=args.experience,
        workplace=args.workplace,
        employment=getattr(args, "employment", None),
        working_time=getattr(args, "working_time", None),
        keyword=getattr(args, "keyword", None),
        with_salary=getattr(args, "with_salary", False),
    )

    all_offers = []
    limit = args.limit or float("inf")

    print(f"🔍 Scraping justjoin.it offers...", file=sys.stderr)
    if args.city:
        print(f"   City: {args.city}", file=sys.stderr)
    if args.category:
        print(f"   Category: {args.category}", file=sys.stderr)

    for batch, total, is_last in iter_pages(params):
        for slug, offer in batch:
            if len(all_offers) >= limit:
                break
            all_offers.append((slug, offer))

        target = min(total, int(limit)) if limit != float("inf") else total
        print(f"   Fetched {len(all_offers)}/{target} offers...", file=sys.stderr, end="\r")

        if len(all_offers) >= limit or is_last:
            break
        time.sleep(0.3)

    # Optionally fetch full descriptions
    if getattr(args, "fetch_details", False):
        print(f"\n📝 Fetching offer details...", file=sys.stderr)
        results = []
        for i, (slug, offer) in enumerate(all_offers):
            try:
                body = fetch_detail(slug)
                offer["body"] = body
            except Exception as e:
                print(f"\n   ⚠ Could not fetch {slug}: {e}", file=sys.stderr)
            results.append(offer)
            print(f"   Details {i+1}/{len(all_offers)}...", file=sys.stderr, end="\r")
            time.sleep(0.15)
        print(f"\n✅ Done! Total offers collected: {len(results)}", file=sys.stderr)
        return results

    print(f"\n✅ Done! Total offers collected: {len(all_offers)}", file=sys.stderr)
    return [offer for _, offer in all_offers]
