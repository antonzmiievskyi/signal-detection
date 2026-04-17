"""Tests for the Provider Status Page checker."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_provider_status import (
    PROVIDERS,
    format_incident,
    get_components,
    get_incidents,
    get_status,
    get_unresolved,
)

SAMPLE_STATUS = {
    "status": {"indicator": "minor", "description": "Minor Service Outage"}
}

SAMPLE_STATUS_OK = {
    "status": {"indicator": "none", "description": "All Systems Operational"}
}

SAMPLE_INCIDENT = {
    "id": "inc-001",
    "name": "API failures",
    "status": "investigating",
    "impact": "major",
    "created_at": "2026-04-16T12:00:00.000Z",
    "updated_at": "2026-04-16T13:00:00.000Z",
    "resolved_at": None,
    "started_at": "2026-04-16T12:00:00.000Z",
    "components": [
        {"name": "API", "status": "partial_outage"},
        {"name": "Dashboard", "status": "degraded_performance"},
    ],
    "incident_updates": [
        {
            "id": "upd-001",
            "status": "investigating",
            "body": "We are investigating increased error rates on the API.",
            "created_at": "2026-04-16T12:30:00.000Z",
        }
    ],
}

SAMPLE_RESOLVED_INCIDENT = {
    "id": "inc-002",
    "name": "DNS resolution delays",
    "status": "resolved",
    "impact": "minor",
    "created_at": "2026-04-15T08:00:00.000Z",
    "updated_at": "2026-04-15T10:00:00.000Z",
    "resolved_at": "2026-04-15T10:00:00.000Z",
    "started_at": "2026-04-15T08:00:00.000Z",
    "components": [{"name": "DNS", "status": "operational"}],
    "incident_updates": [
        {"id": "upd-002", "status": "resolved", "body": "This incident has been resolved.",
         "created_at": "2026-04-15T10:00:00.000Z"},
    ],
}

SAMPLE_COMPONENTS = {
    "components": [
        {"id": "c1", "name": "API", "status": "operational", "group": False},
        {"id": "c2", "name": "CDN", "status": "partial_outage", "group": False},
        {"id": "c3", "name": "Services Group", "status": "partial_outage", "group": True},
        {"id": "c4", "name": "DNS", "status": "degraded_performance", "group": False},
    ]
}


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestProviders:
    def test_all_four_providers_defined(self):
        assert "Cloudflare" in PROVIDERS
        assert "Akamai" in PROVIDERS
        assert "F5" in PROVIDERS
        assert "Imperva" in PROVIDERS

    def test_provider_urls_are_https(self):
        for name, url in PROVIDERS.items():
            assert url.startswith("https://"), f"{name} URL should be HTTPS"


class TestGetStatus:
    @patch("scripts.check_provider_status.requests.get")
    def test_returns_status_dict(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_STATUS)
        result = get_status("https://example.com")
        assert result["indicator"] == "minor"
        assert result["description"] == "Minor Service Outage"

    @patch("scripts.check_provider_status.requests.get")
    def test_calls_correct_endpoint(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_STATUS)
        get_status("https://www.cloudflarestatus.com")
        mock_get.assert_called_once_with(
            "https://www.cloudflarestatus.com/api/v2/status.json", timeout=10
        )

    @patch("scripts.check_provider_status.requests.get")
    def test_ok_status(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_STATUS_OK)
        result = get_status("https://example.com")
        assert result["indicator"] == "none"


class TestGetIncidents:
    @patch("scripts.check_provider_status.requests.get")
    def test_returns_incident_list(self, mock_get):
        mock_get.return_value = _mock_response(
            {"incidents": [SAMPLE_INCIDENT, SAMPLE_RESOLVED_INCIDENT]}
        )
        result = get_incidents("https://example.com")
        assert len(result) == 2

    @patch("scripts.check_provider_status.requests.get")
    def test_empty_incidents(self, mock_get):
        mock_get.return_value = _mock_response({"incidents": []})
        result = get_incidents("https://example.com")
        assert result == []


class TestGetUnresolved:
    @patch("scripts.check_provider_status.requests.get")
    def test_returns_unresolved_only(self, mock_get):
        mock_get.return_value = _mock_response({"incidents": [SAMPLE_INCIDENT]})
        result = get_unresolved("https://example.com")
        assert len(result) == 1
        assert result[0]["status"] == "investigating"

    @patch("scripts.check_provider_status.requests.get")
    def test_calls_unresolved_endpoint(self, mock_get):
        mock_get.return_value = _mock_response({"incidents": []})
        get_unresolved("https://www.akamaistatus.com")
        mock_get.assert_called_once_with(
            "https://www.akamaistatus.com/api/v2/incidents/unresolved.json", timeout=10
        )


class TestGetComponents:
    @patch("scripts.check_provider_status.requests.get")
    def test_returns_all_components(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_COMPONENTS)
        result = get_components("https://example.com")
        assert len(result) == 4

    @patch("scripts.check_provider_status.requests.get")
    def test_filter_degraded_non_group(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_COMPONENTS)
        components = get_components("https://example.com")
        degraded = [c for c in components if c["status"] != "operational" and not c.get("group")]
        assert len(degraded) == 2
        assert degraded[0]["name"] == "CDN"
        assert degraded[1]["name"] == "DNS"


class TestFormatIncident:
    def test_active_incident_shows_ongoing(self):
        output = format_incident(SAMPLE_INCIDENT)
        assert "MAJOR" in output
        assert "API failures" in output
        assert "ONGOING" in output
        assert "API, Dashboard" in output

    def test_resolved_incident_shows_timestamp(self):
        output = format_incident(SAMPLE_RESOLVED_INCIDENT)
        assert "MINOR" in output
        assert "DNS resolution delays" in output
        assert "2026-04-15 10:00" in output

    def test_includes_latest_update(self):
        output = format_incident(SAMPLE_INCIDENT)
        assert "investigating increased error rates" in output

    def test_no_components(self):
        inc = {**SAMPLE_INCIDENT, "components": []}
        output = format_incident(inc)
        assert "N/A" in output

    def test_no_updates(self):
        inc = {**SAMPLE_INCIDENT, "incident_updates": []}
        output = format_incident(inc)
        assert "Latest update" not in output

    def test_truncates_long_update_body(self):
        long_body = "x" * 300
        inc = {**SAMPLE_INCIDENT, "incident_updates": [
            {"id": "u1", "status": "investigating", "body": long_body, "created_at": "2026-04-16T12:00:00Z"}
        ]}
        output = format_incident(inc)
        # Body should be truncated to 200 chars
        assert len(long_body) > 200
        assert "x" * 200 in output
        assert "x" * 201 not in output
