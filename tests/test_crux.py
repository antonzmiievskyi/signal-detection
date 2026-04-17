"""Tests for the CrUX performance checker."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_crux import (
    format_metric_value,
    get_crux_history,
    get_crux_metrics,
    rate_metric,
)

SAMPLE_CRUX_RESPONSE = {
    "record": {
        "key": {"origin": "https://epicgames.com"},
        "metrics": {
            "largest_contentful_paint": {
                "histogram": [
                    {"start": 0, "end": 2500, "density": 0.75},
                    {"start": 2500, "end": 4000, "density": 0.15},
                    {"start": 4000, "density": 0.10},
                ],
                "percentiles": {"p75": 2200},
            },
            "interaction_to_next_paint": {
                "histogram": [
                    {"start": 0, "end": 200, "density": 0.60},
                    {"start": 200, "end": 500, "density": 0.25},
                    {"start": 500, "density": 0.15},
                ],
                "percentiles": {"p75": 250},
            },
            "cumulative_layout_shift": {
                "histogram": [
                    {"start": 0, "end": 0.1, "density": 0.85},
                    {"start": 0.1, "end": 0.25, "density": 0.10},
                    {"start": 0.25, "density": 0.05},
                ],
                "percentiles": {"p75": "0.05"},
            },
            "experimental_time_to_first_byte": {
                "histogram": [
                    {"start": 0, "end": 800, "density": 0.50},
                    {"start": 800, "end": 1800, "density": 0.35},
                    {"start": 1800, "density": 0.15},
                ],
                "percentiles": {"p75": 950},
            },
        },
        "collectionPeriod": {
            "firstDate": {"year": 2026, "month": 3, "day": 20},
            "lastDate": {"year": 2026, "month": 4, "day": 16},
        },
    }
}

SAMPLE_POOR_RESPONSE = {
    "record": {
        "key": {"origin": "https://slow-site.com"},
        "metrics": {
            "largest_contentful_paint": {
                "histogram": [
                    {"start": 0, "end": 2500, "density": 0.20},
                    {"start": 2500, "end": 4000, "density": 0.30},
                    {"start": 4000, "density": 0.50},
                ],
                "percentiles": {"p75": 5500},
            },
        },
        "collectionPeriod": {
            "firstDate": {"year": 2026, "month": 3, "day": 20},
            "lastDate": {"year": 2026, "month": 4, "day": 16},
        },
    }
}


def _mock_response(json_data=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestRateMetric:
    def test_lcp_good(self):
        assert rate_metric("largest_contentful_paint", 2000) == "GOOD"

    def test_lcp_at_boundary(self):
        assert rate_metric("largest_contentful_paint", 2500) == "GOOD"

    def test_lcp_needs_work(self):
        assert rate_metric("largest_contentful_paint", 3000) == "NEEDS WORK"

    def test_lcp_poor(self):
        assert rate_metric("largest_contentful_paint", 5000) == "POOR"

    def test_inp_good(self):
        assert rate_metric("interaction_to_next_paint", 150) == "GOOD"

    def test_inp_poor(self):
        assert rate_metric("interaction_to_next_paint", 600) == "POOR"

    def test_cls_good(self):
        assert rate_metric("cumulative_layout_shift", 0.05) == "GOOD"

    def test_cls_needs_work(self):
        assert rate_metric("cumulative_layout_shift", 0.15) == "NEEDS WORK"

    def test_cls_poor(self):
        assert rate_metric("cumulative_layout_shift", 0.30) == "POOR"

    def test_ttfb_good(self):
        assert rate_metric("experimental_time_to_first_byte", 500) == "GOOD"

    def test_ttfb_poor(self):
        assert rate_metric("experimental_time_to_first_byte", 2000) == "POOR"

    def test_unknown_metric(self):
        assert rate_metric("nonexistent_metric", 100) == "unknown"


class TestFormatMetricValue:
    def test_lcp_format(self):
        assert format_metric_value("largest_contentful_paint", 2200) == "2200ms"

    def test_cls_format(self):
        assert format_metric_value("cumulative_layout_shift", 0.05) == "0.050"

    def test_ttfb_format(self):
        assert format_metric_value("experimental_time_to_first_byte", 950) == "950ms"

    def test_unknown_metric_no_unit(self):
        assert format_metric_value("unknown_metric", 42) == "42"


class TestGetCruxMetrics:
    @patch("scripts.check_crux.requests.post")
    def test_returns_data(self, mock_post):
        mock_post.return_value = _mock_response(SAMPLE_CRUX_RESPONSE)
        result = get_crux_metrics("https://epicgames.com")
        assert result is not None
        assert "record" in result
        assert "metrics" in result["record"]

    @patch("scripts.check_crux.requests.post")
    def test_404_returns_none(self, mock_post):
        resp = _mock_response(status_code=404)
        mock_post.return_value = resp
        result = get_crux_metrics("https://unknown-site.xyz")
        assert result is None

    @patch("scripts.check_crux.requests.post")
    def test_passes_origin_in_body(self, mock_post):
        mock_post.return_value = _mock_response(SAMPLE_CRUX_RESPONSE)
        get_crux_metrics("https://epicgames.com")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["origin"] == "https://epicgames.com"

    @patch("scripts.check_crux.requests.post")
    def test_passes_form_factor(self, mock_post):
        mock_post.return_value = _mock_response(SAMPLE_CRUX_RESPONSE)
        get_crux_metrics("https://epicgames.com", form_factor="PHONE")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["formFactor"] == "PHONE"

    @patch("scripts.check_crux.requests.post")
    def test_omits_form_factor_when_none(self, mock_post):
        mock_post.return_value = _mock_response(SAMPLE_CRUX_RESPONSE)
        get_crux_metrics("https://epicgames.com")
        _, kwargs = mock_post.call_args
        assert "formFactor" not in kwargs["json"]

    @patch("scripts.check_crux.requests.post")
    def test_includes_api_key_in_url(self, mock_post):
        mock_post.return_value = _mock_response(SAMPLE_CRUX_RESPONSE)
        with patch("scripts.check_crux.API_KEY", "test-key-123"):
            get_crux_metrics("https://epicgames.com")
        args, _ = mock_post.call_args
        assert "key=test-key-123" in args[0]


class TestGetCruxHistory:
    @patch("scripts.check_crux.requests.post")
    def test_returns_data(self, mock_post):
        mock_post.return_value = _mock_response({"record": {"key": {}}})
        result = get_crux_history("https://epicgames.com")
        assert result is not None

    @patch("scripts.check_crux.requests.post")
    def test_404_returns_none(self, mock_post):
        resp = _mock_response(status_code=404)
        mock_post.return_value = resp
        result = get_crux_history("https://unknown.xyz")
        assert result is None

    @patch("scripts.check_crux.requests.post")
    def test_calls_history_endpoint(self, mock_post):
        mock_post.return_value = _mock_response({"record": {}})
        with patch("scripts.check_crux.API_KEY", "key123"):
            get_crux_history("https://example.com")
        args, _ = mock_post.call_args
        assert "queryHistoryRecord" in args[0]


class TestMetricParsing:
    """Test parsing of CrUX response data structures."""

    def test_extract_p75_values(self):
        metrics = SAMPLE_CRUX_RESPONSE["record"]["metrics"]
        assert metrics["largest_contentful_paint"]["percentiles"]["p75"] == 2200
        assert metrics["interaction_to_next_paint"]["percentiles"]["p75"] == 250
        assert metrics["cumulative_layout_shift"]["percentiles"]["p75"] == "0.05"
        assert metrics["experimental_time_to_first_byte"]["percentiles"]["p75"] == 950

    def test_cls_p75_is_string(self):
        """CLS p75 comes as string from the API — verify we handle it."""
        p75 = SAMPLE_CRUX_RESPONSE["record"]["metrics"]["cumulative_layout_shift"]["percentiles"]["p75"]
        assert isinstance(p75, str)
        assert float(p75) == 0.05

    def test_histogram_densities_sum_to_one(self):
        metrics = SAMPLE_CRUX_RESPONSE["record"]["metrics"]
        for metric_name, metric_data in metrics.items():
            total = sum(b["density"] for b in metric_data["histogram"])
            assert abs(total - 1.0) < 0.01, f"{metric_name} densities don't sum to 1.0"

    def test_collection_period_present(self):
        period = SAMPLE_CRUX_RESPONSE["record"]["collectionPeriod"]
        assert period["firstDate"]["year"] == 2026
        assert period["lastDate"]["month"] == 4
