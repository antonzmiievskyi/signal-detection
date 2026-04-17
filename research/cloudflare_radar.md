# Cloudflare Radar — Detailed Research

## Overview

Cloudflare Radar is a free, publicly accessible hub that showcases global Internet traffic,
attacks, and technology trends. It is powered by two primary data sources:

1. **Cloudflare's global network** — operational data from their distributed infrastructure
   (one of the largest networks in the world).
2. **Cloudflare's 1.1.1.1 public DNS resolver** — aggregated and anonymized DNS query data.

The **Cloudflare Radar Outage Center (CROC)** is a specific feature within Radar that
provides data on Internet outages occurring around the world. It tracks disruptions at
the country and ASN (Autonomous System Number) level, categorizing them by cause, type,
and scope. CROC cross-references outage data with NetFlows and HTTP request metrics to
analyze impact patterns (e.g., differences between mobile and desktop traffic).

**Data License:** CC BY-NC 4.0 (non-commercial use).

## API Access

### Authentication

- Create a **Custom API Token** in the Cloudflare dashboard.
- Permission required: **Account > Radar > Read**.
- Include the token in every request via the `Authorization` header:
  ```
  Authorization: Bearer <API_TOKEN>
  ```
- No Cloudflare paid plan is required — Radar API is available on all plans, including free.

### Base URL

```
https://api.cloudflare.com/client/v4/radar/
```

### Rate Limits

The official documentation does not publish specific rate limit numbers for the Radar API.
This is a notable gap — in practice, standard Cloudflare API rate limits likely apply
(historically 1200 requests per 5 minutes for Cloudflare APIs generally, but this is
unconfirmed for Radar specifically).

### Pricing

- **Free.** Cloudflare states the API is free and available to "data enthusiasts, academics,
  and others who want access to Internet traffic data."
- The data license (CC BY-NC 4.0) restricts commercial use of the data.

## Key Endpoints for Outage Detection

### 1. Get Internet Outages and Anomalies

```
GET /radar/annotations/outages
```

Full URL: `https://api.cloudflare.com/client/v4/radar/annotations/outages`

**Query Parameters:**

| Parameter   | Type   | Required | Description                                              |
|-------------|--------|----------|----------------------------------------------------------|
| `asn`       | number | No       | Filter by Autonomous System Number (single integer)      |
| `location`  | string | No       | Filter by alpha-2 country code (e.g., "US", "UA")        |
| `dateRange` | string | No       | Predefined range (e.g., "7d", "1d", "30d")               |
| `dateStart` | string | No       | Start of date range (inclusive), ISO 8601 format          |
| `dateEnd`   | string | No       | End of date range (inclusive), ISO 8601 format            |
| `origin`    | string | No       | Filter by origin                                         |
| `format`    | string | No       | Response format: "JSON" or "CSV"                         |
| `limit`     | number | No       | Maximum number of objects returned                       |
| `offset`    | number | No       | Number of objects to skip (for pagination)               |

**Example request:**
```bash
curl "https://api.cloudflare.com/client/v4/radar/annotations/outages?dateRange=7d&format=json&location=US" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"
```

### 2. Get Outage Count by Location

```
GET /radar/annotations/outages/locations
```

Full URL: `https://api.cloudflare.com/client/v4/radar/annotations/outages/locations`

**Query Parameters:**

| Parameter   | Type   | Required | Description                                    |
|-------------|--------|----------|------------------------------------------------|
| `dateRange` | string | No       | Predefined date range filter                   |
| `dateStart` | string | No       | Start of date range (inclusive)                 |
| `dateEnd`   | string | No       | End of date range (inclusive)                   |
| `format`    | string | No       | Response format: "JSON" or "CSV"               |
| `limit`     | number | No       | Maximum number of objects returned              |

Returns a count of outages per country — useful for identifying which regions are
most affected over a time period.

## Data Format

### Outage Annotations Response

```json
{
  "result": {
    "annotations": [
      {
        "id": "string",
        "asns": [12345],
        "asnsDetails": [
          {
            "asn": 12345,
            "name": "Example ISP",
            "locations": ["US"]
          }
        ],
        "dataSource": "string",
        "eventType": "string",
        "locations": ["US"],
        "locationsDetails": [
          {
            "code": "US",
            "name": "United States"
          }
        ],
        "origins": ["string"],
        "originsDetails": [
          {
            "name": "string",
            "origin": "string"
          }
        ],
        "outage": {
          "outageCause": "POWER_OUTAGE",
          "outageType": "NATIONWIDE"
        },
        "startDate": "2024-01-15T08:00:00Z",
        "endDate": "2024-01-15T14:00:00Z",
        "description": "Optional description text",
        "linkedUrl": "https://example.com/reference",
        "scope": "Optional scope detail"
      }
    ]
  },
  "success": true
}
```

### Key Fields Explained

- **`outage.outageCause`** — Root cause classification. Known values include:
  `POWER_OUTAGE`, `WEATHER`, government shutdowns, natural disasters, cable cuts,
  infrastructure failures. (The API does not document the complete enum; these are
  values observed in practice.)
- **`outage.outageType`** — Scope classification. Known values: `REGIONAL`, `NATIONWIDE`,
  or single network provider.
- **`asns` / `asnsDetails`** — The affected Autonomous Systems, with names and locations.
- **`locations` / `locationsDetails`** — Alpha-2 country codes and names.
- **`startDate` / `endDate`** — ISO 8601 timestamps. `endDate` is optional (may be null
  for ongoing outages).
