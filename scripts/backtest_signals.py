"""
Backtest current signals against the rules the team proposed.

Reads signal_detection.db and reports, for each rule, how many "outages"
survive — to give an empirical answer to:
  - is the per-company outage count an artifact?
  - what does each filter actually remove?
  - which signals are still load-bearing once provider-level noise is gone?

This is exploratory (small dataset, 4 runs on 2026-04-17), not a real
historical backtest. It's the cheapest way to ground the redesign in
data we already have.
"""

import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import VENDOR_WEIGHTS, CONFIDENCE_THRESHOLD, compute_confidence

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "signal_detection.db")

# Lukasz's threshold ladder, in seconds.
T_MIN_LADDER = [
    ("5min",  5 * 60),
    ("15min", 15 * 60),
    ("30min", 30 * 60),
    ("1h",    60 * 60),
    ("4h",    4 * 60 * 60),
]


def query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    conn = sqlite3.connect(DB_PATH)

    section("DATASET")
    runs = query(conn, "SELECT COUNT(*) n, MIN(started_at) lo, MAX(started_at) hi FROM runs")[0]
    sigs = query(conn, "SELECT COUNT(*) n FROM signals")[0]
    outs = query(conn, "SELECT COUNT(*) n FROM outages")[0]
    print(f"  runs:    {runs['n']}  ({runs['lo']} .. {runs['hi']})")
    print(f"  signals: {sigs['n']}")
    print(f"  outages: {outs['n']}")

    section("PER-VENDOR SIGNAL VOLUME")
    rows = query(conn, """
        SELECT vendor,
               SUM(CASE WHEN outage_detected=1 THEN 1 ELSE 0 END) AS flagged,
               SUM(CASE WHEN outage_detected=0 THEN 1 ELSE 0 END) AS clean,
               SUM(CASE WHEN outage_detected IS NULL THEN 1 ELSE 0 END) AS unknown,
               COUNT(DISTINCT company) AS unique_co,
               COUNT(DISTINCT CASE WHEN outage_detected=1 THEN company END) AS unique_co_flagged
        FROM signals GROUP BY vendor ORDER BY vendor
    """)
    print(f"  {'vendor':<18} {'flagged':>8} {'clean':>8} {'unknown':>8} {'co_flagged':>12}")
    for r in rows:
        print(f"  {r['vendor']:<18} {r['flagged']:>8} {r['clean']:>8} {r['unknown'] or 0:>8} {r['unique_co_flagged']:>12}")

    section("OUTAGE TABLE: COFIRE PATTERN")
    rows = query(conn, """
        SELECT substr(started_at,1,16) AS minute,
               vendors_confirmed,
               COUNT(*) AS n
        FROM outages
        GROUP BY minute, vendors_confirmed
        ORDER BY minute, n DESC
    """)
    for r in rows:
        print(f"  {r['minute']}  {r['vendors_confirmed']:<45} → {r['n']} companies")

    section("RULE BACKTEST: how many outages survive each filter")
    all_outages = query(conn, "SELECT * FROM outages")
    total = len(all_outages)

    def vendors(o):
        try:
            return json.loads(o.get("vendors_confirmed") or "[]")
        except Exception:
            return []

    rules = [
        ("R0 — current pipeline (no filter)",
         lambda o: True),
        ("R1 — drop provider_status-only signals",
         lambda o: vendors(o) != ["provider_status"]),
        ("R2 — require >=2 vendors",
         lambda o: len(vendors(o)) >= 2),
        ("R3 — require >=2 AND no provider_status alone",
         lambda o: len(vendors(o)) >= 2 and vendors(o) != ["provider_status"]),
        ("R4 — require per-company vendor (downdetector OR tranco)",
         lambda o: any(v in vendors(o) for v in ("downdetector", "tranco"))),
    ]

    for name, pred in rules:
        survivors = [o for o in all_outages if pred(o)]
        pct = (len(survivors) / total * 100) if total else 0
        unique_co = len({o["company"] for o in survivors})
        print(f"  {name}")
        print(f"      survives: {len(survivors):>3}/{total} ({pct:5.1f}%)   unique companies: {unique_co}")

    section("PER-COMPANY VENDOR AGREEMENT")
    rows = query(conn, """
        SELECT company,
               COUNT(DISTINCT vendor) AS vendors_total,
               COUNT(DISTINCT CASE WHEN outage_detected=1 THEN vendor END) AS vendors_flagging
        FROM signals
        GROUP BY company
        HAVING vendors_flagging >= 2
        ORDER BY vendors_flagging DESC, company
    """)
    if rows:
        print(f"  {'company':<32} {'vendors_flagging':>18}")
        for r in rows:
            print(f"  {r['company']:<32} {r['vendors_flagging']:>18}")
    else:
        print("  (no company has >=2 distinct vendors flagging it across all runs)")

    section("WHAT THE NON-PROVIDER VENDORS ACTUALLY SAID")
    rows = query(conn, """
        SELECT vendor, company, severity, substr(detail, 1, 80) AS detail
        FROM signals
        WHERE outage_detected = 1 AND vendor != 'provider_status'
        ORDER BY vendor, company
        LIMIT 25
    """)
    if rows:
        for r in rows:
            print(f"  [{r['vendor']:<16}] {r['company']:<25} {r['severity'] or '-':<7} {r['detail']}")
    else:
        print("  (no non-provider_status outage flags in the dataset)")

    section("THRESHOLD SWEEP — how many leads survive each T_min")
    print("  For each T_min, we replay every signal in chronological order")
    print("  and count how many companies would have been promoted to outages")
    print("  vs left as candidates that never matured. Same confidence model")
    print("  (τ = {tau}, weights = {wts}).".format(
        tau=CONFIDENCE_THRESHOLD,
        wts=", ".join(f"{k}={v}" for k, v in VENDOR_WEIGHTS.items() if v > 0),
    ))
    print()
    sweep_results = simulate_t_min_sweep(conn)
    print(f"  {'T_min':<8} {'promoted':>10} {'unique_co':>11} {'still_candidate':>17} {'dropped':>10}")
    print(f"  {'-'*8} {'-'*10} {'-'*11} {'-'*17} {'-'*10}")
    for label, stats in sweep_results:
        print(
            f"  {label:<8} {stats['promoted']:>10} {stats['unique_companies']:>11} "
            f"{stats['still_candidate']:>17} {stats['dropped']:>10}"
        )
    print()
    print("  promoted = lead would have been created at this threshold")
    print("  still_candidate = signal never sustained T_min before history ended")
    print("  dropped = signal fell below τ before promoting (real noise filter)")

    section("CAVEAT")
    print("  - The threshold sweep replays stored signals using each run's")
    print("    timestamp as the 'arrival time'. With ~hourly manual runs the")
    print("    inter-arrival gap is ~1h, so T_min < 1h essentially collapses")
    print("    to 'present in 2 runs'. To get meaningful 5/15/30 separation")
    print("    you need a minute-cadence scheduler (docker-compose, cron).")
    print("  - Conclusions are about NOISE STRUCTURE in the current pipeline,")
    print("    not about real-world outage durations.")


