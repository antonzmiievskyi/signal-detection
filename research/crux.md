# CrUX (Chrome User Experience Report) -- Detailed Research

## Overview

CrUX (Chrome User Experience Report) is a public dataset provided by Google that reflects
how real-world Chrome users experience popular destinations on the web. It is the official
dataset for Google's Web Vitals program and feeds into Google Search's page experience
ranking signals.

Data is collected from real Chrome browser sessions on supported platforms (desktop Chrome
on Windows, macOS, ChromeOS, Linux; and Android Chrome including Custom Tabs and WebAPKs).
Users must meet all of the following eligibility criteria to contribute data:

1. Usage statistics reporting is enabled
2. Browser history sync is enabled
3. No Sync passphrase is set
4. Running on a supported platform

Notable exclusions: Chrome on iOS, Android WebView, and non-Chrome Chromium browsers do
not contribute data.

Origins and pages must be publicly discoverable (HTTP 200, no noindex) and meet a minimum
traffic threshold (exact number undisclosed) to appear in the dataset.

## Metrics Available

### Core Web Vitals
- **LCP (Largest Contentful Paint):** Measures loading performance -- the time until the
  largest content element is rendered. API field: `largest_contentful_paint`.
- **INP (Interaction to Next Paint):** Measures interactivity/responsiveness -- the latency
  of user interactions. API field: `interaction_to_next_paint`. (Replaced FID as of
  March 2024.)
- **CLS (Cumulative Layout Shift):** Measures visual stability -- how much the page layout
  shifts unexpectedly. API field: `cumulative_layout_shift`.

### Other Metrics
- **FCP (First Contentful Paint):** Time until the first content is rendered on screen.
  API field: `first_contentful_paint`.
- **TTFB (Time to First Byte):** Time from navigation start to the first byte of the
  response. API field: `experimental_time_to_first_byte`.
- **RTT (Round Trip Time):** Network round-trip time. API field: `round_trip_time`.

### Breakdown Metrics (API)
- `navigation_types` -- distribution of navigation types (e.g., navigate, reload,
  back-forward, prerender, etc.)
- `form_factors` -- distribution across DESKTOP, PHONE, TABLET
- LCP sub-part metrics: `largest_contentful_paint_resource_type`,
  `largest_contentful_paint_image_time_to_first_byte`,
  `largest_contentful_paint_image_resource_load_delay`,
  `largest_contentful_paint_image_resource_load_duration`,
  `largest_contentful_paint_image_element_render_delay`

### What These Metrics Tell Us
These metrics characterize user-perceived performance: how fast a page loads (LCP, FCP,
TTFB), how responsive it is to interaction (INP), and how visually stable it is (CLS).
They do NOT measure availability or uptime -- a site that is completely down would simply
have no data, not bad metrics.

## API Access

### CrUX API (Daily)
- **Endpoint:** `POST https://chromeuxreport.googleapis.com/v1/records:queryRecord`
- **Authentication:** Google Cloud API key passed as query parameter (`?key=API_KEY`).
  The key is safe to embed in URLs without encoding.
- **Rate limits:** 150 queries per minute per Google Cloud project. No paid tier to
  increase this.
- **Pricing:** Free. No cost.
- **Request format:** JSON body with either `"origin"` or `"url"` plus optional
  `"formFactor"` (DESKTOP, PHONE, TABLET) and `"metrics"` array. Omitting formFactor
  returns aggregated data; omitting metrics returns all available metrics.

Example request body (origin-level):
```json
{
  "origin": "https://example.com",
  "formFactor": "PHONE",
  "metrics": ["largest_contentful_paint", "cumulative_layout_shift"]
}
```

### CrUX History API
- **Endpoint:** `POST https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord`
- **Provides:** ~25 collection periods (up to 40 via `collectionPeriodCount` parameter),
  covering approximately 6-10 months of historical data.
- **Granularity:** Weekly collection periods, each representing a 28-day rolling window.
  Three weeks of data overlap between successive periods; one week differs.
