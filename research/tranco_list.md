# Tranco List -- Detailed Research

## Overview

Tranco is a research-oriented top sites ranking designed to be hardened against manipulation. It was created by researchers at imec-DistriNet (KU Leuven), TU Delft, and Universite Grenoble Alpes (LIG), and published alongside a peer-reviewed paper at NDSS 2019.

Tranco was created because existing rankings (especially Alexa) were shown to disagree on which domains are most popular, change significantly on a daily basis, and be vulnerable to manipulation by malicious actors. Tranco improves on these shortcomings by combining multiple source rankings and averaging over time.

Since the Alexa ranking was discontinued (removed from the default Tranco list as of August 1, 2023), Tranco has become the de facto replacement for Alexa in academic and security research. Over 600 academic publications have referenced or used Tranco.

The default list contains one million domains, obtained by averaging all available provider rankings over the past 30 days using the Dowdall rule (scoring items with 1, 1/2, ..., 1/N points). Where source ranks are "bucketed" (coarse ranges), Tranco normalizes each bucket to the geometric mean of its boundaries.

## Data Sources Combined

The current default Tranco list combines five provider rankings:

### Cisco Umbrella
- **Data basis:** DNS traffic to OpenDNS resolvers; claimed over 100 billion daily requests from 65 million users. Domains ranked on unique IPs issuing DNS queries.
- **List size:** 1 million entries, updated daily.
- **Content:** Both websites and infrastructural domains; includes subdomains aggregated to their parent.
- **Licensing:** Available free of charge.
- **Download:** `https://umbrella-static.s3-us-west-1.amazonaws.com/top-1m.csv.zip`

### Majestic
- **Data basis:** Backlinks from a crawl of ~450 billion URLs over 120 days. Sites ranked on the number of referring Class C (/24) subnets.
- **List size:** 1 million entries ("Majestic Million"), updated daily.
- **Content:** Mostly pay-level domains; includes subdomains for very popular sites.
- **Licensing:** Available under a CC BY 3.0 license.
- **Download:** `http://downloads.majestic.com/majestic_million.csv`

### Farsight (DomainTools)
- **Data basis:** Passive DNS traffic from DNSDB dataset. Data originates from organizations sharing "above-resolver" DNS traffic (cache misses sent to authoritative nameservers).
- **List size:** 1 million entries, updated daily.
- **Content:** Both websites and infrastructural domains; only pay-level domains ranked.
- **Integrated into default Tranco list:** Since May 1, 2022.
- **Licensing:** Only available for the default Tranco list (not separately downloadable for custom lists in the same way as others).

### Chrome User Experience Report (CrUX)
- **Data basis:** Browser traffic from opt-in Chrome users. Only "sufficiently popular" origins are included. Monthly update.
- **List size:** Variable; ~18 million entries as of June 2023.
- **Content:** Websites only. Origins are normalized to subdomains.
- **Ranks are bucketed:** Buckets of 1000, 5000, 10000, 50000, 100000, 500000, 1M, 5M, 10M, and remaining.
- **Integrated into default Tranco list:** Since August 1, 2023.
- **Licensing:** Available under a CC BY-SA 4.0 license.
- **Note:** Considered the most accurate ranking in a 2022 study by Ruth et al.

### Cloudflare Radar
- **Data basis:** DNS traffic to Cloudflare's 1.1.1.1 resolver. A machine learning model computes a popularity metric reflecting "the estimated relative size of the user population."
- **List size:** 1 million entries. Updated weekly (top 100 updated daily).
- **Content:** Both websites and infrastructural domains; only pay-level domains ranked.
- **Ranks are bucketed:** Buckets of 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, and 1M. Top 100 are individually ranked.
- **Integrated into default Tranco list:** Since August 1, 2023.
- **Licensing:** Available under a CC BY-NC 4.0 license.

### Deprecated Sources
- **Alexa:** Removed from default list as of August 1, 2023 (service discontinued).
- **Quantcast:** Became unavailable April 1, 2020.

## Access Methods

### CSV Download

**Permanent URL for latest list (no subdomains):**
```
https://tranco-list.eu/top-1m.csv.zip
```

**Permanent URL for latest list (with subdomains):**
```
https://tranco-list.eu/top-1m-incl-subdomains.csv.zip
```

**Get the permanent ID of the current list:**
```
https://tranco-list.eu/top-1m-id
https://tranco-list.eu/top-1m-id?subdomains=true
```

**Retrieve a specific daily list by date:**
```
https://tranco-list.eu/daily_list?date=YYYY-MM-DD
https://tranco-list.eu/daily_list?date=YYYY-MM-DD&subdomains=true
```

