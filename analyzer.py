#!/usr/bin/env python3
"""
IT Offers Salary Analyzer
=========================
Analyzes salary data from scraped job offers.
Shows median salary range and percentile distribution.

Usage:
    python analyzer.py offers.json
    python analyzer.py offers.json --type b2b
    python analyzer.py offers.json --type permanent
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter

PERCENTILES = [10, 25, 50, 70, 80, 90]

KEYWORDS_VACATION = [
    "urlop", "vacation", "paid leave", "paid time off", "pto",
    "days off", "paid days off", "annual leave",
    "płatne dni", "platne dni", "paid day", "unlimited pto",
    "unlimited vacation",
]
KEYWORDS_SICK = [
    "l4", "sick leave", "sick day", "chorobow", "zwolnienie lekarskie",
    "paid sick", "health day", "wellness day", "recovery day",
    "family friendly leave", "medical leave",
]
KEYWORDS_EXTRA_BENEFITS = [
    "kafeteria", "kafeteryjny", "mybenefit", "wellbeing", "wellness",
    "budget for development", "budżet rozwoj", "budżet szkoleniow",
    "unlimited pto", "unlimited vacation",
]


def normalize_monthly(salary: float) -> float:
    """Convert salary to monthly equivalent based on magnitude heuristic.

    The API unit field is unreliable (sometimes swapped), so we detect
    the rate type by the value itself:
      < 500        → hourly rate   → * 168 (21 days * 8h)
      500 – 1500   → daily rate    → * 21
      1500 – 100k  → monthly       → as-is
      > 100k       → yearly        → / 12
    """
    if salary < 500:
        return salary * 168
    if salary < 1500:
        return salary * 21
    if salary > 100_000:
        return salary / 12
    return salary


def extract_salaries(offers: list[dict], employment_type: str | None = None) -> list[tuple[float, float, dict]]:
    """Extract (salary_from, salary_to, offer) tuples normalized to monthly PLN."""
    salaries = []
    for offer in offers:
        for et in offer.get("employment_types", []):
            if employment_type and et.get("type") != employment_type:
                continue
            sfrom = et.get("salary_from")
            sto = et.get("salary_to")
            if sfrom is None or sto is None:
                continue
            low = normalize_monthly(sfrom)
            high = normalize_monthly(sto)
            salaries.append((low, high, offer))
            break  # one match per offer is enough
    return salaries


def detect_outliers(salaries: list[tuple[float, float, dict]]) -> tuple[list[tuple[float, float, dict]], list[tuple[float, float, dict]]]:
    """Split salaries into (clean, outliers) using IQR method.

    An offer is an outlier if its midpoint falls outside Q1 - 1.5*IQR .. Q3 + 1.5*IQR.
    """
    if len(salaries) < 4:
        return salaries, []

    midpoints = sorted((low + high) / 2 for low, high, _ in salaries)
    q1 = percentile(midpoints, 25)
    q3 = percentile(midpoints, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    clean, outliers = [], []
    for low, high, offer in salaries:
        mid = (low + high) / 2
        if mid < lower_bound or mid > upper_bound:
            outliers.append((low, high, offer))
        else:
            clean.append((low, high, offer))
    return clean, outliers


def percentile(sorted_values: list[float], p: int) -> float:
    """Calculate the p-th percentile of a sorted list."""
    n = len(sorted_values)
    k = (p / 100) * (n - 1)
    f = int(k)
    c = k - f
    if f + 1 < n:
        return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
    return sorted_values[f]


def fmt(val: float) -> str:
    """Format salary as a readable string."""
    return f"{val:,.0f} PLN"


def print_outliers(outliers: list[tuple[float, float, dict]]):
    """Print detected outlier offers."""
    if not outliers:
        return
    print(f"\n  ⚠ Detected outliers ({len(outliers)}):")
    print(f"  {'Mid':>10}  {'From':>10}  {'To':>10}  {'Company':<30}  Title")
    print(f"  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 30}  {'-' * 30}")
    for low, high, offer in sorted(outliers, key=lambda x: (x[0]+x[1])/2, reverse=True):
        mid = (low + high) / 2
        print(f"  {fmt(mid):>10}  {fmt(low):>10}  {fmt(high):>10}  {offer['company_name']:<30}  {offer['title']}")


def print_top_companies(salaries: list[tuple[float, float, dict]], p90_val: float):
    """Print offers above P90 grouped by company."""
    above = [(low, high, offer) for low, high, offer in salaries if (low + high) / 2 > p90_val]
    if not above:
        return
    above.sort(key=lambda x: (x[0] + x[1]) / 2, reverse=True)

    # Count per company
    company_counts = Counter(o["company_name"] for _, _, o in above)

    print(f"\n  Companies with offers > P90 ({fmt(p90_val)}):")
    print(f"  {'Company':<35}  {'Offers':>6}  {'Min mid':>12}  {'Max mid':>12}")
    print(f"  {'-' * 35}  {'-' * 6}  {'-' * 12}  {'-' * 12}")
    for company, count in company_counts.most_common():
        mids = [(low + high) / 2 for low, high, o in above if o["company_name"] == company]
        print(f"  {company:<35}  {count:>6}  {fmt(min(mids)):>12}  {fmt(max(mids)):>12}")

    print(f"\n  Offer details > P90:")
    print(f"  {'Mid':>10}  {'From':>10}  {'To':>10}  {'Company':<30}  Title")
    print(f"  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 30}  {'-' * 30}")
    for low, high, offer in above:
        mid = (low + high) / 2
        print(f"  {fmt(mid):>10}  {fmt(low):>10}  {fmt(high):>10}  {offer['company_name']:<30}  {offer['title']}")


def print_report(salaries: list[tuple[float, float, dict]], employment_type: str | None, total_offers: int, exclude_outliers: bool = False, show_top: bool = False):
    """Print salary analysis report."""
    if not salaries:
        print("No offers with salary data.")
        return

    clean, outliers = detect_outliers(salaries)
    active = clean if exclude_outliers else salaries

    midpoints = sorted([(low + high) / 2 for low, high, _ in active])
    lows = sorted([low for low, _, _ in active])
    highs = sorted([high for _, high, _ in active])

    label = employment_type.upper() if employment_type else "all types"
    print(f"\n{'=' * 60}")
    print(f"  Salary Analysis — {label}")
    print(f"{'=' * 60}")
    mode = " (excluding outliers)" if exclude_outliers else ""
    print(f"  Total offers:          {total_offers}")
    print(f"  Offers with salary:    {len(salaries)}")
    print(f"  Outliers:              {len(outliers)}{mode}")
    print(f"  Without salary data:   {total_offers - len(salaries)}")

    print(f"\n  Median salary range:")
    med_low = statistics.median(lows)
    med_high = statistics.median(highs)
    med_mid = statistics.median(midpoints)
    print(f"    Lower bound:         {fmt(med_low)}")
    print(f"    Upper bound:         {fmt(med_high)}")
    print(f"    Mid-range:           {fmt(med_mid)}")

    print(f"\n  Average salary range:")
    avg_low = statistics.mean(lows)
    avg_high = statistics.mean(highs)
    print(f"    Lower bound:         {fmt(avg_low)}")
    print(f"    Upper bound:         {fmt(avg_high)}")

    print(f"\n  Percentiles (mid-range):")
    print(f"  {'Percentile':>12}  {'Amount':>14}  {'Offers below':>14}")
    print(f"  {'-' * 12}  {'-' * 14}  {'-' * 14}")
    for p in PERCENTILES:
        val = percentile(midpoints, p)
        count_below = sum(1 for m in midpoints if m <= val)
        print(f"  {p:>11}%  {fmt(val):>14}  {count_below:>14}")

    print(f"\n  Salary distribution (brackets):")
    # Build salary brackets dynamically from percentiles
    p10 = percentile(midpoints, 10)
    p25 = percentile(midpoints, 25)
    p50 = percentile(midpoints, 50)
    p75 = percentile(midpoints, 75)
    p90 = percentile(midpoints, 90)

    brackets = [
        (0, p10, "below P10"),
        (p10, p25, "P10–P25"),
        (p25, p50, "P25–P50"),
        (p50, p75, "P50–P75"),
        (p75, p90, "P75–P90"),
        (p90, float("inf"), "above P90"),
    ]

    max_bar = 30
    total = len(midpoints)
    print(f"  {'Bracket':>16}  {'Range':>28}  {'Offers':>6}  {'%':>5}  Chart")
    print(f"  {'-' * 16}  {'-' * 28}  {'-' * 6}  {'-' * 5}  {'-' * max_bar}")
    for lo, hi, label in brackets:
        count = sum(1 for m in midpoints if lo < m <= hi) if lo > 0 else sum(1 for m in midpoints if m <= hi)
        pct = count / total * 100
        bar_len = int(pct / 100 * max_bar)
        hi_str = fmt(hi) if hi != float("inf") else "∞"
        range_str = f"{fmt(lo)} – {hi_str}"
        print(f"  {label:>16}  {range_str:>28}  {count:>6}  {pct:>4.1f}%  {'█' * bar_len}")

    if show_top:
        print_top_companies(active, p90)

    print_outliers(outliers)
    print(f"\n{'=' * 60}\n")


def strip_html(html: str) -> str:
    """Strip HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return text.lower()


