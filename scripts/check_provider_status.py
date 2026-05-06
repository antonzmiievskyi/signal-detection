"""
Provider Status Page Checker

Polls Akamai, Cloudflare, F5, and Imperva status pages for recent incidents.
All use Atlassian Statuspage API (no auth required).

These show PROVIDER-level outages. Cross-reference with which companies use which provider.
"""

import argparse
import json
import os
from datetime import datetime, timezone

import requests

try:
    from detect_provider import detect_providers  # script-style execution
except ImportError:  # imported as scripts.check_provider_status (e.g. by pytest)
    from scripts.detect_provider import detect_providers

COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")

PROVIDERS = {
    "Cloudflare": "https://www.cloudflarestatus.com",
    "Akamai": "https://www.akamaistatus.com",
    "F5": "https://www.f5cloudstatus.com",
    "Imperva": "https://status.imperva.com",
}


def load_companies(path: str | None = None) -> list[dict]:
    with open(path if path is not None else COMPANIES_FILE) as f:
        return json.load(f)


def get_status(base_url: str) -> dict:
    """Get overall status indicator."""
    resp = requests.get(f"{base_url}/api/v2/status.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["status"]


def get_incidents(base_url: str) -> list[dict]:
    """Get 50 most recent incidents."""
    resp = requests.get(f"{base_url}/api/v2/incidents.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["incidents"]


def get_unresolved(base_url: str) -> list[dict]:
    """Get currently unresolved incidents."""
    resp = requests.get(f"{base_url}/api/v2/incidents/unresolved.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["incidents"]


def get_components(base_url: str) -> list[dict]:
    """Get all components with current status."""
    resp = requests.get(f"{base_url}/api/v2/components.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["components"]


def format_incident(inc: dict) -> str:
    """Format a single incident for display."""
    status = inc["status"]
    impact = inc["impact"]
    name = inc["name"]
    created = inc["created_at"][:16].replace("T", " ")
    resolved = inc.get("resolved_at")
    resolved_str = resolved[:16].replace("T", " ") if resolved else "ONGOING"

    components = [c["name"] for c in inc.get("components", [])]
    comp_str = ", ".join(components) if components else "N/A"

    lines = [
        f"  [{impact.upper()}] {name}",
        f"    Status: {status} | Created: {created} | Resolved: {resolved_str}",
        f"    Components: {comp_str}",
    ]

    # Show latest update
    updates = inc.get("incident_updates", [])
    if updates:
        latest = updates[0]
        body = latest["body"][:200] if latest.get("body") else ""
        if body:
            lines.append(f"    Latest update: {body}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", default=COMPANIES_FILE, help="Path to companies JSON file")
    args = parser.parse_args()

    companies = load_companies(args.companies)
    print("Provider Status Page Checker")
    print(f"Companies monitored: {', '.join(c['company'] for c in companies)}")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    providers_with_incidents: set[str] = set()

    for provider, base_url in PROVIDERS.items():
        print(f"\n{'='*70}")
        print(f"  {provider.upper()}")
        print(f"  {base_url}")
        print(f"{'='*70}")

        try:
            # Overall status
            status = get_status(base_url)
            indicator = status["indicator"]
            description = status["description"]
            status_icon = {"none": "OK", "minor": "MINOR", "major": "MAJOR", "critical": "CRITICAL"}
            print(f"\n  Overall: [{status_icon.get(indicator, indicator)}] {description}")

            # Degraded components
            components = get_components(base_url)
            degraded = [c for c in components if c["status"] != "operational" and not c.get("group")]
            if degraded:
                print(f"\n  Degraded components ({len(degraded)}):")
                for c in degraded:
                    print(f"    - {c['name']}: {c['status']}")

            # Unresolved incidents
            unresolved = get_unresolved(base_url)
            if unresolved:
                providers_with_incidents.add(provider)
                print(f"\n  ACTIVE INCIDENTS ({len(unresolved)}):")
                for inc in unresolved:
                    print(format_incident(inc))
                    print()
            else:
                print("\n  No active incidents.")

            # Recent resolved incidents (last 10)
            incidents = get_incidents(base_url)
            resolved = [i for i in incidents if i["status"] == "resolved"][:10]
            if resolved:
                print(f"\n  Recent resolved incidents (last {len(resolved)}):")
                for inc in resolved:
                    print(format_incident(inc))
                    print()

        except requests.RequestException as e:
            print(f"\n  ERROR fetching {provider}: {e}")

    # Per-company attribution: which monitored companies sit on a provider
    # that currently has an unresolved incident? This is what should drive
    # per-company outage flags downstream.
    print(f"\n{'='*70}")
    print("  PER-COMPANY ATTRIBUTION")
    print(f"{'='*70}")
    domain_to_provider = detect_providers([c["domain"] for c in companies])
    affected: list[str] = []
    for c in companies:
        prov = domain_to_provider.get(c["domain"])
        is_affected = prov is not None and prov in providers_with_incidents
        marker = "AFFECTED" if is_affected else ("ok" if prov else "?")
        print(f"  [{marker:<8}] {c['company']:<30} {c['domain']:<35} provider={prov or '-'}")
        if is_affected:
            affected.append(c["company"])

    # Machine-readable summary lines for run_all.py to parse.
    # Keep these on dedicated lines, no wrapping, comma-separated.
    print()
    print(f"PROVIDERS_WITH_INCIDENTS: {','.join(sorted(providers_with_incidents))}")
    print(f"AFFECTED_COMPANIES: {','.join(affected)}")


if __name__ == "__main__":
    main()
