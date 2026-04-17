"""Tests for the Tranco List domain ranking checker."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_tranco import (
    analyze_rank_trend,
    get_domain_ranks,
    get_latest_list_metadata,
)

SAMPLE_RANKS = [
    {"date": "2026-04-01", "rank": 500},
    {"date": "2026-04-02", "rank": 510},
    {"date": "2026-04-03", "rank": 490},
    {"date": "2026-04-04", "rank": 520},
    {"date": "2026-04-05", "rank": 505},
]

SAMPLE_RANKS_BIG_DROP = [
    {"date": "2026-04-01", "rank": 100},
    {"date": "2026-04-05", "rank": 500},
]

SAMPLE_RANKS_IMPROVEMENT = [
    {"date": "2026-04-01", "rank": 10000},
    {"date": "2026-04-05", "rank": 5000},
]

SAMPLE_LIST_METADATA = {
    "list_id": "VQYYN",
    "available": True,
    "download": "https://tranco-list.eu/download/VQYYN/1000000",
    "created_on": "2026-04-16T22:00:02.023104",
    "failed": False,
}


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestAnalyzeRankTrend:
    def test_empty_ranks_returns_no_data(self):
        result = analyze_rank_trend([])
        assert result["status"] == "no_data"

    def test_stable_trend(self):
        result = analyze_rank_trend(SAMPLE_RANKS)
        assert result["status"] == "ranked"
        assert result["current_rank"] == 505
        assert result["oldest_rank"] == 500
        assert result["best_rank"] == 490
        assert result["worst_rank"] == 520
        assert result["data_points"] == 5

    def test_change_calculated_correctly(self):
        result = analyze_rank_trend(SAMPLE_RANKS)
        assert result["change"] == 5  # 505 - 500

    def test_big_drop_detected(self):
        result = analyze_rank_trend(SAMPLE_RANKS_BIG_DROP)
        assert result["current_rank"] == 500
        assert result["oldest_rank"] == 100
        assert result["change"] == 400
        assert result["pct_change"] == 400.0

    def test_improvement_detected(self):
        result = analyze_rank_trend(SAMPLE_RANKS_IMPROVEMENT)
        assert result["current_rank"] == 5000
        assert result["change"] == -5000  # improved (lower rank number)
        assert result["pct_change"] == -50.0

    def test_single_data_point(self):
        result = analyze_rank_trend([{"date": "2026-04-01", "rank": 300}])
        assert result["status"] == "ranked"
        assert result["current_rank"] == 300
        assert result["change"] == 0
        assert result["data_points"] == 1

    def test_sorts_by_date(self):
        # Pass in reverse order — should still get correct current/oldest
        reversed_ranks = list(reversed(SAMPLE_RANKS))
        result = analyze_rank_trend(reversed_ranks)
        assert result["oldest_rank"] == 500  # earliest date
        assert result["current_rank"] == 505  # latest date

    def test_avg_rank(self):
        result = analyze_rank_trend(SAMPLE_RANKS)
        expected_avg = round((500 + 510 + 490 + 520 + 505) / 5)
        assert result["avg_rank"] == expected_avg

    def test_date_range_string(self):
        result = analyze_rank_trend(SAMPLE_RANKS)
        assert result["date_range"] == "2026-04-01 to 2026-04-05"


class TestGetDomainRanks:
    @patch("scripts.check_tranco.requests.get")
    def test_returns_ranks_list(self, mock_get):
        mock_get.return_value = _mock_response({"ranks": SAMPLE_RANKS})
        result = get_domain_ranks("example.com")
        assert len(result) == 5
        assert result[0]["rank"] == 500

    @patch("scripts.check_tranco.requests.get")
    def test_calls_correct_url(self, mock_get):
        mock_get.return_value = _mock_response({"ranks": []})
        get_domain_ranks("epicgames.com")
        mock_get.assert_called_once_with(
            "https://tranco-list.eu/api/ranks/domain/epicgames.com", timeout=15
        )

    @patch("scripts.check_tranco.requests.get")
    def test_domain_not_ranked(self, mock_get):
        mock_get.return_value = _mock_response({"ranks": []})
        result = get_domain_ranks("unknown-domain.xyz")
        assert result == []

    @patch("scripts.check_tranco.requests.get")
    def test_missing_ranks_key(self, mock_get):
        mock_get.return_value = _mock_response({})
        result = get_domain_ranks("example.com")
        assert result == []

    @patch("scripts.check_tranco.requests.get")
    def test_http_error_raises(self, mock_get):
        resp = _mock_response({})
        resp.raise_for_status.side_effect = Exception("429 Rate Limited")
        mock_get.return_value = resp
        with pytest.raises(Exception, match="429"):
            get_domain_ranks("example.com")


class TestGetLatestListMetadata:
    @patch("scripts.check_tranco.requests.get")
    def test_returns_metadata(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_LIST_METADATA)
        result = get_latest_list_metadata()
        assert result["list_id"] == "VQYYN"
        assert result["available"] is True

    @patch("scripts.check_tranco.requests.get")
    def test_calls_correct_url(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_LIST_METADATA)
        get_latest_list_metadata()
        mock_get.assert_called_once_with(
            "https://tranco-list.eu/api/lists/date/latest", timeout=15
        )
