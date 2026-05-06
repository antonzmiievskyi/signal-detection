"""
Signal Detection Database — SQLite storage for tracking signals over time.

Stores results from each pipeline run, tracks outage state transitions
(OK→OUTAGE, OUTAGE→OK), and calculates outage durations.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "signal_detection.db")

# Per-vendor weights for confidence scoring. An outage row is created only
# when the sum of weights from vendors flagging a company exceeds
# CONFIDENCE_THRESHOLD. Rationale:
#   downdetector     : direct per-company user-reported evidence
#   cloudflare_radar : ASN-attributed (post-fix), high precision
#   provider_status  : context-only — "company on a provider with an
#                      incident" is weak evidence on its own; needs a
#                      second confirming source
#   tranco           : rank drop is lagging and noisy
#   crux             : 28-day perf metric, not an outage signal
VENDOR_WEIGHTS: dict[str, float] = {
    "downdetector": 0.7,
    "cloudflare_radar": 0.5,
    "provider_status": 0.2,
    "tranco": 0.2,
    "crux": 0.0,
}

# Threshold above which a company is considered to have an outage. Tuned
# so that any single strong source (downdetector, ASN-matched radar)
# triggers a lead, but no weak/context-only source does alone.
CONFIDENCE_THRESHOLD: float = 0.5

# Minimum sustained duration before a candidate is promoted into the
# outages table. Implements Lukasz's "5min+" floor — a single transient
# blip won't create a lead even if confidence ≥ τ in one run. Library
# default is 0 (legacy / immediate-promotion) so existing callers and
# tests don't break; production callers (run_all.py CLI) set the real
# value, default 5 min.
MIN_DURATION_SECONDS_DEFAULT: int = 5 * 60


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH):
    """Create tables if they don't exist; apply additive migrations."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            company TEXT NOT NULL,
            domain TEXT,
            vendor TEXT NOT NULL,
            outage_detected INTEGER,  -- 1=yes, 0=no, NULL=unknown
            severity TEXT,
            detail TEXT,
            raw_data TEXT,  -- JSON blob with full vendor response
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_signals_company ON signals(company);
        CREATE INDEX IF NOT EXISTS idx_signals_vendor ON signals(vendor);
        CREATE INDEX IF NOT EXISTS idx_signals_run ON signals(run_id);

        CREATE TABLE IF NOT EXISTS outages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            domain TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,  -- NULL = still ongoing
            severity TEXT,
            vendors_confirmed TEXT,  -- JSON array of vendor names
            detail TEXT,
            notified INTEGER DEFAULT 0  -- 1 if alert was sent
        );

        CREATE INDEX IF NOT EXISTS idx_outages_company ON outages(company);
        CREATE INDEX IF NOT EXISTS idx_outages_active ON outages(ended_at);

        CREATE TABLE IF NOT EXISTS outage_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL UNIQUE,
            domain TEXT,
            first_detected_at TEXT NOT NULL,
            last_confirmed_at TEXT NOT NULL,
            severity TEXT,
            vendors_confirmed TEXT,
            confidence REAL
        );
        CREATE INDEX IF NOT EXISTS idx_candidates_company ON outage_candidates(company);
    """)

    # Additive migration: confidence column on outages.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(outages)").fetchall()}
    if "confidence" not in cols:
        conn.execute("ALTER TABLE outages ADD COLUMN confidence REAL")

    conn.commit()
    conn.close()


def start_run(db_path: str = DB_PATH) -> int:
    """Record a new pipeline run. Returns the run ID."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO runs (started_at, status) VALUES (?, ?)",
        (now, "running"),
    )
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id


