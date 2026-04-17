"""
Full Signal Detection Pipeline

Runs all checker scripts sequentially, saves results, then runs AI analysis.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.join(SCRIPTS_DIR, "..")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")

CHECKERS = [
    ("Provider Status Pages", "check_provider_status.py", "provider_status.txt"),
    ("Tranco Rankings", "check_tranco.py", "tranco.txt"),
    ("Cloudflare Radar", "check_cloudflare_radar.py", "cloudflare_radar.txt"),
    ("CrUX Performance", "check_crux.py", "crux.txt"),
    ("Downdetector (Apify+AI)", "check_downdetector_apify.py", "downdetector_apify.txt"),
]

ANALYZER = ("Signal Analysis", "analyze_signals.py", "signal_report.txt")


def run_script(name: str, script: str, output_file: str) -> bool:
    """Run a checker script and save output to results/."""
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
        import re
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
                # Print last 5 lines of stderr
                for line in result.stderr.strip().split("\n")[-5:]:
                    print(f"  STDERR: {line}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print(f"  ERROR: Script timed out after 600 seconds")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("=" * 70)
    print("  SIGNAL DETECTION — FULL PIPELINE")
    print(f"  {timestamp}")
    print("=" * 70)

    # Run all checkers
    results = {}
    for name, script, output in CHECKERS:
        success = run_script(name, script, output)
        results[name] = "OK" if success else "FAILED"

    # Run analyzer
    print("\n")
    success = run_script(*ANALYZER)
    results[ANALYZER[0]] = "OK" if success else "FAILED"

    # Final summary
    print(f"\n\n{'='*70}")
    print("  PIPELINE COMPLETE")
    print(f"{'='*70}")
    for name, status in results.items():
        icon = "+" if status == "OK" else "!"
        print(f"  [{icon}] {name}: {status}")

    print(f"\n  Results saved to: {RESULTS_DIR}/")
    print(f"  Full report: {os.path.join(RESULTS_DIR, ANALYZER[2])}")

    failed = [n for n, s in results.items() if s == "FAILED"]
    if failed:
        print(f"\n  WARNING: {len(failed)} step(s) failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