- **`scope`** — Optional further geographic detail (state, city, or network).
- **`linkedUrl`** — Reference link to external reporting or blog post.

### Outage Locations Response

```json
{
  "result": {
    "annotations": [
      {
        "clientCountryAlpha2": "PT",
        "clientCountryName": "Portugal",
        "value": "10"
      }
    ]
  },
  "success": true
}
```

## Python Integration

There is no official Cloudflare Python SDK specifically for Radar. Use the `requests`
library directly.

```python
import requests
from datetime import datetime, timedelta

CLOUDFLARE_RADAR_TOKEN = "your_api_token_here"
BASE_URL = "https://api.cloudflare.com/client/v4/radar"

def get_outages(
    date_range: str = "7d",
    location: str | None = None,
    asn: int | None = None,
    limit: int = 100,
) -> dict:
    """Fetch recent Internet outages from Cloudflare Radar."""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_RADAR_TOKEN}",
    }
    params = {
        "dateRange": date_range,
        "format": "json",
        "limit": limit,
    }
    if location:
        params["location"] = location
    if asn:
        params["asn"] = asn

    response = requests.get(
        f"{BASE_URL}/annotations/outages",
        headers=headers,
        params=params,
    )
    response.raise_for_status()
    return response.json()


def get_outage_counts_by_location(date_range: str = "30d") -> dict:
    """Get outage counts per country over a date range."""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_RADAR_TOKEN}",
    }
    params = {
        "dateRange": date_range,
        "format": "json",
    }
    response = requests.get(
        f"{BASE_URL}/annotations/outages/locations",
        headers=headers,
        params=params,
    )
    response.raise_for_status()
    return response.json()


# Example usage
if __name__ == "__main__":
    data = get_outages(date_range="7d", location="US")
    for annotation in data.get("result", {}).get("annotations", []):
        print(
            f"{annotation['startDate']} | "
            f"{annotation['outage']['outageType']} | "
            f"{annotation['outage']['outageCause']} | "
            f"{', '.join(annotation['locations'])}"
        )
```

## Limitations

### What It Does NOT Cover

- **Company-specific or service-specific outages.** CROC tracks Internet connectivity
  disruptions at the country and ASN level. It does NOT detect application-level outages
  (e.g., "AWS us-east-1 is down" or "Slack is experiencing issues"). It only detects
  when underlying network connectivity drops.
- **Individual website or domain monitoring.** Radar does not monitor whether a specific
  website or service is up or down.
- **Root cause attribution for application outages.** Even when a network outage is
  detected, CROC may not identify the specific service impacted.

### Data Freshness / Delays

- The documentation does not specify exact latency between an outage occurring and it
  appearing in the API. Based on the nature of the data (traffic anomaly detection),
  there is likely some delay (minutes to hours) before an outage is annotated and
  published.
- Some outages may only be annotated retroactively after manual review by Cloudflare's
  team.

### Normalization

- Radar generally does not return raw traffic values. Data is normalized using methods
  like PERCENTAGE, MIN_MAX, MIN0_MAX, or PERCENTAGE_CHANGE. The `result.meta.normalization`
  field indicates which method was applied.
- When comparing values across locations or time ranges with min-max normalization,
  comparisons must be done within the same API request to ensure consistent normalization.

### Other Limitations

- **Non-commercial license (CC BY-NC 4.0):** Data cannot be used for commercial purposes
  without separate licensing.
- **No webhook / push notifications via this API.** Polling is required.
- **Rate limits are undocumented** for the Radar API specifically.
- **ASN-level granularity only.** Cannot drill down to specific IP ranges or subnets.

## Relevance to Our Use Case

### Strengths

- **Free, authoritative data source** for Internet-level outages worldwide.
- **Structured, machine-readable API** with filtering by location and ASN.
- **Cause classification** (power outage, weather, government shutdown, etc.) adds
  context that is hard to get from other sources.
- **Good for detecting infrastructure-level events** that affect target companies
  indirectly — e.g., if a country or major ISP goes down, services hosted there
  would be affected.
- **Historical data available** via date range queries, useful for backtesting and
  correlation analysis.

### Gaps for Company-Specific Outage Detection

- CROC will NOT detect that "Company X's API is returning 500 errors" or "Company Y's
  website is slow." It only sees network-level disruptions.
- To detect outages for specific target companies, we would need to supplement CROC
  with:
  - **Status page monitoring** (e.g., scraping status.company.com endpoints)
  - **Synthetic monitoring** (e.g., pinging specific endpoints)
  - **Social media signals** (e.g., Downdetector, Twitter/X mentions)
  - **Cloud provider status pages** (AWS, GCP, Azure health dashboards)
- CROC is best used as a **contextual enrichment source** — when we detect a company
  outage through other means, we can check CROC to see if there is a correlated
  network-level event that explains it.

### Recommended Integration Pattern

1. **Poll `/radar/annotations/outages`** periodically (e.g., every 15-30 minutes) with
   `dateRange=1d` to catch recent outages.
2. **Filter by ASNs** relevant to target companies if known (e.g., the ASN of their
   hosting provider).
3. **Cross-reference** detected network outages with company-specific signals to
   determine if a company outage correlates with a broader Internet disruption.
4. **Use `/radar/annotations/outages/locations`** for dashboard displays showing
   global outage hotspots.