def search_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords appear in text."""
    return [k for k in keywords if k in text]


def print_benefits(offers: list[dict], employment_type: str | None):
    """Analyze and print B2B benefits (paid vacation, sick leave)."""
    # Check if body data is available
    has_body = sum(1 for o in offers if o.get("body"))
    if has_body == 0:
        print("⚠ No offer description data. Use --fetch-details in scraper.")
        return

    b2b_offers = []
    for offer in offers:
        has_b2b = any(et.get("type") == "b2b" for et in offer.get("employment_types", []))
        if employment_type and employment_type != "b2b":
            has_b2b = any(et.get("type") == employment_type for et in offer.get("employment_types", []))
        if not has_b2b:
            continue
        b2b_offers.append(offer)

    with_vacation = []
    with_sick = []
    with_extra = []
    with_any = []

    with_body = [o for o in b2b_offers if o.get("body")]
    for offer in with_body:
        text = strip_html(offer["body"])
        vac = search_keywords(text, KEYWORDS_VACATION)
        sick = search_keywords(text, KEYWORDS_SICK)
        extra = search_keywords(text, KEYWORDS_EXTRA_BENEFITS)
        if vac:
            with_vacation.append((offer, vac))
        if sick:
            with_sick.append((offer, sick))
        if extra:
            with_extra.append((offer, extra))
        if vac or sick or extra:
            with_any.append((offer, vac, sick, extra))

    total = len(with_body)
    pct = lambda n: f"{n} ({n/total*100:.1f}%)" if total else "0"

    print(f"\n{'=' * 60}")
    print(f"  B2B Benefits Analysis")
    print(f"{'=' * 60}")
    print(f"  B2B offers with desc:  {total}")
    print(f"  Mentions vacation:     {pct(len(with_vacation))}")
    print(f"  Mentions sick leave:   {pct(len(with_sick))}")
    print(f"  Cafeteria/extras:      {pct(len(with_extra))}")
    print(f"  Any of above:          {pct(len(with_any))}")

    if with_any:
        print(f"\n  B2B offers with benefits:")
        print(f"  {'Company':<30}  {'Vacation':<16}  {'Sick leave':<16}  {'Extras':<16}  Title")
        print(f"  {'-' * 30}  {'-' * 16}  {'-' * 16}  {'-' * 16}  {'-' * 30}")
        for offer, vac, sick, extra in with_any:
            vac_str = ", ".join(vac) if vac else "-"
            sick_str = ", ".join(sick) if sick else "-"
            extra_str = ", ".join(extra) if extra else "-"
            print(f"  {offer['company_name']:<30}  {vac_str:<16}  {sick_str:<16}  {extra_str:<16}  {offer['title']}")

    print(f"\n{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="IT job offers salary analysis")
    parser.add_argument("file", help="JSON file with offers (scraper output)")
    parser.add_argument(
        "--type", "-t",
        choices=["b2b", "permanent", "mandate", "internship"],
        default=None,
        help="Filter by employment type (default: all)",
    )

    parser.add_argument(
        "--exclude-outliers", "-x",
        action="store_true",
        help="Exclude outliers (IQR) from analysis",
    )
    parser.add_argument(
        "--show-top",
        action="store_true",
        help="Show companies with offers above P90",
    )
    parser.add_argument(
        "--benefits",
        action="store_true",
        help="B2B benefits analysis (paid vacation, sick leave). Requires --fetch-details in scraper",
    )

    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as f:
        offers = json.load(f)

    salaries = extract_salaries(offers, args.type)
    print_report(salaries, args.type, len(offers), args.exclude_outliers, args.show_top)

    if args.benefits:
        print_benefits(offers, args.type)


if __name__ == "__main__":
    main()