**Retrieve a specific list by ID:**
```
https://tranco-list.eu/download/{list_id}/1000000
```

**File format:** CSV with two columns: `rank,domain` (e.g., `1,google.com`). Same format as the old Alexa and Cisco Umbrella lists. Delivered as a ZIP archive.

**Update frequency:** Daily, available by 0:00 UTC. The `Last-Modified` HTTP header provides the exact timestamp.

**Historical lists:** Available back to December 1, 2018.

### Python Package

- **Package name:** `tranco`
- **Install:** `pip install tranco`
- **Latest version:** 0.8.1
- **License:** MIT
- **Author:** Victor Le Pochat
- **Source:** https://github.com/DistriNet/tranco-python-package
- **Dependencies:** `requests`

**Basic usage:**
```python
from tranco import Tranco

# Create a Tranco object with caching enabled
t = Tranco(cache=True, cache_dir='.tranco')

# Retrieve the latest daily list
latest_list = t.list()

# Retrieve a list for a specific date
date_list = t.list(date='2024-01-15')

# Retrieve a list by ID
id_list = t.list(list_id='6P7X')

# With subdomains
sub_list = t.list(subdomains=True)

# Full list (beyond top 1M, if available)
full_list = t.list(full=True)
```

**`list()` method parameters:**
- `date`: Date string in `YYYY-MM-DD` format. If omitted, returns the latest daily list.
- `list_id`: Specific list ID to retrieve. Cannot be combined with `date`.
- `subdomains`: Boolean, whether to include subdomains. Default: `False`.
- `full`: Boolean, whether to retrieve the full list. Default: `False`.

**Working with a `TrancoList` object:**
```python
# Get top N domains
top_10k = latest_list.top(10000)

# Get the list ID (for citation/reproducibility)
latest_list.list_id

# Get the list page URL
latest_list.list_page

# Look up the rank of a specific domain
latest_list.rank("google.com")      # returns integer rank
latest_list.rank("not.in.ranking")  # returns -1
```

**Generating custom lists (requires account):**
```python
t = Tranco(account_email="user@example.com", api_key="YOUR_API_KEY")

c = t.configure({
    'providers': ['umbrella', 'majestic', 'crux', 'radar'],
    'startDate': '2024-01-01',
    'endDate': '2024-01-30',
    'combinationMethod': 'dowdall',
    'listPrefix': 'full',
    'filterPLD': 'on',
})
# Returns a tuple: (is_available: bool, list_id: str)
```

**Checking list metadata:**
```python
m = t.list_metadata(list_id="6P7X")
# Useful to track generation progress or see configuration of a list
```

**Caching behavior:** Caching is required. Downloaded lists are stored locally in the specified `cache_dir` (default `.tranco`). Subsequent requests for the same list are served from the local cache.

### API

**Base URL:** `https://tranco-list.eu/api/`

**Status:** Alpha

