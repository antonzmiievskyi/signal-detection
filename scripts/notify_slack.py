"""
Slack notifier — posts a short summary of the latest pipeline run to a Slack channel.

Standalone: reads the latest run from the SQLite DB and sends a message via
Slack Web API (chat.postMessage). Uses Block Kit for readable formatting.
Requires SLACK_BOT_TOKEN and SLACK_CHANNEL in the environment.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from db import get_active_outages, get_connection, get_run_summary

load_dotenv()

SLACK_API = "https://slack.com/api/chat.postMessage"

VENDORS = [
    ("provider_status", "Providers"),
    ("tranco", "Tranco"),
    ("cloudflare_radar", "CF Radar"),
    ("crux", "CrUX"),
    ("downdetector", "Downdetector"),
]

SEVERITY_EMOJI = {
    "critical": "🚨",
    "major": "🔴",
    "minor": "🟡",
    "unknown": "⚪",
}


def latest_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def transitions_for_run(conn: sqlite3.Connection, run_id: int) -> dict:
    run = conn.execute(
        "SELECT started_at, finished_at FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    if not run:
        return {"new": [], "resolved": []}

    started = run["started_at"]
    finished = run["finished_at"] or datetime.now(timezone.utc).isoformat()

    new = conn.execute(
        """SELECT company, severity, vendors_confirmed FROM outages
           WHERE started_at >= ? AND started_at <= ?""",
        (started, finished),
    ).fetchall()

    resolved = conn.execute(
        """SELECT company, severity, vendors_confirmed, started_at, ended_at
           FROM outages WHERE ended_at IS NOT NULL
           AND ended_at >= ? AND ended_at <= ?""",
        (started, finished),
    ).fetchall()

    return {
        "new": [dict(r) for r in new],
        "resolved": [dict(r) for r in resolved],
    }


def vendor_statuses(conn: sqlite3.Connection, run_id: int) -> list[tuple[str, bool]]:
    rows = conn.execute(
        "SELECT DISTINCT vendor FROM signals WHERE run_id = ?", (run_id,)
    ).fetchall()
    seen = {r["vendor"] for r in rows}
    return [(label, code in seen) for code, label in VENDORS]


def format_duration(started_at: str) -> str:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    delta = datetime.now(timezone.utc) - start
    total = int(delta.total_seconds())
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m"
    if total < 86400:
        return f"{total // 3600}h{(total % 3600) // 60:02d}m"
    return f"{total // 86400}d{(total % 86400) // 3600:02d}h"


def pretty_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except ValueError:
        return iso


def build_blocks(run_id: int) -> tuple[list[dict], str]:
    """Return (blocks, fallback_text) for chat.postMessage."""
    conn = get_connection()
    try:
        summary = get_run_summary(run_id)
        transitions = transitions_for_run(conn, run_id)
        active = get_active_outages()
        steps = vendor_statuses(conn, run_id)
    finally:
        conn.close()

    ts = summary.get("finished_at") or summary.get("started_at") or ""
    ts_pretty = pretty_time(ts)

    outage_count = summary.get("outage_signals", 0)
    header_emoji = "🚨" if outage_count > 0 else "✅"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{header_emoji} Signal Detection — Run #{run_id}",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":clock1: {ts_pretty}"},
                {
                    "type": "mrkdwn",
                    "text": (
                        f":office: *{summary.get('companies_checked', 0)}* companies"
                    ),
                },
                {
                    "type": "mrkdwn",
                    "text": (
                        f":satellite_antenna: *{summary.get('vendors_used', 0)}/"
                        f"{len(VENDORS)}* vendors"
                    ),
                },
                {
                    "type": "mrkdwn",
                    "text": f":signal_strength: *{summary.get('total_signals', 0)}* signals",
                },
                {
                    "type": "mrkdwn",
                    "text": f":warning: *{outage_count}* outage signal(s)",
                },
            ],
        },
    ]

    # NEW outages
    if transitions["new"]:
        lines = ["*🔴 NEW outages*"]
        for o in transitions["new"]:
            vendors = ", ".join(json.loads(o.get("vendors_confirmed") or "[]"))
            icon = SEVERITY_EMOJI.get(o.get("severity") or "unknown", "")
            lines.append(
                f"{icon} *{o['company']}* · `{o.get('severity') or 'unknown'}`"
                f"{' · ' + vendors if vendors else ''}"
            )
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
            }
        )

    # RESOLVED
    if transitions["resolved"]:
        lines = ["*🟢 RESOLVED*"]
        for o in transitions["resolved"]:
            lines.append(f"• *{o['company']}*")
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
            }
        )

    # Active outages
    if active:
        lines = [f"*Active outages ({len(active)})*"]
        for o in active:
            vendors = ", ".join(json.loads(o.get("vendors_confirmed") or "[]"))
            icon = SEVERITY_EMOJI.get(o.get("severity") or "unknown", "")
            dur = format_duration(o["started_at"])
            lines.append(
                f"{icon} *{o['company']}* · `{o.get('severity') or 'unknown'}`"
                f" · {dur}"
                f"{' · ' + vendors if vendors else ''}"
            )
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
            }
        )
    elif not transitions["new"] and not transitions["resolved"]:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: *No active outages.* All tracked services are operational.",
                },
            }
        )

    # Step statuses
    step_text = "  ".join(f"{'✅' if ok else '❌'} {label}" for label, ok in steps)
    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": step_text}],
        }
    )

    fallback = (
        f"Signal Detection Run #{run_id} — {outage_count} outage signals, "
        f"{len(active)} active, {len(transitions['new'])} new, "
        f"{len(transitions['resolved'])} resolved."
    )
    return blocks, fallback


def post_to_slack(token: str, channel: str, blocks: list[dict], fallback: str) -> dict:
    resp = requests.post(
        SLACK_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "channel": channel,
            "text": fallback,
            "blocks": blocks,
            "unfurl_links": False,
            "unfurl_media": False,
        },
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error')} — response: {data}")
    return data


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")
    if not token or not channel:
        print("ERROR: SLACK_BOT_TOKEN and SLACK_CHANNEL must be set.", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) > 1:
        run_id = int(sys.argv[1])
    else:
        conn = get_connection()
        try:
            run_id = latest_run_id(conn)
        finally:
            conn.close()
        if run_id is None:
            print("ERROR: no runs found in database.", file=sys.stderr)
            sys.exit(1)

    blocks, fallback = build_blocks(run_id)
    print(json.dumps(blocks, indent=2, ensure_ascii=False))
    print(f"\nFallback: {fallback}")
    print("\n--- Posting to Slack ---")
    result = post_to_slack(token, channel, blocks, fallback)
    print(f"Posted to {result.get('channel')} ts={result.get('ts')}")


if __name__ == "__main__":
    main()
