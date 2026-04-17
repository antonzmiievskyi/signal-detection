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


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH):
    """Create tables if they don't exist."""
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
    """)
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


def update_outages(run_id: int, db_path: str = DB_PATH) -> list[dict]:
    """Process signals from a run to detect outage state transitions.

    - If a company has outage signals and no active outage → create one (NEW)
    - If a company has no outage signals and has an active outage → close it (RESOLVED)
    - If a company has outage signals and an active outage → update it (ONGOING)

    Returns list of transitions: [{"company": ..., "transition": "new"|"resolved"|"ongoing", ...}]
    """
    conn = get_connection(db_path)
    transitions = []

    # Get all companies with signals in this run
    rows = conn.execute(
        """SELECT DISTINCT company, domain FROM signals WHERE run_id = ?""",
        (run_id,),
    ).fetchall()

    now = datetime.now(timezone.utc).isoformat()

    for row in rows:
        company = row["company"]
        domain = row["domain"]

        # Get outage signals for this company in this run
        outage_signals = conn.execute(
            """SELECT vendor, severity, detail FROM signals
               WHERE run_id = ? AND company = ? AND outage_detected = 1""",
            (run_id, company),
        ).fetchall()

        # Get current active outage for this company
        active_outage = conn.execute(
            """SELECT id, vendors_confirmed, severity FROM outages
               WHERE company = ? AND ended_at IS NULL""",
            (company,),
        ).fetchone()

        if outage_signals and not active_outage:
            # NEW outage
            vendors = [s["vendor"] for s in outage_signals]
            worst_severity = _worst_severity([s["severity"] for s in outage_signals])
            details = "; ".join(s["detail"] for s in outage_signals if s["detail"])

            conn.execute(
                """INSERT INTO outages (company, domain, started_at, severity,
                   vendors_confirmed, detail)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (company, domain, now, worst_severity, json.dumps(vendors), details),
            )
            transitions.append({
                "company": company,
                "transition": "new",
                "severity": worst_severity,
                "vendors": vendors,
                "detail": details,
            })

        elif outage_signals and active_outage:
            # ONGOING outage — update vendors and severity
            vendors = list(set(
                json.loads(active_outage["vendors_confirmed"] or "[]")
                + [s["vendor"] for s in outage_signals]
            ))
            worst_severity = _worst_severity(
                [s["severity"] for s in outage_signals] + [active_outage["severity"]]
            )

            conn.execute(
                """UPDATE outages SET vendors_confirmed = ?, severity = ?
                   WHERE id = ?""",
                (json.dumps(vendors), worst_severity, active_outage["id"]),
            )
            transitions.append({
                "company": company,
                "transition": "ongoing",
                "severity": worst_severity,
                "vendors": vendors,
            })

        elif not outage_signals and active_outage:
            # RESOLVED — close the outage
            conn.execute(
                "UPDATE outages SET ended_at = ? WHERE id = ?",
                (now, active_outage["id"]),
            )
            transitions.append({
                "company": company,
                "transition": "resolved",
                "started_at": None,  # will be filled from outage record if needed
            })

    conn.commit()
    conn.close()
    return transitions


def get_active_outages(db_path: str = DB_PATH) -> list[dict]:
    """Get all currently active (unresolved) outages."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT id, company, domain, started_at, severity,
                  vendors_confirmed, detail
           FROM outages WHERE ended_at IS NULL
           ORDER BY started_at DESC""",
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