- **Update schedule:** Mondays around 04:00 UTC, with data through the previous Saturday.
- **Rate limit:** Shares the 150 queries/min limit with the daily API.
- **Response format:** Same metrics as the daily API but in timeseries arrays
  (`histogramTimeseries`, `p75s`, `densities`). Missing data appears as `"NaN"` in
  densities or `null` in percentiles.

## BigQuery Access

### Dataset Location
- **Project:** `chrome-ux-report`
- **Global data:** `chrome-ux-report.all` -- monthly tables named by YYYYMM
- **Country-specific:** `chrome-ux-report.country_CC` (e.g., `country_us`)
- **Experimental:** `chrome-ux-report.experimental` -- partitioned/clustered tables
  with consolidated historical data (`experimental.country`, `experimental.global`)
- **Materialized:** `chrome-ux-report.materialized` -- pre-computed summary tables

### Table Structure (Raw Monthly Tables)
Each table contains columns for:
- `origin`, `effective_connection_type`, `form_factor`
- Metric histograms: `first_paint`, `first_contentful_paint`,
  `largest_contentful_paint`, `dom_content_loaded`, `onload`
- `layout_instability` (CLS), `interaction_to_next_paint`
- `round_trip_time`, `navigation_types`
- Experimental: `permission`, `time_to_first_byte`, `popularity`

### Materialized Summary Tables
1. **`metrics_summary`** -- origin-level monthly metrics with p75 values and
   fast/avg/slow breakdowns
2. **`device_summary`** -- adds form factor dimension
3. **`country_summary`** -- adds country code and device dimensions
4. **`origin_summary`** -- lists all origins in the dataset

Column naming convention: `fast_<metric>`, `avg_<metric>`, `slow_<metric>`,
`p75_<metric>`, plus density fields like `desktopDensity`.

### How to Query
Standard SQL via BigQuery console, `bq` CLI, or client libraries. Example:
```sql
SELECT
  origin,
  p75_lcp,
  fast_lcp,
  avg_lcp,
  slow_lcp
FROM
  `chrome-ux-report.materialized.device_summary`
WHERE
  yyyymm = 202401
  AND device = 'phone'
  AND origin = 'https://example.com'
```

### Cost Considerations
- Free tier covers basic exploration (1 TB/month of query processing).
- Historical data goes back to 2017.
- New Google Cloud users get signup credits, but a credit card is required.
- The experimental tables use clustering/partitioning for better query performance
  and lower costs.

### Release Schedule
Data is released on the second Tuesday of the following month (i.e., January data
becomes available on the second Tuesday of February).

## Data Characteristics

- **28-day rolling average:** Both the API and BigQuery data represent aggregated
  metrics over a trailing 28-day collection window, not point-in-time snapshots.
- **API update frequency:** Updated daily on a best-effort basis, approximately 04:00 UTC.
- **Data lag:** Approximately 2 days behind the current date (PST timezone).
- **History API updates:** Weekly on Mondays.
- **BigQuery updates:** Monthly, released on the second Tuesday of the following month.
- **Minimum data threshold:** Origins and pages must meet an undisclosed minimum visitor
  count to be included. Pages below the threshold are excluded entirely.
- **Privacy protections:** A small amount of randomness is applied to prevent
  reverse-engineering of user data. Origins losing over 20% of traffic to ineligible
  dimension combinations are excluded.
- **No real-time or hourly data:** The finest granularity available is a 28-day window,
  updated daily (API) or weekly (History API) or monthly (BigQuery).

## Python Integration

### How to Call the API
Use the `requests` library to POST to the CrUX API endpoint with a JSON body.

### Example Code
```python
import requests

API_KEY = "YOUR_GOOGLE_CLOUD_API_KEY"
ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"

def get_crux_metrics(origin: str, form_factor: str = None) -> dict:
    """Query CrUX API for an origin's performance metrics."""
    url = f"{ENDPOINT}?key={API_KEY}"
    body = {"origin": origin}
    if form_factor:
        body["formFactor"] = form_factor  # DESKTOP, PHONE, or TABLET

    response = requests.post(url, json=body)
    response.raise_for_status()
    return response.json()

# Example usage
result = get_crux_metrics("https://example.com", "PHONE")
metrics = result["record"]["metrics"]

# Extract p75 values
p75_lcp = metrics["largest_contentful_paint"]["percentiles"]["p75"]
p75_cls = metrics["cumulative_layout_shift"]["percentiles"]["p75"]
p75_fcp = metrics["first_contentful_paint"]["percentiles"]["p75"]
p75_inp = metrics["interaction_to_next_paint"]["percentiles"]["p75"]
p75_ttfb = metrics["experimental_time_to_first_byte"]["percentiles"]["p75"]

print(f"LCP p75: {p75_lcp}ms, CLS p75: {p75_cls}, INP p75: {p75_inp}ms")
```

