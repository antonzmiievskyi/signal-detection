"""
Tranco List Domain Ranking Checker

Looks up domain rankings for target companies to validate they are significant
web properties and track rank changes over time.

No authentication required for basic lookups.
"""

import json
import os
import sys
import time

import requests

COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")
TRANCO_API = "https://tranco-list.eu/api"


def load_companies() -> list[dict]:
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def get_domain_ranks(domain: str) -> list[dict]:
    """Get rank history for a domain over the past 30+ days.

    Rate limit: 1 query/second.
    """
    resp = requests.get(f"{TRANCO_API}/ranks/domain/{domain}", timeout=15)
    resp.raise_for_status()
    return resp.json().get("ranks", [])


def get_latest_list_metadata() -> dict:
    """Get metadata for the latest daily list."""
    resp = requests.get(f"{TRANCO_API}/lists/date/latest", timeout=15)
    resp.raise_for_status()
    return resp.json()


def analyze_rank_trend(ranks: list[dict]) -> dict:
    """Analyze rank trend for significant changes."""
    if not ranks:
        return {"status": "no_data"}

    # Sort by date
    ranks_sorted = sorted(ranks, key=lambda x: x["date"])
    current_rank = ranks_sorted[-1]["rank"]
    oldest_rank = ranks_sorted[0]["rank"]

    # Calculate stats
    all_ranks = [r["rank"] for r in ranks_sorted]
    avg_rank = sum(all_ranks) / len(all_ranks)
    min_rank = min(all_ranks)  # best position
    max_rank = max(all_ranks)  # worst position

    # Detect significant changes (>20% rank shift)
    change = current_rank - oldest_rank
    pct_change = (change / oldest_rank * 100) if oldest_rank > 0 else 0

    return {
        "status": "ranked",
        "current_rank": current_rank,
        "oldest_rank": oldest_rank,
        "avg_rank": round(avg_rank),
        "best_rank": min_rank,
        "worst_rank": max_rank,
        "change": change,
        "pct_change": round(pct_change, 1),
        "data_points": len(ranks_sorted),
        "date_range": f"{ranks_sorted[0]['date']} to {ranks_sorted[-1]['date']}",
    }


def main():
    companies = load_companies()
    print("Tranco List Domain Ranking Checker")
    print(f"Checking {len(companies)} companies")
    print("=" * 70)

    # Get latest list info
    try:
        list_meta = get_latest_list_metadata()
        print(f"Latest list ID: {list_meta.get('list_id', 'N/A')}")
        print(f"Created: {list_meta.get('created_on', 'N/A')}")
    except requests.RequestException as e:
        print(f"Warning: Could not fetch list metadata: {e}")

    print(f"\n{'Company':<25} {'Domain':<25} {'Rank':>8} {'Change':>8} {'Trend':>8}")
    print("-" * 80)

    results = []
    for i, company in enumerate(companies):
        domain = company["domain"]
        name = company["company"]

        try:
            ranks = get_domain_ranks(domain)
            analysis = analyze_rank_trend(ranks)

            if analysis["status"] == "no_data":
                print(f"{name:<25} {domain:<25} {'N/A':>8} {'N/A':>8} {'N/A':>8}")
                results.append({"company": name, "domain": domain, "status": "not_ranked"})
            else:
                rank = analysis["current_rank"]
                change = analysis["change"]
                pct = analysis["pct_change"]

                # Trend indicator
                if abs(pct) < 5:
                    trend = "stable"
                elif change < 0:
                    trend = "UP"  # rank number decreased = improved
                else:
                    trend = "DOWN"  # rank number increased = dropped

                change_str = f"{change:+d}" if change != 0 else "0"
                print(f"{name:<25} {domain:<25} {rank:>8,} {change_str:>8} {trend:>8}")

                results.append({
                    "company": name,
                    "domain": domain,
                    "status": "ranked",
                    **analysis,
                })

        except requests.RequestException as e:
            print(f"{name:<25} {domain:<25} {'ERROR':>8}")
            results.append({"company": name, "domain": domain, "status": "error", "error": str(e)})

        # Rate limit: 1 query/second
        if i < len(companies) - 1:
            time.sleep(1.1)

    # Summary
    ranked = [r for r in results if r["status"] == "ranked"]
    not_ranked = [r for r in results if r["status"] == "not_ranked"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"\n{'='*70}")
    print(f"Summary: {len(ranked)} ranked, {len(not_ranked)} not in top 1M, {len(errors)} errors")

    if ranked:
        top = min(ranked, key=lambda r: r["current_rank"])
        print(f"Highest ranked: {top['company']} ({top['domain']}) at #{top['current_rank']:,}")

    # Flag significant drops
    drops = [r for r in ranked if r.get("pct_change", 0) > 20]
    if drops:
        print(f"\nWARNING: Significant rank drops detected:")
        for d in drops:
            print(f"  {d['company']}: {d['pct_change']:+.1f}% ({d['oldest_rank']:,} -> {d['current_rank']:,})")


if __name__ == "__main__":
    main()
