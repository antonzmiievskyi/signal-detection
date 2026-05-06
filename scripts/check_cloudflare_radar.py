"""
Cloudflare Radar Outage Checker

Checks for network-level Internet outages in countries where target companies operate.
CROC tracks country/ASN-level disruptions, not per-company outages.

Requires: CLOUDFLARE_RADAR_TOKEN environment variable (free API token with Account > Radar > Read).
"""

import argparse
import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

try:
    from detect_provider import detect_providers
except ImportError:
    from scripts.detect_provider import detect_providers

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")
BASE_URL = "https://api.cloudflare.com/client/v4/radar"
TOKEN = os.environ.get("CLOUDFLARE_RADAR_TOKEN", "")

# Edge ASNs of providers we can fingerprint via detect_provider.
# Used to attribute country-level Radar outages to companies whose CDN's
# ASN actually appears in the outage's asnsDetails. Country alone is not
# sufficient evidence — most CROC outages are local-ISP, not CDN-edge.
PROVIDER_ASNS: dict[str, set[int]] = {
    "Cloudflare": {13335},
    "Akamai": {16625, 20940, 21342, 21357, 35994},
    "F5": {35260, 47217},
    "Imperva": {19551, 26944},
}


def load_companies(path: str | None = None) -> list[dict]:
    with open(path if path is not None else COMPANIES_FILE) as f:
        return json.load(f)


def get_outages(date_range: str = "30d", location: str | None = None, limit: int = 100) -> list[dict]:
    """Fetch outages from Cloudflare Radar CROC."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    params = {"dateRange": date_range, "format": "json", "limit": limit}
    if location:
        params["location"] = location

    resp = requests.get(f"{BASE_URL}/annotations/outages", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", {}).get("annotations", [])


def get_outage_counts_by_location(date_range: str = "30d") -> list[dict]:
    """Get outage counts per country."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    params = {"dateRange": date_range, "format": "json"}

    resp = requests.get(f"{BASE_URL}/annotations/outages/locations", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", {}).get("annotations", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", default=COMPANIES_FILE, help="Path to companies JSON file")
    args = parser.parse_args()

    if not TOKEN:
        print("ERROR: Set CLOUDFLARE_RADAR_TOKEN environment variable.")
        print("  Create a free token at https://dash.cloudflare.com/profile/api-tokens")
        print("  Permission needed: Account > Radar > Read")
        sys.exit(1)

    companies = load_companies(args.companies)

    # Get unique countries from company list
    countries = sorted(set(c["country"] for c in companies))
    print(f"Checking Cloudflare Radar outages for countries: {', '.join(countries)}")
    print(f"Date range: last 30 days")
    print("=" * 70)

    # Check outage counts by location first
    print("\n--- Global Outage Counts (top affected countries, last 30 days) ---")
    location_counts = get_outage_counts_by_location("30d")
    location_counts.sort(key=lambda x: int(x.get("value", 0)), reverse=True)
    for loc in location_counts[:20]:
        marker = " <-- TARGET" if loc["clientCountryAlpha2"] in countries else ""
        print(f"  {loc['clientCountryAlpha2']} ({loc['clientCountryName']}): {loc['value']} outages{marker}")

    # Per-country outage detail + ASN collection for downstream attribution.
    country_outage_asns: dict[str, set[int]] = {}
    affected_countries: list[str] = []

    for country in countries:
        country_companies = [c["company"] for c in companies if c["country"] == country]
        print(f"\n--- Outages in {country} (companies: {', '.join(country_companies)}) ---")

        outages = get_outages(date_range="30d", location=country)
        if not outages:
            print("  No outages detected.")
            continue

        affected_countries.append(country)
        asns_for_country: set[int] = set()

        for outage in outages:
            cause = outage.get("outage", {}).get("outageCause", "unknown")
            otype = outage.get("outage", {}).get("outageType", "unknown")
            start = outage.get("startDate", "?")
            end = outage.get("endDate", "ongoing")
            asn_details = outage.get("asnsDetails", [])
            asns = [f"{a['name']} (AS{a['asn']})" for a in asn_details]
            asn_str = ", ".join(asns) if asns else "N/A"

            for a in asn_details:
                try:
                    asns_for_country.add(int(a["asn"]))
                except (KeyError, TypeError, ValueError):
                    pass

            print(f"  [{start} -> {end or 'ongoing'}]")
            print(f"    Type: {otype} | Cause: {cause}")
            print(f"    ASNs: {asn_str}")
            if outage.get("description"):
                print(f"    Description: {outage['description']}")
            print()

        country_outage_asns[country] = asns_for_country

    # Per-company attribution: a company is "affected" only when its country
    # had a Radar outage AND its detected CDN's ASN appears in that outage's
    # asnsDetails. Country alone is too coarse (most CROC events are local-
    # ISP outages that don't impact a globally-hosted SaaS).
    print(f"\n{'='*70}")
    print("  PER-COMPANY ATTRIBUTION")
    print(f"{'='*70}")
    domain_to_provider = detect_providers([c["domain"] for c in companies])
    affected: list[str] = []
    for c in companies:
        country = c["country"]
        prov = domain_to_provider.get(c["domain"])
        outage_asns = country_outage_asns.get(country, set())
        provider_asns = PROVIDER_ASNS.get(prov or "", set())
        is_affected = bool(outage_asns and provider_asns & outage_asns)
        marker = "AFFECTED" if is_affected else (
            "ctx" if country in affected_countries else "ok"
        )
        print(
            f"  [{marker:<8}] {c['company']:<30} {country:<3} "
            f"provider={prov or '-':<11} outage_asns={sorted(outage_asns) or '-'}"
        )
        if is_affected:
            affected.append(c["company"])

    # Machine-readable summary lines for run_all.py to parse.
    print()
    print(f"RADAR_AFFECTED_COUNTRIES: {','.join(affected_countries)}")
    print(f"AFFECTED_COMPANIES_RADAR: {','.join(affected)}")


if __name__ == "__main__":
    main()