def finish_run(run_id: int, status: str = "completed", db_path: str = DB_PATH):
    """Mark a pipeline run as finished."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE runs SET finished_at = ?, status = ? WHERE id = ?",
        (now, status, run_id),
    )
    conn.commit()
    conn.close()


def save_signal(
    run_id: int,
    company: str,
    domain: str,
    vendor: str,
    outage_detected: bool | None,
    severity: str | None = None,
    detail: str | None = None,
    raw_data: dict | None = None,
    db_path: str = DB_PATH,
):
    """Save a signal from a vendor check."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()

    outage_int = None
    if outage_detected is True:
        outage_int = 1
    elif outage_detected is False:
        outage_int = 0

    conn.execute(
        """INSERT INTO signals (run_id, company, domain, vendor, outage_detected,
           severity, detail, raw_data, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, company, domain, vendor, outage_int,
            severity, detail,
            json.dumps(raw_data) if raw_data else None,
            now,
        ),
    )
    conn.commit()
    conn.close()


def compute_confidence(vendors: list[str]) -> float:
    """Sum vendor weights for a list of confirming vendors. Unknown vendors
    contribute 0; duplicates count once."""
    return sum(VENDOR_WEIGHTS.get(v, 0.0) for v in set(vendors))


def update_outages(
    run_id: int,
    db_path: str = DB_PATH,
    min_duration_seconds: int = 0,
    now: datetime | None = None,
) -> list[dict]:
    """Process signals from a run to detect outage state transitions.

    Two gates apply:

      1. Confidence (τ): sum of vendor weights over confirming vendors must
         reach CONFIDENCE_THRESHOLD before a company is considered "down".
      2. Duration (T_min): a company that crosses τ enters the
         outage_candidates pool first and is only promoted to the outages
         table once it stays above τ for `min_duration_seconds`. Single-run
         flickers and short-lived blips never reach the outages table.

    Transitions returned:
      candidate          — first run a company crossed τ; T_min countdown started
      pending            — already a candidate, still inside the T_min window
      promoted           — candidate matured; outage row created (started_at
                           = first_detected_at so duration history is real)
      candidate_dropped  — candidate's evidence fell below τ before T_min
      new                — only emitted when min_duration_seconds == 0 (legacy
                           direct-creation path; preserved so existing call
                           sites and tests don't change semantics)
      ongoing            — outage row already exists; vendors/confidence merged
      resolved           — outage row exists, evidence fell below τ; row closed
    """
    conn = get_connection(db_path)
    transitions = []

    rows = conn.execute(
        """SELECT DISTINCT company, domain FROM signals WHERE run_id = ?""",
        (run_id,),
    ).fetchall()

    now_dt = now if now is not None else datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    for row in rows:
        company = row["company"]
        domain = row["domain"]

        outage_signals = conn.execute(
            """SELECT vendor, severity, detail FROM signals
               WHERE run_id = ? AND company = ? AND outage_detected = 1""",
            (run_id, company),
        ).fetchall()

        active_outage = conn.execute(
            """SELECT id, vendors_confirmed, severity FROM outages
               WHERE company = ? AND ended_at IS NULL""",
            (company,),
        ).fetchone()

        candidate = conn.execute(
            """SELECT id, first_detected_at, vendors_confirmed
               FROM outage_candidates WHERE company = ?""",
            (company,),
        ).fetchone()

        vendors = [s["vendor"] for s in outage_signals]
        confidence = compute_confidence(vendors)
        passes = confidence >= CONFIDENCE_THRESHOLD
        worst_severity = _worst_severity([s["severity"] for s in outage_signals])
        details = "; ".join(s["detail"] for s in outage_signals if s["detail"])

        if passes and active_outage:
            # ONGOING — already promoted, just merge metadata.
            merged_vendors = sorted(set(
                json.loads(active_outage["vendors_confirmed"] or "[]") + vendors
            ))
            merged_confidence = compute_confidence(merged_vendors)
            merged_severity = _worst_severity(
                [s["severity"] for s in outage_signals] + [active_outage["severity"]]
            )
            conn.execute(
                """UPDATE outages SET vendors_confirmed=?, severity=?, confidence=?
                   WHERE id=?""",
                (json.dumps(merged_vendors), merged_severity, merged_confidence, active_outage["id"]),
            )
            transitions.append({
                "company": company, "transition": "ongoing",
                "severity": merged_severity, "vendors": merged_vendors,
                "confidence": merged_confidence,
            })

        elif passes and candidate:
            # Candidate exists — has it matured into a real outage?
            try:
                first_dt = datetime.fromisoformat(candidate["first_detected_at"])
            except ValueError:
                first_dt = now_dt  # corrupt timestamp — treat as just-now
            age_seconds = (now_dt - first_dt).total_seconds()

            if age_seconds >= min_duration_seconds:
                # PROMOTE — started_at is the original first-detected time so
                # the recorded outage duration reflects reality, not when we
                # decided to write the row.
                conn.execute(
                    """INSERT INTO outages (company, domain, started_at, severity,
                       vendors_confirmed, detail, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (company, domain, candidate["first_detected_at"], worst_severity,
                     json.dumps(vendors), details, confidence),
                )
                conn.execute("DELETE FROM outage_candidates WHERE id = ?", (candidate["id"],))
                transitions.append({
                    "company": company, "transition": "promoted",
                    "severity": worst_severity, "vendors": vendors,
                    "confidence": confidence, "detail": details,
                    "duration_seconds": age_seconds,
                })
            else:
                # Still inside T_min window — refresh the candidate.
                conn.execute(
                    """UPDATE outage_candidates
                       SET last_confirmed_at=?, vendors_confirmed=?, confidence=?, severity=?
                       WHERE id=?""",
                    (now_iso, json.dumps(vendors), confidence, worst_severity, candidate["id"]),
                )
                transitions.append({
                    "company": company, "transition": "pending",
                    "severity": worst_severity, "vendors": vendors,
                    "confidence": confidence,
                    "age_seconds": age_seconds,
                    "remaining_seconds": max(0, min_duration_seconds - age_seconds),
                })

        elif passes:
            # First time crossing τ for this company. With T_min == 0 we
            # preserve the legacy "create outage immediately" semantics so
            # existing callers don't break; otherwise we open a candidate.
            if min_duration_seconds <= 0:
                conn.execute(
                    """INSERT INTO outages (company, domain, started_at, severity,
                       vendors_confirmed, detail, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (company, domain, now_iso, worst_severity, json.dumps(vendors), details, confidence),
                )
                transitions.append({
                    "company": company, "transition": "new",
                    "severity": worst_severity, "vendors": vendors,
                    "confidence": confidence, "detail": details,
                })
            else:
                conn.execute(
                    """INSERT INTO outage_candidates (company, domain, first_detected_at,
                       last_confirmed_at, severity, vendors_confirmed, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (company, domain, now_iso, now_iso, worst_severity, json.dumps(vendors), confidence),
                )
                transitions.append({
                    "company": company, "transition": "candidate",
                    "severity": worst_severity, "vendors": vendors,
                    "confidence": confidence,
                })

        else:
            # confidence < τ
            if active_outage:
                conn.execute(
                    "UPDATE outages SET ended_at=? WHERE id=?",
                    (now_iso, active_outage["id"]),
                )
                transitions.append({
                    "company": company, "transition": "resolved",
                    "confidence": confidence,
                })
            if candidate:
                conn.execute("DELETE FROM outage_candidates WHERE id=?", (candidate["id"],))
                transitions.append({
                    "company": company, "transition": "candidate_dropped",
                    "confidence": confidence,
                })
            # else: no candidate, no outage — nothing to record

    conn.commit()
    conn.close()
    return transitions


def get_active_candidates(db_path: str = DB_PATH) -> list[dict]:
    """List outage candidates currently in the T_min waiting window."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT id, company, domain, first_detected_at, last_confirmed_at,
                  severity, vendors_confirmed, confidence
           FROM outage_candidates
           ORDER BY first_detected_at"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_outages(db_path: str = DB_PATH) -> list[dict]:
    """Get all currently active (unresolved) outages."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT id, company, domain, started_at, severity,
                  vendors_confirmed, detail, confidence
           FROM outages WHERE ended_at IS NULL
           ORDER BY confidence DESC NULLS LAST, started_at DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_outage_history(
    company: str | None = None,
    days: int = 30,
    db_path: str = DB_PATH,
) -> list[dict]:
    """Get outage history, optionally filtered by company."""
    conn = get_connection(db_path)
    query = """
        SELECT id, company, domain, started_at, ended_at, severity,
               vendors_confirmed, detail
        FROM outages
        WHERE started_at >= datetime('now', ?)
    """
    params: list = [f"-{days} days"]

    if company:
        query += " AND company = ?"
        params.append(company)

    query += " ORDER BY started_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_run_summary(run_id: int, db_path: str = DB_PATH) -> dict:
    """Get summary of a specific run."""
    conn = get_connection(db_path)

    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        conn.close()
        return {}

    signals = conn.execute(
        """SELECT company, vendor, outage_detected, severity, detail
           FROM signals WHERE run_id = ?""",
        (run_id,),
    ).fetchall()

    outage_count = sum(1 for s in signals if s["outage_detected"] == 1)
    companies_checked = len(set(s["company"] for s in signals))
    vendors_used = len(set(s["vendor"] for s in signals))

    conn.close()
    return {
        "run_id": run_id,
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "status": run["status"],
        "companies_checked": companies_checked,
        "vendors_used": vendors_used,
        "outage_signals": outage_count,
        "total_signals": len(signals),
    }


def _worst_severity(severities: list[str | None]) -> str:
    """Return the worst severity from a list."""
    order = {"critical": 4, "major": 3, "minor": 2, "none": 1, "unknown": 0}
    worst = "unknown"
    worst_val = -1
    for s in severities:
        val = order.get(s or "unknown", 0)
        if val > worst_val:
            worst_val = val
            worst = s or "unknown"
    return worst


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")

    # Show stats if DB exists
    conn = get_connection()
    runs = conn.execute("SELECT COUNT(*) as c FROM runs").fetchone()["c"]
    signals = conn.execute("SELECT COUNT(*) as c FROM signals").fetchone()["c"]
    outages = conn.execute("SELECT COUNT(*) as c FROM outages").fetchone()["c"]
    active = conn.execute("SELECT COUNT(*) as c FROM outages WHERE ended_at IS NULL").fetchone()["c"]
    conn.close()

    print(f"  Runs: {runs}")
    print(f"  Signals: {signals}")
    print(f"  Outages: {outages} ({active} active)")
