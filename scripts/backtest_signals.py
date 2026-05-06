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
from collections import Counter, defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "signal_detection.db")


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

    section("CAVEAT")
    print("  - Only 4 runs over ~2.5 hours on 2026-04-17 are stored.")
    print("  - All outages have ended_at=NULL: duration histogram is not meaningful yet.")
    print("  - Conclusions are about NOISE STRUCTURE in the current pipeline,")
    print("    not about real-world outage durations. Real T_min tuning needs")
    print("    days-to-weeks of run history.")


if __name__ == "__main__":
    main()
