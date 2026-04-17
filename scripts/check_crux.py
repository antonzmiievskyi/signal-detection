"""
CrUX (Chrome User Experience Report) Performance Checker

Checks real-user performance metrics for target company domains.
Uses the free CrUX API (150 queries/min).

NOTE: CrUX is NOT suitable for outage detection (28-day rolling average).
It's useful for assessing general site performance quality.

Requires: CRUX_API_KEY environment variable (free Google Cloud API key).
"""

import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")
CRUX_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
CRUX_HISTORY_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"
API_KEY = os.environ.get("CRUX_API_KEY", "")

# Core Web Vitals thresholds
THRESHOLDS = {
    "largest_contentful_paint": {"good": 2500, "poor": 4000, "unit": "ms"},
    "interaction_to_next_paint": {"good": 200, "poor": 500, "unit": "ms"},
    "cumulative_layout_shift": {"good": 0.1, "poor": 0.25, "unit": ""},
    "first_contentful_paint": {"good": 1800, "poor": 3000, "unit": "ms"},
    "experimental_time_to_first_byte": {"good": 800, "poor": 1800, "unit": "ms"},
}


def load_companies() -> list[dict]:
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def get_crux_metrics(origin: str, form_factor: str | None = None) -> dict | None:
    """Query CrUX API for an origin's performance metrics."""
    url = f"{CRUX_ENDPOINT}?key={API_KEY}"
    body = {"origin": origin}
    if form_factor:
        body["formFactor"] = form_factor

    resp = requests.post(url, json=body, timeout=15)
    if resp.status_code == 404:
        return None  # Origin not in CrUX dataset
    resp.raise_for_status()
    return resp.json()


def get_crux_history(origin: str) -> dict | None:
    """Query CrUX History API for trend data."""
    url = f"{CRUX_HISTORY_ENDPOINT}?key={API_KEY}"
    body = {"origin": origin}

    resp = requests.post(url, json=body, timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def rate_metric(metric_name: str, p75_value: float) -> str:
    """Rate a metric p75 value as good/needs-improvement/poor."""
    if metric_name not in THRESHOLDS:
        return "unknown"
    t = THRESHOLDS[metric_name]
    if p75_value <= t["good"]:
        return "GOOD"
    elif p75_value <= t["poor"]:
        return "NEEDS WORK"
    else:
        return "POOR"


def format_metric_value(metric_name: str, value: float) -> str:
    """Format a metric value with unit."""
    unit = THRESHOLDS.get(metric_name, {}).get("unit", "")
    if metric_name == "cumulative_layout_shift":
        return f"{value:.3f}"
    return f"{value:.0f}{unit}"


def main():
    if not API_KEY:
        print("ERROR: Set CRUX_API_KEY environment variable.")
        print("  Get a free API key at https://console.cloud.google.com/apis/credentials")
        print("  Enable the 'Chrome UX Report API'")
        sys.exit(1)

    companies = load_companies()
    print("CrUX Performance Checker")
    print(f"Checking {len(companies)} companies")
    print()
    print("NOTE: CrUX uses a 28-day rolling average. Not suitable for outage detection.")
    print("      This shows general site performance quality.")
    print("=" * 70)

    metrics_to_check = [
        "largest_contentful_paint",
        "interaction_to_next_paint",
        "cumulative_layout_shift",
        "experimental_time_to_first_byte",
    ]
    short_names = {"largest_contentful_paint": "LCP", "interaction_to_next_paint": "INP",
                   "cumulative_layout_shift": "CLS", "experimental_time_to_first_byte": "TTFB"}

    results = []

    for company in companies:
        domain = company["domain"]
        name = company["company"]
        origin = f"https://{domain}"

        print(f"\n--- {name} ({domain}) ---")

        try:
            data = get_crux_metrics(origin)
            if data is None:
                # Try with www. prefix — CrUX often indexes that instead
                origin_www = f"https://www.{domain}"
                data = get_crux_metrics(origin_www)
                if data is not None:
                    origin = origin_www
            if data is None:
                print("  Not in CrUX dataset (insufficient traffic or not indexed)")
                results.append({"company": name, "domain": domain, "status": "not_found"})
                continue

            record = data.get("record", {})
            metrics = record.get("metrics", {})
            period = record.get("collectionPeriod", {})

            # Show collection period
            first = period.get("firstDate", {})
            last = period.get("lastDate", {})
            if first and last:
                print(f"  Collection period: {first.get('year')}-{first.get('month'):02d}-{first.get('day'):02d}"
                      f" to {last.get('year')}-{last.get('month'):02d}-{last.get('day'):02d}")

            company_result = {"company": name, "domain": domain, "status": "ok", "metrics": {}}

            for metric_key in metrics_to_check:
                if metric_key not in metrics:
                    continue

                metric_data = metrics[metric_key]
                p75 = metric_data.get("percentiles", {}).get("p75")
                if p75 is None:
                    continue

                # For CLS, p75 is a string like "0.05"
                p75_val = float(p75) if isinstance(p75, str) else p75
                rating = rate_metric(metric_key, p75_val)
                formatted = format_metric_value(metric_key, p75_val)
                short = short_names.get(metric_key, metric_key)

                # Distribution
                histogram = metric_data.get("histogram", [])
                good_pct = histogram[0]["density"] * 100 if histogram else 0

                print(f"  {short:>5}: p75={formatted:<10} [{rating}]  ({good_pct:.0f}% good)")

                company_result["metrics"][short] = {
                    "p75": p75_val,
                    "rating": rating,
                    "good_pct": round(good_pct, 1),
                }

            results.append(company_result)

        except requests.RequestException as e:
            print(f"  ERROR: {e}")
            results.append({"company": name, "domain": domain, "status": "error", "error": str(e)})

    # Summary
    print(f"\n{'='*70}")
    print("Summary:")
    found = [r for r in results if r["status"] == "ok"]
    not_found = [r for r in results if r["status"] == "not_found"]
    print(f"  In CrUX: {len(found)} | Not found: {len(not_found)}")

    # Flag poorly performing sites
    poor_sites = []
    for r in found:
        poor_metrics = [k for k, v in r.get("metrics", {}).items() if v.get("rating") == "POOR"]
        if poor_metrics:
            poor_sites.append((r["company"], poor_metrics))

    if poor_sites:
        print("\n  Sites with POOR metrics:")
        for company, metrics in poor_sites:
            print(f"    {company}: {', '.join(metrics)}")


if __name__ == "__main__":
    main()
