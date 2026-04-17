"""
Full Signal Detection Pipeline

Runs all checker scripts sequentially, saves results to files and SQLite,
tracks outage state transitions, then runs AI analysis.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from db import init_db, start_run, finish_run, save_signal, update_outages
from db import get_active_outages, get_run_summary

load_dotenv()

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPTS_DIR, "..")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")

CHECKERS = [
    ("Provider Status Pages", "check_provider_status.py", "provider_status.txt", "provider_status"),
    ("Tranco Rankings", "check_tranco.py", "tranco.txt", "tranco"),
    ("Cloudflare Radar", "check_cloudflare_radar.py", "cloudflare_radar.txt", "cloudflare_radar"),
    ("CrUX Performance", "check_crux.py", "crux.txt", "crux"),
    ("Downdetector (Apify+AI)", "check_downdetector_apify.py", "downdetector_apify.txt", "downdetector"),
]

ANALYZER = ("Signal Analysis", "analyze_signals.py", "signal_report.txt")


def run_script(name: str, script: str, output_file: str) -> tuple[bool, str]:
    """Run a checker script and save output to results/.

    Returns (success, clean_output).
    """
    script_path = os.path.join(SCRIPTS_DIR, script)
    output_path = os.path.join(RESULTS_DIR, output_file)

    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"  Script: {script}")
    print(f"{'='*70}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=ROOT_DIR,
        )

        # Filter out Apify log noise (ANSI color codes)
        clean_output = re.sub(r'\[36m\[.*?\[0m[^\n]*\n?', '', result.stdout)
        clean_output = clean_output.strip()

        with open(output_path, "w") as f:
            f.write(clean_output)

        # Print last 20 lines as summary
        lines = clean_output.split("\n")
        summary_lines = lines[-20:] if len(lines) > 20 else lines
        for line in summary_lines:
            print(f"  {line}")

        if result.returncode != 0:
            print(f"\n  WARNING: Script exited with code {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[-5:]:
                    print(f"  STDERR: {line}")
            return False, clean_output

        return True, clean_output

    except subprocess.TimeoutExpired:
        print(f"  ERROR: Script timed out after 600 seconds")
        return False, ""
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, ""


def parse_signals_from_output(vendor: str, output: str, companies: list[dict]) -> list[dict]:
    """Parse checker script output into structured signals for the database.

    Returns list of dicts with: company, domain, outage_detected, severity, detail.
    """
    signals = []

    for company in companies:
        name = company["company"]
        domain = company["domain"]
        signal = {
            "company": name,
            "domain": domain,
            "outage_detected": None,
            "severity": None,
            "detail": None,
        }

        if vendor == "provider_status":
            # Provider status shows provider-level issues, not per-company
            # Check for active incidents across all providers
            if "ACTIVE INCIDENTS" in output:
                signal["outage_detected"] = True
                signal["severity"] = "minor"
                signal["detail"] = "Active provider incidents detected"
            else:
                signal["outage_detected"] = False
                signal["detail"] = "All providers operational"

        elif vendor == "tranco":
            for line in output.split("\n"):
                if name in line and domain in line:
                    if "ERROR" in line:
                        signal["detail"] = "Tranco lookup error"
                    elif "DOWN" in line:
                        signal["detail"] = line.strip()
                        # Significant rank drops are a weak signal
                        if "Significant rank drops" in output and name in output.split("Significant rank drops")[1]:
                            signal["outage_detected"] = None
                            signal["severity"] = "minor"
                    elif "UP" in line:
                        signal["outage_detected"] = False
                        signal["detail"] = line.strip()
                    else:
                        signal["outage_detected"] = False
                        signal["detail"] = line.strip()
                    break

        elif vendor == "cloudflare_radar":
            country = company["country"]
            if f"Outages in {country}" in output:
                start = output.index(f"Outages in {country}")
                end = output.find("\n---", start + 1)
                section = output[start:end] if end != -1 else output[start:]
                if "No outages detected" in section:
                    signal["outage_detected"] = False
                    signal["detail"] = f"No network outages in {country}"
                else:
                    signal["outage_detected"] = True
                    signal["severity"] = "major"
                    signal["detail"] = section.strip()

        elif vendor == "crux":
            section_header = f"--- {name} ("
            if section_header in output:
                start = output.index(section_header)
                end = output.find("\n---", start + 1)
                section = output[start:end] if end != -1 else output[start:]
                poor = [l.strip() for l in section.split("\n") if "POOR" in l and "p75=" in l]
                if poor:
                    signal["severity"] = "minor"
                    signal["detail"] = "; ".join(poor)
                else:
                    signal["outage_detected"] = False
                    signal["detail"] = "All metrics acceptable"

        elif vendor == "downdetector":
            slug = company.get("downdetector_slug", "")
            if slug and slug in output:
                for line in output.split("\n"):
                    if slug in line:
                        if "OUTAGE" in line:
                            signal["outage_detected"] = True
                            # Find severity if present
                            sev_match = re.search(r'\[(\w+)\]', line)
                            signal["severity"] = sev_match.group(1).lower() if sev_match else "minor"
                            signal["detail"] = line.strip()
                        elif "No problems" in line:
                            signal["outage_detected"] = False
                            signal["detail"] = "No problems reported"
                        elif "not found" in line.lower() or "not available" in line.lower():
                            signal["detail"] = "Page not available"
                        break

        signals.append(signal)

    return signals


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Load companies
    companies_path = os.path.join(ROOT_DIR, "companies.json")
    with open(companies_path) as f:
        companies = json.load(f)

    # Initialize database and start run
    init_db()
    run_id = start_run()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("=" * 70)
    print("  SIGNAL DETECTION — FULL PIPELINE")
    print(f"  {timestamp}")
    print(f"  Run ID: {run_id}")
    print("=" * 70)

    # Run all checkers and save signals to DB
    step_results = {}
    for name, script, output_file, vendor in CHECKERS:
        success, output = run_script(name, script, output_file)
        step_results[name] = "OK" if success else "FAILED"

        if success and output:
            signals = parse_signals_from_output(vendor, output, companies)
            for sig in signals:
                save_signal(
                    run_id=run_id,
                    company=sig["company"],
                    domain=sig["domain"],
                    vendor=vendor,
                    outage_detected=sig["outage_detected"],
                    severity=sig["severity"],
                    detail=sig["detail"],
                )

    # Process outage state transitions
    print(f"\n{'='*70}")
    print("  OUTAGE TRANSITIONS")
    print(f"{'='*70}")
    transitions = update_outages(run_id)
    if transitions:
        for t in transitions:
            icon = {"new": "!!!", "ongoing": "...", "resolved": "OK "}[t["transition"]]
            print(f"  [{icon}] {t['company']}: {t['transition'].upper()}", end="")
            if t.get("severity"):
                print(f" (severity: {t['severity']})", end="")
            if t.get("vendors"):
                print(f" — confirmed by: {', '.join(t['vendors'])}", end="")
            print()
    else:
        print("  No outage state changes.")

    # Show active outages
    active = get_active_outages()
    if active:
        print(f"\n  Active outages ({len(active)}):")
        for o in active:
            vendors = json.loads(o.get("vendors_confirmed") or "[]")
            print(f"    - {o['company']} [{o['severity']}] since {o['started_at']}")
            print(f"      Vendors: {', '.join(vendors)}")

    # Run analyzer
    print("\n")
    success, _ = run_script(*ANALYZER, )
    step_results[ANALYZER[0]] = "OK" if success else "FAILED"

    # Finish run
    all_ok = all(s == "OK" for s in step_results.values())
    finish_run(run_id, status="completed" if all_ok else "partial")

    # Run summary
    summary = get_run_summary(run_id)

    # Final output
    print(f"\n\n{'='*70}")
    print("  PIPELINE COMPLETE")
    print(f"{'='*70}")
    for name, status in step_results.items():
        icon = "+" if status == "OK" else "!"
        print(f"  [{icon}] {name}: {status}")

    print(f"\n  Run #{run_id}: {summary['total_signals']} signals, "
          f"{summary['outage_signals']} outage(s), "
          f"{summary['companies_checked']} companies, "
          f"{summary['vendors_used']} vendors")
    print(f"  Results: {RESULTS_DIR}/")
    print(f"  Database: {os.path.abspath(os.path.join(ROOT_DIR, 'signal_detection.db'))}")
    print(f"  Report: {os.path.join(RESULTS_DIR, ANALYZER[2])}")

    # Best-effort Slack notification (never fails the pipeline)
    if os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_CHANNEL"):
        print(f"\n{'='*70}")
        print("  SLACK NOTIFICATION")
        print(f"{'='*70}")
        try:
            from notify_slack import build_blocks, post_to_slack
            blocks, fallback = build_blocks(run_id)
            result = post_to_slack(
                os.environ["SLACK_BOT_TOKEN"],
                os.environ["SLACK_CHANNEL"],
                blocks,
                fallback,
            )
            print(f"  Posted to Slack: channel={result.get('channel')} ts={result.get('ts')}")
        except Exception as e:
            print(f"  WARNING: Slack notification failed: {e}")
    else:
        print("\n  (Skipping Slack: SLACK_BOT_TOKEN or SLACK_CHANNEL not set)")

    failed = [n for n, s in step_results.items() if s == "FAILED"]
    if failed:
        print(f"\n  WARNING: {len(failed)} step(s) failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
