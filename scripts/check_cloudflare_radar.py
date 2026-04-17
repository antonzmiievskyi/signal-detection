"""
Cloudflare Radar Outage Checker

Checks for network-level Internet outages in countries where target companies operate.
CROC tracks country/ASN-level disruptions, not per-company outages.

Requires: CLOUDFLARE_RADAR_TOKEN environment variable (free API token with Account > Radar > Read).
"""

import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")
BASE_URL = "https://api.cloudflare.com/client/v4/radar"
TOKEN = os.environ.get("CLOUDFLARE_RADAR_TOKEN", "")


def load_companies() -> list[dict]:
    with open(COMPANIES_FILE) as f:
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
    if not TOKEN:
        print("ERROR: Set CLOUDFLARE_RADAR_TOKEN environment variable.")
        print("  Create a free token at https://dash.cloudflare.com/profile/api-tokens")
        print("  Permission needed: Account > Radar > Read")
        sys.exit(1)

    companies = load_companies()

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

    # Check outages per target country
    for country in countries:
        country_companies = [c["company"] for c in companies if c["country"] == country]
        print(f"\n--- Outages in {country} (companies: {', '.join(country_companies)}) ---")

        outages = get_outages(date_range="30d", location=country)
        if not outages:
            print("  No outages detected.")
            continue

        for outage in outages:
            cause = outage.get("outage", {}).get("outageCause", "unknown")
            otype = outage.get("outage", {}).get("outageType", "unknown")
            start = outage.get("startDate", "?")
            end = outage.get("endDate", "ongoing")
            asns = [f"{a['name']} (AS{a['asn']})" for a in outage.get("asnsDetails", [])]
            asn_str = ", ".join(asns) if asns else "N/A"

            print(f"  [{start} -> {end or 'ongoing'}]")
            print(f"    Type: {otype} | Cause: {cause}")
            print(f"    ASNs: {asn_str}")
            if outage.get("description"):
                print(f"    Description: {outage['description']}")
            print()


if __name__ == "__main__":
    main()