def simulate_t_min_sweep(conn) -> list[tuple[str, dict]]:
    """Replay all signals chronologically and simulate the candidate→
    promotion logic for each T_min threshold. Returns one stats row per
    threshold:
      promoted          — leads that would have crossed T_min
      unique_companies  — distinct companies among those leads
      still_candidate   — companies whose signal hadn't matured by end of
                          history (would still be in the pen)
      dropped           — companies whose signal fell below τ before
                          promoting (genuinely filtered noise)
    """
    rows = query(conn, """
        SELECT s.run_id, s.company, s.vendor, s.outage_detected, s.created_at
        FROM signals s ORDER BY s.created_at, s.run_id
    """)

    # Group signals by (run_id, company) so we can compute per-run confidence.
    runs_seen: list[tuple[str, str]] = []  # (run_id, created_at) for replay order
    per_run: dict = defaultdict(lambda: defaultdict(list))  # run_id -> company -> [vendors]
    run_time: dict = {}  # run_id -> earliest created_at in that run
    for r in rows:
        rid, co, ven, od, ts = r["run_id"], r["company"], r["vendor"], r["outage_detected"], r["created_at"]
        if od == 1:
            per_run[rid][co].append(ven)
        if rid not in run_time:
            run_time[rid] = ts
            runs_seen.append((rid, ts))

    runs_seen.sort(key=lambda x: x[1])

    out = []
    for label, t_min_sec in T_MIN_LADDER:
        candidates: dict[str, datetime] = {}  # company -> first_detected datetime
        promoted = 0
        promoted_companies: set[str] = set()
        dropped = 0

        for rid, run_ts in runs_seen:
            try:
                run_dt = datetime.fromisoformat(run_ts.replace("Z", "+00:00"))
            except ValueError:
                continue

            # Companies that crossed τ in this run
            companies_passing: set[str] = set()
            for company, vendors in per_run[rid].items():
                if compute_confidence(vendors) >= CONFIDENCE_THRESHOLD:
                    companies_passing.add(company)

            # Promote / open candidates for passers
            for company in companies_passing:
                if company in candidates:
                    age = (run_dt - candidates[company]).total_seconds()
                    if age >= t_min_sec:
                        promoted += 1
                        promoted_companies.add(company)
                        del candidates[company]
                else:
                    candidates[company] = run_dt

            # Companies seen in this run but not passing → drop their candidate
            companies_in_run = set(per_run[rid].keys())
            for company in companies_in_run - companies_passing:
                if company in candidates:
                    dropped += 1
                    del candidates[company]

        out.append((label, {
            "promoted": promoted,
            "unique_companies": len(promoted_companies),
            "still_candidate": len(candidates),
            "dropped": dropped,
        }))
    return out


if __name__ == "__main__":
    main()
