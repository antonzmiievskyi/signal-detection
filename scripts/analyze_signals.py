"""
Signal Analyzer — Cross-vendor report comparison and signal extraction.

Reads all results from the results/ folder, cross-references data from
different vendors, and uses OpenAI to produce a clear signal report
with actionable outreach opportunities.

Requires: OPENAI_API_KEY environment variable.
"""

import argparse
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


def load_companies(path: str | None = None) -> list[dict]:
    with open(path if path is not None else COMPANIES_FILE) as f:
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

        # Provider status — use the structured AFFECTED_COMPANIES line that
        # the checker emits, instead of scraping per-provider sections.
        # The previous scan stopped at the closing === of each provider's
        # header banner and never reached the ACTIVE INCIDENTS body.
        provider = results.get("provider_status", "")
        providers_down: list[str] = []
        affected: list[str] = []
        for line in provider.splitlines():
            if line.startswith("PROVIDERS_WITH_INCIDENTS:"):
                providers_down = [p.strip() for p in line.split(":", 1)[1].split(",") if p.strip()]
            elif line.startswith("AFFECTED_COMPANIES:"):
                affected = [p.strip() for p in line.split(":", 1)[1].split(",") if p.strip()]
        if name in affected:
            lines.append(
                f"  Provider context: company on {', '.join(providers_down) or 'unknown'} which has active incidents (NOT a per-company outage by itself)"
            )
        elif providers_down:
            lines.append(f"  Provider context: incidents at {', '.join(providers_down)} but company not on affected provider")
        else:
            lines.append(f"  Provider context: all monitored providers operational")

        # Downdetector (Apify only)
        dd = results.get("downdetector_apify", "")
        slug = company.get("downdetector_slug", "")
        if dd and slug and slug in dd:
            for line in dd.split("\n"):
                if slug in line and ("OUTAGE" in line or "No problems" in line or "BLOCKED" in line or "ERROR" in line):
                    lines.append(f"  Downdetector: {line.strip()}")
                    break

        # CrUX intentionally excluded from this cross-reference — it's a
        # 28-day rolling perf metric, not an outage signal. See the
        # PERFORMANCE SUMMARY section appended to the report.

    return "\n".join(lines)


def build_perf_summary(companies: list[dict], crux_output: str) -> str:
    """Separate stream for CrUX-driven performance signals.

    These are not outages — they're 28-day rolling p75 measurements that
    feed a different sales motion (performance / CDN optimization), not
    incident-response outreach. Kept explicitly distinct from the outage
    signal report so they don't bleed into lead scoring.
    """
    if not crux_output:
        return ""

    lines = ["=" * 70,
             "PERFORMANCE SUMMARY (CrUX, 28-day rolling p75)",
             "NOTE: separate sales motion from outage signals — do not combine.",
             "=" * 70, ""]

    poor: list[tuple[str, list[str]]] = []
    needs_work: list[tuple[str, int]] = []

    for c in companies:
        name = c["company"]
        section_header = f"--- {name} ("
        if section_header not in crux_output:
            continue
        start = crux_output.index(section_header)
        end = crux_output.find("\n---", start + 1)
        section = crux_output[start:end] if end != -1 else crux_output[start:]
        poor_metrics = [l.strip() for l in section.split("\n") if "POOR" in l and "p75=" in l]
        nw_metrics = [l.strip() for l in section.split("\n") if "NEEDS WORK" in l and "p75=" in l]
        if poor_metrics:
            poor.append((name, poor_metrics))
        elif nw_metrics:
            needs_work.append((name, len(nw_metrics)))

    if poor:
        lines.append("POOR (perf-optimization outreach candidates):")
        for name, metrics in poor:
            lines.append(f"  - {name}: {'; '.join(metrics)}")
    else:
        lines.append("No POOR metrics across the list.")

    if needs_work:
        lines.append("")
        lines.append("NEEDS WORK (watch list):")
        for name, count in needs_work:
            lines.append(f"  - {name}: {count} metrics")

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
Analyze the following data to identify **outage-driven sales signals** —
companies that are experiencing or recently experienced service incidents,
making them candidates for incident-response / resilience outreach.

IMPORTANT: This analysis is for OUTAGE signals only. CrUX (28-day rolling
p75 performance) is a SEPARATE sales motion (perf optimization) and is
not included in this input. Do NOT ask for or invent CrUX data, and do
NOT factor performance metrics into outage signal strength.

## Target Companies
{companies_json}

## Cross-Reference Summary (outage-relevant vendors per company)
{cross_ref}

## Raw Data from Each Vendor
{raw_data}

## Your Task

Produce a structured report with these sections:

### 1. Signal Strength Rating
For each company, rate the signal strength (STRONG / MODERATE / WEAK / NONE):
- STRONG: Multiple realtime sources confirm an outage (e.g., Downdetector spike
  + ASN-attributed Cloudflare Radar event)
- MODERATE: One realtime source shows issues with supporting context
- WEAK: Minor or single-source indicator
- NONE: No outage signals detected

NOTE on provider context: "Provider context" lines indicate that the company's
upstream CDN has a public incident on its status page. This is CONTEXT only,
NEVER sufficient on its own to count as an outage signal — most public
status-page incidents are minor edge issues that don't affect customers.
Only treat it as confirming evidence when paired with another realtime source.

### 2. Vendor Agreement Matrix
Show where vendors agree or disagree on outage status. Multiple vendors
flagging the same company is a stronger signal. Note shared-upstream
patterns (multiple companies on the same provider lighting up at once)
as one upstream incident, not N separate leads.

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

Be specific. Use actual data from the reports, not generic advice. If a
company shows no outage signals, say so briefly — don't pad the report."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=25000,
    )

    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", default=COMPANIES_FILE, help="Path to companies JSON file")
    args = parser.parse_args()

    if not OPENAI_API_KEY:
        print("ERROR: Set OPENAI_API_KEY environment variable in .env")
        sys.exit(1)

    companies = load_companies(args.companies)
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

    # Split CrUX out of the outage flow — it feeds a separate perf stream.
    crux_output = results.pop("crux", "")

    # Build cross-reference (outage signals only)
    print("\nBuilding cross-reference table...")
    cross_ref = build_cross_reference(companies, results)
    print(cross_ref)

    # Build perf summary (CrUX-driven, separate sales motion)
    perf_summary = build_perf_summary(companies, crux_output)
    if perf_summary:
        print("\n\n" + perf_summary)

    # Analyze with OpenAI (outage signals only — CrUX excluded by design)
    print("\n\nSending to OpenAI for outage signal analysis...")
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
        f.write("CROSS-REFERENCE TABLE (outage signals)\n")
        f.write(f"{'=' * 70}\n")
        f.write(cross_ref)
        f.write(f"\n\n{'=' * 70}\n")
        f.write("AI SIGNAL ANALYSIS (outage-driven)\n")
        f.write(f"{'=' * 70}\n")
        f.write(analysis)
        if perf_summary:
            f.write(f"\n\n{perf_summary}\n")
        f.write("\n")

    print(f"\n\nFull report saved to: {report_path}")


if __name__ == "__main__":
    main()
