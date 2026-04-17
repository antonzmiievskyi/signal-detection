"""
Signal Analyzer — Cross-vendor report comparison and signal extraction.

Reads all results from the results/ folder, cross-references data from
different vendors, and uses OpenAI to produce a clear signal report
with actionable outreach opportunities.

Requires: OPENAI_API_KEY environment variable.
"""

import json
import os
import sys
from datetime import datetime, timezone

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def load_companies() -> list[dict]:
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def load_result(filename: str) -> str | None:
    """Load a result file, return contents or None if missing."""
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read()


def build_cross_reference(companies: list[dict], results: dict[str, str]) -> str:
    """Build a per-company cross-reference table from all vendor results."""
    lines = []
    lines.append("=" * 70)
    lines.append("CROSS-REFERENCE: Per-Company Signal Summary")
    lines.append("=" * 70)

    for company in companies:
        name = company["company"]
        domain = company["domain"]
        country = company["country"]
        lines.append(f"\n--- {name} ({domain}, {country}) ---")

        # Tranco ranking
        tranco = results.get("tranco", "")
        for line in tranco.split("\n"):
            if name in line and ("ranked" in line.lower() or domain in line):
                lines.append(f"  Tranco: {line.strip()}")
                break

        # Cloudflare Radar (country-level)
        radar = results.get("cloudflare_radar", "")
        if f"Outages in {country}" in radar:
            # Extract the section for this country
            start = radar.index(f"Outages in {country}")
            end = radar.find("\n---", start + 1)
            section = radar[start:end] if end != -1 else radar[start:]
            if "No outages detected" in section:
                lines.append(f"  CF Radar ({country}): No network outages")
            else:
                outage_lines = [l.strip() for l in section.split("\n") if l.strip() and not l.startswith("---")]
                lines.append(f"  CF Radar ({country}): {'; '.join(outage_lines[:3])}")

        # Provider status (check all 4)
        provider = results.get("provider_status", "")
        active_issues = []
        for prov_name in ["CLOUDFLARE", "AKAMAI", "F5", "IMPERVA"]:
            if f"  {prov_name}" in provider:
                start = provider.index(f"  {prov_name}")
                next_section = provider.find("=" * 70, start + 10)
                section = provider[start:next_section] if next_section != -1 else provider[start:]
                if "ACTIVE INCIDENTS" in section:
                    active_issues.append(prov_name)
        if active_issues:
            lines.append(f"  Provider issues: Active incidents at {', '.join(active_issues)}")
        else:
            lines.append(f"  Provider issues: All providers operational")

        # Downdetector (Apify only)
        dd = results.get("downdetector_apify", "")
        slug = company.get("downdetector_slug", "")
        if dd and slug and slug in dd:
            for line in dd.split("\n"):
                if slug in line and ("OUTAGE" in line or "No problems" in line or "BLOCKED" in line or "ERROR" in line):
                    lines.append(f"  Downdetector: {line.strip()}")
                    break

        # CrUX performance — match section header "--- {name} (" to avoid summary false positives
        crux = results.get("crux", "")
        section_header = f"--- {name} ("
        if section_header in crux:
            start = crux.index(section_header)
            end = crux.find("\n---", start + 1)
            section = crux[start:end] if end != -1 else crux[start:]
            poor = [l.strip() for l in section.split("\n") if "POOR" in l and "p75=" in l]
            needs_work = [l.strip() for l in section.split("\n") if "NEEDS WORK" in l and "p75=" in l]
            if poor:
                lines.append(f"  CrUX: POOR metrics: {'; '.join(poor)}")
            elif needs_work:
                lines.append(f"  CrUX: Some metrics need work ({len(needs_work)} metrics)")
            else:
                lines.append(f"  CrUX: All metrics GOOD")

    return "\n".join(lines)