### Response Format and Key Fields
```json
{
  "record": {
    "key": {
      "origin": "https://example.com",
      "formFactor": "PHONE"
    },
    "metrics": {
      "largest_contentful_paint": {
        "histogram": [
          {"start": 0, "end": 2500, "density": 0.7524},
          {"start": 2500, "end": 4000, "density": 0.1456},
          {"start": 4000, "density": 0.1020}
        ],
        "percentiles": {
          "p75": 2830
        }
      }
    },
    "collectionPeriod": {
      "firstDate": {"year": 2024, "month": 1, "day": 15},
      "lastDate": {"year": 2024, "month": 2, "day": 11}
    }
  }
}
```

The histogram bins divide data into three ranges corresponding to "good", "needs
improvement", and "poor" thresholds. Density values are fractions that sum to ~1.0.
Most values are rounded to 4 decimal places; CLS is rounded to 2 decimal places.

## Limitations for Outage Detection

1. **28-day rolling average is too slow:** An outage lasting hours or even a few days
   would be diluted across the 28-day window, making it nearly invisible in the metrics.
2. **Measures performance, not availability:** CrUX captures how fast pages load for
   users who successfully loaded them. If a site is down, there are simply no data
   points -- not degraded data points.
3. **No way to see sudden drops on a specific day:** The API provides a single 28-day
   aggregate snapshot. The History API provides weekly snapshots of 28-day windows.
   Neither can isolate a single day's performance.
4. **Minimum traffic threshold excludes smaller sites:** Sites or pages below the
   undisclosed popularity threshold have no data at all.
5. **Historical daily data only in BigQuery, but still monthly tables:** BigQuery data
   is released monthly and still uses aggregated 28-day windows. There is no daily
   granular breakdown in any CrUX data source.
6. **2-day data lag:** Even the "daily" API update runs ~2 days behind, further
   reducing usefulness for detecting current issues.
7. **No error rate or HTTP status code data:** CrUX does not track 5xx errors,
   connection failures, or other availability signals.

## Relevance to Our Use Case

- **NOT suitable for real-time or recent outage detection.** The 28-day rolling average
  fundamentally prevents detection of short-duration incidents. A 4-hour outage would
  shift the 28-day average by less than 1%.
- **Could show long-term performance degradation trends.** If a company's infrastructure
  degrades over weeks or months, this would gradually appear in CrUX metrics (rising LCP,
  worsening INP, etc.).
- **BigQuery historical data might show monthly shifts but still averaged.** Comparing
  month-over-month p75 values could reveal sustained degradation, but cannot pinpoint
  when an incident occurred.
- **Better suited for "is this company's site generally slow" than "did they have an
  outage."** CrUX answers the question of general performance quality, not incident
  detection.
- **Absence of data could theoretically signal issues.** If a previously-reported origin
  disappears from CrUX (falls below traffic threshold), it could indicate a major,
  sustained problem -- but this is an extremely coarse signal.
- **Lowest priority data source for our use case.** For detecting service outages or
  incidents, CrUX is far inferior to status page monitoring, Downdetector-style
  crowdsourced reports, or synthetic monitoring. It should be deprioritized accordingly.

## Sources

- https://developer.chrome.com/docs/crux
- https://developer.chrome.com/docs/crux/api
- https://developer.chrome.com/docs/crux/bigquery
- https://developer.chrome.com/docs/crux/history-api
- https://developer.chrome.com/docs/crux/methodology
- https://screenspan.net/blog/crux-web-vitals-python/
