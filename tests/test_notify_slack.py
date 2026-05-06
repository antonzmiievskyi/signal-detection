"""Tests for the Slack notifier helpers."""

import os
import tempfile

from scripts.notify_slack import (
    extract_actionable_signals,
    md_to_slack_mrkdwn,
)


SAMPLE_REPORT = """\
Signal Detection Report — 2026-05-06 14:00 UTC

## 1. Signal Strength Rating
| Acme | NONE | nothing |

## 2. Vendor Agreement Matrix
some matrix

## 3. Actionable Signals (Ranked by Priority)

### 1. Aeza (Hosting, RU)
- **What happened:** Large-scale DDoS confirmed by Cloudflare Radar.
- **Vendors confirming:** Cloudflare Radar, Tranco
- **Suggested outreach angle:** DDoS mitigation; emphasize rapid recovery.
- **Timing recommendation:** Immediate outreach.

### 2. Found (Banking, US)
- **What happened:** Card payment failures reported on Downdetector.
- **Vendors confirming:** Downdetector
- **Suggested outreach angle:** Application-layer resilience for payments.
- **Timing recommendation:** Near-term.

## 4. Data Quality Assessment
| vendor | usefulness |

### Summary
extra notes
"""


def _write_report(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w") as f:
        f.write(content)
    return path


class TestExtractActionableSignals:
    def test_parses_all_top_level_leads(self):
        path = _write_report(SAMPLE_REPORT)
        try:
            leads = extract_actionable_signals(path)
        finally:
            os.unlink(path)
        assert [l["company"] for l in leads] == ["Aeza", "Found"]

    def test_extracts_each_field(self):
        path = _write_report(SAMPLE_REPORT)
        try:
            leads = extract_actionable_signals(path)
        finally:
            os.unlink(path)
        aeza = leads[0]
        assert "DDoS" in aeza["summary"]
        assert "Cloudflare Radar" in aeza["vendors"]
        assert "DDoS mitigation" in aeza["angle"]
        assert "Immediate" in aeza["timing"]

    def test_stops_at_next_top_level_section_not_at_subitems(self):
        # The "### Summary" subsection sits between the items and should not
        # be misread as another lead, and "## 4. Data Quality Assessment"
        # is the real boundary.
        path = _write_report(SAMPLE_REPORT)
        try:
            leads = extract_actionable_signals(path)
        finally:
            os.unlink(path)
        assert "Summary" not in [l["company"] for l in leads]
        assert "Data Quality" not in [l["company"] for l in leads]

    def test_missing_file_returns_empty(self):
        assert extract_actionable_signals("/nonexistent/path.txt") == []

    def test_report_without_section_returns_empty(self):
        path = _write_report("# Random report\n\nNo actionable section here.\n")
        try:
            leads = extract_actionable_signals(path)
        finally:
            os.unlink(path)
        assert leads == []


class TestMdToSlackMrkdwn:
    def test_converts_double_to_single_asterisk_bold(self):
        assert md_to_slack_mrkdwn("**hello**") == "*hello*"

    def test_leaves_non_bold_alone(self):
        assert md_to_slack_mrkdwn("plain text with _italic_") == "plain text with _italic_"

    def test_handles_multiple_bolds(self):
        assert md_to_slack_mrkdwn("**a** and **b**") == "*a* and *b*"