def analyze_with_openai(companies_json: str, cross_ref: str, raw_results: dict[str, str]) -> str:
    """Send all data to OpenAI for signal analysis."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build the raw data section (truncate each to avoid token limits)
    raw_sections = []
    for name, content in raw_results.items():
        if content:
            truncated = content[:3000] if len(content) > 3000 else content
            raw_sections.append(f"### {name}\n{truncated}")
    raw_data = "\n\n".join(raw_sections)

    prompt = f"""You are a sales intelligence analyst for a cybersecurity/CDN company.
Analyze the following data from multiple monitoring sources to identify **sales signals** —
companies that are experiencing or recently experienced service issues, making them
potential prospects for outreach.

## Target Companies
{companies_json}

## Cross-Reference Summary (all vendors combined per company)
{cross_ref}

## Raw Data from Each Vendor
{raw_data}

## Your Task

Produce a structured report with these sections:

### 1. Signal Strength Rating
For each company, rate the signal strength (STRONG / MODERATE / WEAK / NONE):
- STRONG: Multiple sources confirm issues (e.g., Downdetector outage + provider incident + poor CrUX)
- MODERATE: One source shows issues with supporting evidence
- WEAK: Minor indicators only
- NONE: No issues detected

### 2. Vendor Agreement Matrix
Show where vendors agree or disagree. When multiple vendors report issues for the same
company, that's a stronger signal. When they disagree, explain why (e.g., CrUX is 28-day
average so it won't show recent outages).

### 3. Actionable Signals (ranked by priority)
For each company with MODERATE or STRONG signal:
- What happened (specific issue)
- Which vendors confirmed it
- Suggested outreach angle
- Timing recommendation

### 4. Data Quality Assessment
Rate each vendor's usefulness for this specific check:
- What worked well
- What didn't work or was limited
- Recommendations for improving detection

Be specific. Use actual data from the reports, not generic advice. If a company shows no
issues across all vendors, say so briefly — don't pad the report."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=25000,
    )

    return response.choices[0].message.content


def main():
    if not OPENAI_API_KEY:
        print("ERROR: Set OPENAI_API_KEY environment variable in .env")
        sys.exit(1)

    companies = load_companies()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print("Signal Analyzer — Cross-Vendor Report")
    print(f"Timestamp: {timestamp}")
    print(f"Companies: {len(companies)}")
    print("=" * 70)

    # Load all available results
    result_files = {
        "provider_status": "provider_status.txt",
        "tranco": "tranco.txt",
        "downdetector_apify": "downdetector_apify.txt",
        "cloudflare_radar": "cloudflare_radar.txt",
        "crux": "crux.txt",
    }

    results = {}
    for key, filename in result_files.items():
        content = load_result(filename)
        if content:
            results[key] = content
            print(f"  Loaded: {filename} ({len(content):,} bytes)")
        else:
            print(f"  Missing: {filename}")

    if not results:
        print("\nERROR: No result files found in results/ folder.")
        print("  Run the checker scripts first.")
        sys.exit(1)

    # Build cross-reference
    print("\nBuilding cross-reference table...")
    cross_ref = build_cross_reference(companies, results)
    print(cross_ref)

    # Analyze with OpenAI
    print("\n\nSending to OpenAI for signal analysis...")
    companies_json = json.dumps(companies, indent=2)
    analysis = analyze_with_openai(companies_json, cross_ref, results)

    print("\n" + "=" * 70)
    print("AI SIGNAL ANALYSIS")
    print("=" * 70)
    print(analysis)

    # Save full report
    report_path = os.path.join(RESULTS_DIR, "signal_report.txt")
    with open(report_path, "w") as f:
        f.write(f"Signal Detection Report — {timestamp}\n")
        f.write(f"{'=' * 70}\n\n")
        f.write("CROSS-REFERENCE TABLE\n")
        f.write(f"{'=' * 70}\n")
        f.write(cross_ref)
        f.write(f"\n\n{'=' * 70}\n")
        f.write("AI SIGNAL ANALYSIS\n")
        f.write(f"{'=' * 70}\n")
        f.write(analysis)
        f.write("\n")

    print(f"\n\nFull report saved to: {report_path}")


if __name__ == "__main__":
    main()
