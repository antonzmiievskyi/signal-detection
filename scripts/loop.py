"""Continuous-mode runner.

Wraps run_all.py in a sleep loop so the pipeline executes on a fixed
cadence inside docker-compose. The interval governs how often a fresh
iteration is started — if a run takes longer than the interval (Apify
scraping at 10–15 min for 50+ companies), the next iteration starts
immediately after.

Configurable via env vars:
  PIPELINE_INTERVAL_SECONDS  seconds between iteration starts (default 1800)
  COMPANIES_FILE             path to companies JSON (default companies.json)
  MIN_DURATION_MINUTES       T_min for outage promotion (default 5)
"""

import os
import signal
import subprocess
import sys
import time
from datetime import datetime

INTERVAL_SECONDS = int(os.environ.get("PIPELINE_INTERVAL_SECONDS", "1800"))
COMPANIES_FILE = os.environ.get("COMPANIES_FILE", "companies.json")
MIN_DURATION_MIN = os.environ.get("MIN_DURATION_MINUTES", "5")

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_ALL = os.path.join(SCRIPTS_DIR, "run_all.py")

_stop = False


def _handle(signum, _frame):
    global _stop
    print(f"\n[loop] caught signal {signum}; will stop after current iteration", flush=True)
    _stop = True


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def _sleep_responsive(seconds: int) -> None:
    """Sleep in 5-second chunks so SIGTERM cuts the wait short."""
    while seconds > 0 and not _stop:
        chunk = min(5, seconds)
        time.sleep(chunk)
        seconds -= chunk


def main() -> int:
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    print(
        f"[loop] starting — interval={INTERVAL_SECONDS}s "
        f"companies={COMPANIES_FILE} min_duration={MIN_DURATION_MIN}m",
        flush=True,
    )

    while not _stop:
        started = time.time()
        print(f"\n[loop] iteration {_ts()}", flush=True)

        try:
            result = subprocess.run(
                [
                    sys.executable, RUN_ALL,
                    "--companies", COMPANIES_FILE,
                    "--min-duration", str(MIN_DURATION_MIN),
                ],
            )
            elapsed = int(time.time() - started)
            print(f"[loop] iteration done rc={result.returncode} dur={elapsed}s", flush=True)
        except Exception as exc:
            print(f"[loop] iteration error: {exc}", flush=True)
            elapsed = int(time.time() - started)

        if _stop:
            break

        sleep_for = max(0, INTERVAL_SECONDS - elapsed)
        if sleep_for == 0:
            print("[loop] iteration overran interval; starting next immediately", flush=True)
            continue

        print(f"[loop] sleeping {sleep_for}s", flush=True)
        _sleep_responsive(sleep_for)

    print("[loop] stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