**Authentication:** Basic Authentication. Use your email address as username and your API token (from the account page at https://tranco-list.eu/account) as password. Test with the `/auth/test` endpoint.

**Rate limits:**
- Rank queries: 1 query/second
- List generation: 1 list generated concurrently

**Endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `/ranks/domain/{domain}` | GET | Query ranks of a domain in daily lists of the past 30+ days |
| `/lists/id/{list_id}` | GET | Get metadata for a specific list by ID |
| `/lists/date/{date}` | GET | Get metadata for daily list by date (`YYYYmmdd` format, or `latest`). Optional `?subdomains=true` |
| `/lists/create` | PUT | Generate a custom list (requires authentication) |

**Example requests:**

```bash
# Get ranks for a domain over the past 30+ days
curl https://tranco-list.eu/api/ranks/domain/google.com

# Response:
# {"ranks": [{"date": "2024-01-15", "rank": 1}, ...]}

# Get metadata for the latest daily list
curl https://tranco-list.eu/api/lists/date/latest

# Get metadata for a specific date
curl https://tranco-list.eu/api/lists/date/20240115

# Get metadata for a list by ID
curl https://tranco-list.eu/api/lists/id/6P7X

# Create a custom list (authenticated)
curl -X PUT -u "user@example.com:API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"providers":["umbrella","majestic","crux","radar"],"startDate":"2024-01-01","endDate":"2024-01-30","combinationMethod":"dowdall","listPrefix":"full","filterPLD":"on"}' \
  https://tranco-list.eu/api/lists/create
```

**Response format for `/ranks/domain/{domain}`:**
```json
{
  "ranks": [
    {"date": "2024-01-15", "rank": 1},
    {"date": "2024-01-14", "rank": 1}
  ]
}
```

**Response format for `/lists/id/{list_id}` and `/lists/date/{date}`:**
```json
{
  "list_id": "6P7X",
  "available": true,
  "download": "https://tranco-list.eu/download/6P7X/1000000",
  "created_on": "2024-01-15T00:00:00.000000",
  "configuration": { ... },
  "failed": false,
  "jobs_ahead": 0
}
```

**Error codes:**
- `400`: Invalid configuration (for `/lists/create`)
- `401`: Not authenticated/authorized
- `403`: Service temporarily unavailable
- `404`: No list found for given ID
- `429`: Rate limit exceeded
- `503`: Service temporarily unavailable

### BigQuery

Tranco data is available in Google BigQuery under the `tranco` project.

**Tables:**
- `tranco.daily.daily` -- Contains the full daily Tranco list (rank + domain for all 1M entries, updated daily)
- `tranco.list_ids.list_ids` -- Contains the corresponding list IDs for each daily list

**Access:** Via the Google BigQuery console at `https://console.cloud.google.com/bigquery?p=tranco`

**Example queries:**
```sql
-- Get the rank of a specific domain on a specific date
SELECT rank, domain
FROM `tranco.daily.daily`
WHERE domain = 'google.com'
  AND date = '2024-01-15';

-- Get the top 100 domains from the latest available date
SELECT rank, domain
FROM `tranco.daily.daily`
WHERE date = (SELECT MAX(date) FROM `tranco.daily.daily`)
ORDER BY rank
LIMIT 100;

-- Track a domain's rank over time
SELECT date, rank
FROM `tranco.daily.daily`
WHERE domain = 'example.com'
ORDER BY date DESC
LIMIT 30;
```

Note: The exact schema of these BigQuery tables was determined from the Tranco homepage description. Standard BigQuery access and billing apply.

## Data Format

- **Structure:** CSV with two columns: `rank` (integer, 1-based) and `domain` (string).
- **Example:** `1,google.com`
- **With subdomains option:** Includes subdomain-level entries (e.g., `mail.google.com`) rather than aggregating to pay-level domains only.
- **Without subdomains (default):** Only pay-level domains (e.g., `google.com`).
- **List size:** Top 1 million domains (custom lists can request `full` which may include more).
- **Update frequency:** Daily, available by 0:00 UTC.
- **Combination method:** Dowdall rule averaging over past 30 days by default.
- **Reproducibility:** Each generated list has a permanent ID and a permanent URL, allowing exact reproduction of research results.

## Limitations

- **Not an outage detector:** Tranco is a popularity ranking only. It does not detect outages, downtime, or service disruptions directly.
- **30-day averaging smooths out short-term changes:** The default list averages rankings over 30 days, which means sudden changes in traffic (due to outages, viral events, etc.) are dampened and may not appear immediately.
- **Only top 1M domains:** The default list contains only the top 1 million domains. Domains outside this range are not ranked, so less popular domains cannot be looked up.
- **Source list biases carry through:** Each source ranking has its own biases (e.g., Umbrella includes non-browser DNS traffic and invalid domains; Majestic only considers backlinked sites; CrUX only covers Chrome users who opt in). Combining them mitigates but does not eliminate biases.
- **Bucketed source data:** CrUX and Cloudflare Radar provide bucketed (coarse) ranks rather than exact positions. Tranco normalizes these using geometric means, but precision is inherently limited for these sources.
- **Cloudflare Radar CC BY-NC 4.0 license:** The Cloudflare Radar component is licensed as non-commercial, which may restrict certain commercial uses of data derived from the default Tranco list that includes Radar data.
- **API is in Alpha:** The API is labeled as Alpha and may change. Rate limits are strict (1 query/second for rank lookups).

## Relevance to Our Use Case

- **Validate target companies are significant web properties:** Look up a company's domain in Tranco to confirm it is a top-ranked site. A domain in the top 1M (or top 10K, 100K, etc.) confirms it is a significant web property worth monitoring.
- **Filter and prioritize targets by traffic rank:** Use Tranco rank to prioritize which companies/domains to monitor most closely. Higher-ranked domains represent more impactful potential outages.
- **Detect if a domain drops significantly in rank (indirect signal):** By querying the `/ranks/domain/{domain}` API endpoint (which returns the past 30+ days of rank history), or by comparing daily BigQuery snapshots, you could detect if a domain drops substantially in rank over time. However, due to the 30-day averaging, this would only capture sustained changes, not acute outages.
- **Enrich domain metadata:** The Tranco rank can be used as an enrichment field on monitored domains to provide context about the relative importance/popularity of a target.
- **Reproducible research references:** Every Tranco list has a permanent ID, making it possible to reference the exact list used for any analysis, supporting auditability.
