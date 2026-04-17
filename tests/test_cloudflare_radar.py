"""Tests for the Cloudflare Radar outage checker."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_cloudflare_radar import (
    get_outage_counts_by_location,
    get_outages,
    load_companies,
)

SAMPLE_COMPANIES = [
    {"company": "Epic Games", "domain": "epicgames.com", "industry": "Gaming", "country": "US",
     "downdetector_slug": "epic-games-store"},
    {"company": "Ubisoft", "domain": "ubisoft.com", "industry": "Gaming", "country": "FR",
     "downdetector_slug": "ubisoft"},
]

SAMPLE_OUTAGES_RESPONSE = {
    "result": {
        "annotations": [
            {
                "id": "outage-1",
                "asns": [12345],
                "asnsDetails": [{"asn": 12345, "name": "Example ISP", "locations": ["US"]}],
                "locations": ["US"],
                "locationsDetails": [{"code": "US", "name": "United States"}],
                "outage": {"outageCause": "POWER_OUTAGE", "outageType": "REGIONAL"},
                "startDate": "2026-04-10T08:00:00Z",
                "endDate": "2026-04-10T14:00:00Z",
                "description": "Power outage in eastern US",
            },
            {
                "id": "outage-2",
                "asns": [67890],
                "asnsDetails": [{"asn": 67890, "name": "Another ISP", "locations": ["US"]}],
                "locations": ["US"],
                "locationsDetails": [{"code": "US", "name": "United States"}],
                "outage": {"outageCause": "CABLE_CUT", "outageType": "NATIONWIDE"},
                "startDate": "2026-04-12T10:00:00Z",
                "endDate": None,
                "description": None,
            },
        ]
    },
    "success": True,
}

SAMPLE_LOCATIONS_RESPONSE = {
    "result": {
        "annotations": [
            {"clientCountryAlpha2": "US", "clientCountryName": "United States", "value": "15"},
            {"clientCountryAlpha2": "FR", "clientCountryName": "France", "value": "3"},
            {"clientCountryAlpha2": "RU", "clientCountryName": "Russia", "value": "42"},
        ]
    },
    "success": True,
}


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestLoadCompanies:
    def test_loads_from_file(self, tmp_path):
        f = tmp_path / "companies.json"
        f.write_text(json.dumps(SAMPLE_COMPANIES))
        with patch("scripts.check_cloudflare_radar.COMPANIES_FILE", str(f)):
            result = load_companies()
        assert len(result) == 2
        assert result[0]["company"] == "Epic Games"

    def test_extracts_countries(self, tmp_path):
        f = tmp_path / "companies.json"
        f.write_text(json.dumps(SAMPLE_COMPANIES))
        with patch("scripts.check_cloudflare_radar.COMPANIES_FILE", str(f)):
            companies = load_companies()
        countries = sorted(set(c["country"] for c in companies))
        assert countries == ["FR", "US"]


class TestGetOutages:
    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_returns_annotations(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_OUTAGES_RESPONSE)
        result = get_outages(date_range="7d")
        assert len(result) == 2
        assert result[0]["id"] == "outage-1"
        assert result[0]["outage"]["outageCause"] == "POWER_OUTAGE"

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_passes_location_param(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_OUTAGES_RESPONSE)
        get_outages(date_range="30d", location="US")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["location"] == "US"

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_omits_location_when_none(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_OUTAGES_RESPONSE)
        get_outages(date_range="30d", location=None)
        _, kwargs = mock_get.call_args
        assert "location" not in kwargs["params"]

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_passes_auth_header(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_OUTAGES_RESPONSE)
        with patch("scripts.check_cloudflare_radar.TOKEN", "test-token-123"):
            get_outages()
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-token-123"

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_empty_result(self, mock_get):
        mock_get.return_value = _mock_response({"result": {"annotations": []}, "success": True})
        result = get_outages()
        assert result == []

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_handles_missing_result_key(self, mock_get):
        mock_get.return_value = _mock_response({"success": True})
        result = get_outages()
        assert result == []

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_http_error_raises(self, mock_get):
        resp = _mock_response({})
        resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_get.return_value = resp
        with pytest.raises(Exception, match="401"):
            get_outages()


class TestGetOutageCountsByLocation:
    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_returns_location_counts(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_LOCATIONS_RESPONSE)
        result = get_outage_counts_by_location("30d")
        assert len(result) == 3
        assert result[0]["clientCountryAlpha2"] == "US"
        assert result[0]["value"] == "15"

    @patch("scripts.check_cloudflare_radar.requests.get")
    def test_passes_date_range(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_LOCATIONS_RESPONSE)
        get_outage_counts_by_location("7d")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["dateRange"] == "7d"


class TestOutageDataParsing:
    """Test that outage data fields are correctly structured."""

    def test_outage_has_required_fields(self):
        outage = SAMPLE_OUTAGES_RESPONSE["result"]["annotations"][0]
        assert "startDate" in outage
        assert "outage" in outage
        assert "outageCause" in outage["outage"]
        assert "outageType" in outage["outage"]
        assert "locations" in outage

    def test_ongoing_outage_has_null_end(self):
        outage = SAMPLE_OUTAGES_RESPONSE["result"]["annotations"][1]
        assert outage["endDate"] is None

    def test_asn_details_structure(self):
        outage = SAMPLE_OUTAGES_RESPONSE["result"]["annotations"][0]
        asn = outage["asnsDetails"][0]
        assert "asn" in asn
        assert "name" in asn
        assert isinstance(asn["asn"], int)
