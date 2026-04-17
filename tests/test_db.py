"""Tests for the database module."""

import json
import os
import tempfile

import pytest

from scripts.db import (
    finish_run,
    get_active_outages,
    get_connection,
    get_outage_history,
    get_run_summary,
    init_db,
    save_signal,
    start_run,
    update_outages,
    _worst_severity,
)


@pytest.fixture
def db_path():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


class TestInitDb:
    def test_creates_tables(self, db_path):
        conn = get_connection(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "runs" in table_names
        assert "signals" in table_names
        assert "outages" in table_names
        conn.close()

    def test_idempotent(self, db_path):
        init_db(db_path)  # second call should not fail
        conn = get_connection(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables) >= 3
        conn.close()


class TestRuns:
    def test_start_run(self, db_path):
        run_id = start_run(db_path)
        assert run_id == 1

        conn = get_connection(db_path)
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert run["status"] == "running"
        assert run["started_at"] is not None
        assert run["finished_at"] is None
        conn.close()

    def test_finish_run(self, db_path):
        run_id = start_run(db_path)
        finish_run(run_id, "completed", db_path)

        conn = get_connection(db_path)
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert run["status"] == "completed"
        assert run["finished_at"] is not None
        conn.close()

    def test_multiple_runs(self, db_path):
        id1 = start_run(db_path)
        id2 = start_run(db_path)
        assert id2 == id1 + 1


class TestSignals:
    def test_save_signal(self, db_path):
        run_id = start_run(db_path)
        save_signal(
            run_id, "EA", "ea.com", "downdetector",
            outage_detected=True, severity="major",
            detail="Server issues", db_path=db_path,
        )

        conn = get_connection(db_path)
        sig = conn.execute("SELECT * FROM signals WHERE run_id = ?", (run_id,)).fetchone()
        assert sig["company"] == "EA"
        assert sig["vendor"] == "downdetector"
        assert sig["outage_detected"] == 1
        assert sig["severity"] == "major"
        conn.close()

    def test_save_no_outage(self, db_path):
        run_id = start_run(db_path)
        save_signal(
            run_id, "Nintendo", "nintendo.com", "crux",
            outage_detected=False, detail="All good", db_path=db_path,
        )

        conn = get_connection(db_path)
        sig = conn.execute("SELECT * FROM signals WHERE company = 'Nintendo'").fetchone()
        assert sig["outage_detected"] == 0
        conn.close()

    def test_save_unknown_outage(self, db_path):
        run_id = start_run(db_path)
        save_signal(
            run_id, "Ubisoft", "ubisoft.com", "downdetector",
            outage_detected=None, detail="Page not found", db_path=db_path,
        )

        conn = get_connection(db_path)
        sig = conn.execute("SELECT * FROM signals WHERE company = 'Ubisoft'").fetchone()
        assert sig["outage_detected"] is None
        conn.close()

    def test_save_with_raw_data(self, db_path):
        run_id = start_run(db_path)
        raw = {"report_count": 150, "comments": ["down again"]}
        save_signal(
            run_id, "EA", "ea.com", "downdetector",
            outage_detected=True, raw_data=raw, db_path=db_path,
        )

        conn = get_connection(db_path)
        sig = conn.execute("SELECT raw_data FROM signals WHERE company = 'EA'").fetchone()
        assert json.loads(sig["raw_data"]) == raw
        conn.close()


class TestOutageTransitions:
    def test_new_outage(self, db_path):
        run_id = start_run(db_path)
        save_signal(run_id, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", detail="Server down",
                    db_path=db_path)

        transitions = update_outages(run_id, db_path)
        assert len(transitions) == 1
        assert transitions[0]["company"] == "EA"
        assert transitions[0]["transition"] == "new"
        assert transitions[0]["severity"] == "major"

        active = get_active_outages(db_path)
        assert len(active) == 1
        assert active[0]["company"] == "EA"

    def test_ongoing_outage(self, db_path):
        # Run 1: outage starts
        run1 = start_run(db_path)
        save_signal(run1, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", db_path=db_path)
        update_outages(run1, db_path)

        # Run 2: outage continues
        run2 = start_run(db_path)
        save_signal(run2, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", db_path=db_path)
        save_signal(run2, "EA", "ea.com", "crux",
                    outage_detected=True, severity="minor", db_path=db_path)

        transitions = update_outages(run2, db_path)
        assert len(transitions) == 1
        assert transitions[0]["transition"] == "ongoing"
        assert "crux" in transitions[0]["vendors"]

        # Still one active outage
        active = get_active_outages(db_path)
        assert len(active) == 1

    def test_resolved_outage(self, db_path):
        # Run 1: outage starts
        run1 = start_run(db_path)
        save_signal(run1, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", db_path=db_path)
        update_outages(run1, db_path)

        # Run 2: outage resolved
        run2 = start_run(db_path)
        save_signal(run2, "EA", "ea.com", "downdetector",
                    outage_detected=False, db_path=db_path)

        transitions = update_outages(run2, db_path)
        assert any(t["transition"] == "resolved" and t["company"] == "EA" for t in transitions)

        active = get_active_outages(db_path)
        assert len(active) == 0

    def test_no_outage_no_transition(self, db_path):
        run_id = start_run(db_path)
        save_signal(run_id, "Nintendo", "nintendo.com", "crux",
                    outage_detected=False, db_path=db_path)

        transitions = update_outages(run_id, db_path)
        assert not any(t["company"] == "Nintendo" and t["transition"] == "new" for t in transitions)

    def test_multiple_companies(self, db_path):
        run_id = start_run(db_path)
        save_signal(run_id, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", db_path=db_path)
        save_signal(run_id, "Epic", "epicgames.com", "downdetector",
                    outage_detected=True, severity="minor", db_path=db_path)
        save_signal(run_id, "Nintendo", "nintendo.com", "downdetector",
                    outage_detected=False, db_path=db_path)

        transitions = update_outages(run_id, db_path)
        new_outages = [t for t in transitions if t["transition"] == "new"]
        assert len(new_outages) == 2

        active = get_active_outages(db_path)
        assert len(active) == 2


class TestOutageHistory:
    def test_get_history(self, db_path):
        run_id = start_run(db_path)
        save_signal(run_id, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", db_path=db_path)
        update_outages(run_id, db_path)

        history = get_outage_history(days=1, db_path=db_path)
        assert len(history) == 1
        assert history[0]["company"] == "EA"

    def test_filter_by_company(self, db_path):
        run_id = start_run(db_path)
        save_signal(run_id, "EA", "ea.com", "downdetector",
                    outage_detected=True, db_path=db_path)
        save_signal(run_id, "Epic", "epicgames.com", "downdetector",
                    outage_detected=True, db_path=db_path)
        update_outages(run_id, db_path)

        history = get_outage_history(company="EA", days=1, db_path=db_path)
        assert len(history) == 1
        assert history[0]["company"] == "EA"


class TestRunSummary:
    def test_summary(self, db_path):
        run_id = start_run(db_path)
        save_signal(run_id, "EA", "ea.com", "downdetector",
                    outage_detected=True, severity="major", db_path=db_path)
        save_signal(run_id, "EA", "ea.com", "crux",
                    outage_detected=False, db_path=db_path)
        save_signal(run_id, "Nintendo", "nintendo.com", "crux",
                    outage_detected=False, db_path=db_path)
        finish_run(run_id, "completed", db_path)

        summary = get_run_summary(run_id, db_path)
        assert summary["run_id"] == run_id
        assert summary["status"] == "completed"
        assert summary["companies_checked"] == 2
        assert summary["vendors_used"] == 2
        assert summary["outage_signals"] == 1
        assert summary["total_signals"] == 3

    def test_nonexistent_run(self, db_path):
        summary = get_run_summary(999, db_path)
        assert summary == {}


class TestWorstSeverity:
    def test_critical_wins(self):
        assert _worst_severity(["minor", "critical", "major"]) == "critical"

    def test_major_over_minor(self):
        assert _worst_severity(["minor", "major"]) == "major"

    def test_handles_none(self):
        assert _worst_severity([None, "minor"]) == "minor"

    def test_all_unknown(self):
        assert _worst_severity([None, None]) == "unknown"

    def test_single_value(self):
        assert _worst_severity(["minor"]) == "minor"
