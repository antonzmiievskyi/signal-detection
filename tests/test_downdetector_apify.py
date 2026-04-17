"""Tests for the Downdetector Apify checker."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_downdetector_apify import (
    fetch_page_via_apify,
    fetch_pages_via_apify,
    parse_downdetector_html,
    process_fetch_result,
)

PAGE_NO_PROBLEMS = """
<html>
<body>
<h2>No problems at Epic Games Store</h2>
<script>
var series = [{data: [{x: '2026-04-17 08:00', y: 2}, {x: '2026-04-17 08:15', y: 1},
{x: '2026-04-17 08:30', y: 3}, {x: '2026-04-17 08:45', y: 0},
{x: '2026-04-17 09:00', y: 1}, {x: '2026-04-17 09:15', y: 2},
{x: '2026-04-17 09:30', y: 1}, {x: '2026-04-17 09:45', y: 0}]}];
</script>
</body>
</html>
"""

PAGE_PROBLEMS = """
<html>
<body>
<h2>Problems at Steam</h2>
<script>
var series = [{data: [{x: '2026-04-17 08:00', y: 50}, {x: '2026-04-17 08:15', y: 120},
{x: '2026-04-17 08:30', y: 200}, {x: '2026-04-17 08:45', y: 180},
{x: '2026-04-17 09:00', y: 150}, {x: '2026-04-17 09:15', y: 90},
{x: '2026-04-17 09:30', y: 60}, {x: '2026-04-17 09:45', y: 30}]}];
</script>
</body>
</html>
"""

PAGE_CLOUDFLARE = """
<html>
<div id="challenge-platform">Verifying...</div>
</html>
"""

PAGE_UNPARSEABLE = """
<html><body><p>Something else entirely</p></body></html>
"""


class TestParseDowndetectorHtml:
    """Tests use fallback (title-based) parsing by disabling AI."""

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_title_no_problems(self):
        html = "<html><head><title>Steam - No problems detected</title></head><body></body></html>"
        result = parse_downdetector_html(html, "steam")
        assert result["status"] == "ok"
        assert result["outage_detected"] is False

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_title_outage(self):
        html = "<html><head><title>EA down? Current outages and problems - US</title></head><body></body></html>"
        result = parse_downdetector_html(html, "ea")
        assert result["status"] == "ok"
        assert result["outage_detected"] is True
        assert "down?" in result["detail"].lower()

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_no_title_no_status(self):
        result = parse_downdetector_html(PAGE_UNPARSEABLE, "test")
        assert result["outage_detected"] is None

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_url_set_correctly(self):
        result = parse_downdetector_html(PAGE_NO_PROBLEMS, "nintendo")
        assert result["url"] == "https://downdetector.com/status/nintendo/"

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_no_title_falls_back_to_unclear(self):
        html = "<html><body><p>Some content</p></body></html>"
        result = parse_downdetector_html(html, "test")
        assert result["outage_detected"] is None
        assert "no title" in result["detail"].lower()

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "test-key")
    @patch("scripts.check_downdetector_apify.analyze_with_ai")
    def test_ai_analysis_called(self, mock_ai):
        mock_ai.return_value = {
            "outage_detected": True,
            "severity": "major",
            "status_summary": "Server issues",
            "report_trend": "rising",
            "issue_types": ["server", "login"],
            "comment_sentiment": "negative",
            "comment_summary": "Users report crashes",
            "geographic_pattern": None,
            "confidence": "high",
        }
        result = parse_downdetector_html(PAGE_PROBLEMS, "steam")
        assert result["outage_detected"] is True
        assert result["severity"] == "major"
        assert result["comment_summary"] == "Users report crashes"
        mock_ai.assert_called_once()


class TestFetchPageViaApify:
    @patch("scripts.check_downdetector_apify.ApifyClient")
    def test_successful_fetch(self, MockClient):
        mock_client = MockClient.return_value
        mock_actor = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-123"}

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = iter([
            {"url": "https://downdetector.com/status/ea/", "html": "<html>ea</html>", "statusCode": 200},
        ])

        result = fetch_page_via_apify("https://downdetector.com/status/ea/")
        assert result["html"] == "<html>ea</html>"
        assert result["status_code"] == 200

    @patch("scripts.check_downdetector_apify.ApifyClient")
    def test_empty_dataset(self, MockClient):
        mock_client = MockClient.return_value
        mock_actor = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-123"}

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = iter([])

        result = fetch_page_via_apify("https://example.com")
        assert "error" in result
        assert "Empty dataset" in result["error"]

    @patch("scripts.check_downdetector_apify.ApifyClient")
    def test_no_dataset_id(self, MockClient):
        mock_client = MockClient.return_value
        mock_actor = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {}

        result = fetch_page_via_apify("https://example.com")
        assert "error" in result

    @patch("scripts.check_downdetector_apify.ApifyClient")
    def test_actor_exception(self, MockClient):
        mock_client = MockClient.return_value
        mock_actor = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.side_effect = Exception("Actor timed out")

        result = fetch_page_via_apify("https://example.com")
        assert "error" in result
        assert "timed out" in result["error"]

    @patch("scripts.check_downdetector_apify.ApifyClient")
    def test_passes_url_in_input(self, MockClient):
        mock_client = MockClient.return_value
        mock_actor = MagicMock()
        mock_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-123"}

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = iter([{"html": "<html></html>"}])

        fetch_page_via_apify("https://downdetector.com/status/steam/")
        call_kwargs = mock_actor.call.call_args
        run_input = call_kwargs.kwargs.get("run_input") or call_kwargs[1].get("run_input")
        assert run_input["url"] == "https://downdetector.com/status/steam/"


class TestProcessFetchResult:
    def test_cloudflare_not_bypassed(self):
        result = process_fetch_result({"html": PAGE_CLOUDFLARE}, "steam")
        assert result["status"] == "blocked"

    def test_fetch_error(self):
        result = process_fetch_result({"error": "Actor timed out"}, "steam")
        assert result["status"] == "error"
        assert "timed out" in result["detail"]

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_title_outage(self):
        html = "<html><head><title>EA down? Current outages</title></head><body></body></html>"
        result = process_fetch_result({"html": html}, "ea")
        assert result["status"] == "ok"
        assert result["outage_detected"] is True

    @patch("scripts.check_downdetector_apify.OPENAI_API_KEY", "")
    def test_no_problems(self):
        html = "<html><head><title>EA - No problems detected</title></head><body></body></html>"
        result = process_fetch_result({"html": html}, "ea")
        assert result["status"] == "ok"
        assert result["outage_detected"] is False
