# Signal Detection

Automated pipeline that monitors gaming industry companies for service outages and performance issues across multiple data sources, cross-references signals, and generates actionable sales intelligence reports.

## How It Works

```
companies.json ──► 5 checker scripts ──► results/*.txt + SQLite DB
                                              │
                                              ▼
                                   analyze_signals.py (OpenAI)
                                              │
                                              ▼
                                    signal_report.txt
```

The pipeline runs 5 independent data source checkers against a list of target companies, stores every signal in a SQLite database, detects outage state transitions (new / ongoing / resolved), and produces a cross-vendor AI analysis report.

### Pipeline Runner

```bash
python scripts/run_all.py
```

This runs all steps sequentially:

1. **Provider Status Pages** — polls Akamai, Cloudflare, F5, Imperva for incidents
2. **Tranco Rankings** — checks domain rank changes over time
3. **Cloudflare Radar** — checks for network-level outages by country
4. **CrUX** — checks Chrome real-user performance metrics (28-day average)
5. **Downdetector** — fetches Downdetector pages via Apify, analyzes with OpenAI
6. **Signal Analysis** — cross-references all results, sends to OpenAI for final report
7. **SQLite** — saves all signals, detects outage transitions, tracks history

## Data Sources

| Source | Script | Auth | What It Detects | Cost |
|---|---|---|---|---|
| Provider Status Pages | `check_provider_status.py` | None | CDN/security provider incidents (Statuspage API) | Free |
| Tranco List | `check_tranco.py` | None | Domain ranking changes (traffic trends) | Free |
| Cloudflare Radar | `check_cloudflare_radar.py` | API token | Country/ASN-level internet outages | Free |
| CrUX (Google) | `check_crux.py` | API key | Site performance metrics (LCP, INP, CLS, TTFB) | Free |
| Downdetector | `check_downdetector_apify.py` | Apify + OpenAI | User-reported outages per company | ~$0.05/run |

Each checker is independent — reads `companies.json`, calls one external API, and prints results to stdout. You can run any checker individually.

## Database (SQLite)

The pipeline stores all signals in `signal_detection.db` with three tables:

```
runs     — pipeline executions (id, timestamp, status)
signals  — per-company per-vendor results (outage_detected, severity, detail)
outages  — tracked outage events with start/end times
```

### Outage State Tracking

On each run, the pipeline compares current signals with active outages:

- **NEW**: Company has outage signals but no active outage → creates one with `started_at`
- **ONGOING**: Company still has outage signals → updates vendors/severity
- **RESOLVED**: Company has no outage signals but had active outage → sets `ended_at`

This means: if you run the pipeline hourly via cron, you get automatic outage duration tracking and only get alerted on **state changes**, not repeated "still down" noise.

### Querying the Database

```python
from scripts.db import get_active_outages, get_outage_history

# Current active outages
active = get_active_outages()

# Last 30 days of outage history for EA
history = get_outage_history(company="Electronic Arts", days=30)

# All outages in the last week
recent = get_outage_history(days=7)
```

Or use SQLite directly:

```bash
sqlite3 signal_detection.db "SELECT company, started_at, ended_at, severity FROM outages ORDER BY started_at DESC LIMIT 10"
```

## Signal Analysis

`analyze_signals.py` reads all result files from `results/`, builds a per-company cross-reference table, and sends everything to OpenAI for structured analysis. The output includes:

1. **Signal Strength Rating** — STRONG / MODERATE / WEAK / NONE per company
2. **Vendor Agreement Matrix** — where sources agree or disagree
3. **Actionable Signals** — ranked by priority with outreach recommendations
4. **Data Quality Assessment** — what worked, what didn't, per vendor

## Downdetector + AI

Downdetector is a Next.js app behind Cloudflare protection. The pipeline handles this in three steps:

1. **Apify ScrapeUnblocker** (`scrapeunblocker/scrapeunblocker`) bypasses Cloudflare and fetches the raw HTML
2. **Text extraction** strips scripts, styles, and i18n translation JSON (which contains false-positive status keywords)
3. **OpenAI analysis** reads the visible text + user comments and returns structured JSON: outage status, severity, issue types, comment sentiment, geographic patterns

This replaces brittle regex parsing and correctly handles Downdetector's React Server Components (RSC) payload where status data is embedded in JS chunks rather than visible HTML.

Falls back to title-based detection (`"EA down? Current outages"`) if `OPENAI_API_KEY` is not set.

## Setup

### Prerequisites

- Python 3.10+
- Docker (for dev container) or local Python environment

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
CLOUDFLARE_RADAR_TOKEN=   # Free — https://dash.cloudflare.com/profile/api-tokens
CRUX_API_KEY=             # Free — https://console.cloud.google.com/apis/credentials
APIFY_TOKEN=              # Free $5/mo — https://console.apify.com/account/integrations
OPENAI_API_KEY=           # For AI analysis (Downdetector + signal report)
```

All scripts auto-load from `.env` via `python-dotenv`. Only `check_provider_status.py` and `check_tranco.py` work without any API keys.

### Initialize Database

```bash
python scripts/db.py
```

## Running

```bash
# Full pipeline (all checkers + analysis + DB)
python scripts/run_all.py

# Individual checkers
python scripts/check_provider_status.py
python scripts/check_tranco.py
python scripts/check_cloudflare_radar.py
python scripts/check_crux.py
python scripts/check_downdetector_apify.py

# Signal analysis only (reads existing results/)
python scripts/analyze_signals.py

# Database stats
python scripts/db.py
```

## Slack Notifications

The pipeline posts a summary to Slack after each run if configured. Add to `.env`:

```env
SLACK_BOT_TOKEN=xoxb-...    # Bot token with chat:write scope
SLACK_CHANNEL=C0123456789   # Channel ID
```

The notification includes: run status, active outages with severity, and new state transitions. Uses Slack Block Kit formatting. Skipped silently if not configured — never fails the pipeline.

## Cron Setup

To run the pipeline hourly:

```bash
crontab -e
# Add:
0 * * * * cd /path/to/signal-detection && python scripts/run_all.py >> logs/pipeline.log 2>&1
```

The SQLite database handles deduplication — repeated runs won't create duplicate outage records, only track transitions.

## Tests

```bash
# Run all tests (114 tests)
pytest

# Run a specific test file
pytest tests/test_db.py

# Run a specific test
pytest tests/test_db.py::TestOutageTransitions::test_new_outage

# Run with verbose output
pytest -v
```

Tests use mocked HTTP responses and temporary SQLite databases — no real API calls or network access needed.

## Target Companies

Defined in `companies.json`:

```json
{
  "company": "Electronic Arts",
  "domain": "ea.com",
  "industry": "Gaming",
  "country": "US",
  "downdetector_slug": "ea"
}
```

To add more companies, add entries to this file. The `downdetector_slug` is the URL path on downdetector.com (e.g., `ea` → `downdetector.com/status/ea/`).

## Project Structure

```
signal-detection/
├── companies.json              # Target company list
├── requirements.txt            # Python dependencies
├── signal_detection.db         # SQLite database (gitignored)
├── .env                        # API keys (gitignored)
│
├── scripts/
│   ├── run_all.py              # Full pipeline runner
│   ├── db.py                   # SQLite database module
│   ├── analyze_signals.py      # Cross-vendor AI analysis
│   ├── notify_slack.py         # Slack notifications (optional)
│   ├── check_provider_status.py
│   ├── check_tranco.py
│   ├── check_cloudflare_radar.py
│   ├── check_crux.py
│   └── check_downdetector_apify.py
│
├── tests/                      # 114 tests with mocked APIs
│   ├── test_db.py
│   ├── test_provider_status.py
│   ├── test_tranco.py
│   ├── test_cloudflare_radar.py
│   ├── test_crux.py
│   └── test_downdetector_apify.py
│
├── research/                   # Detailed vendor research docs
│   ├── cost_report.md
│   ├── cloudflare_radar.md
│   ├── provider_status_pages.md
│   ├── tranco_list.md
│   ├── downdetector.md
│   └── crux.md
│
└── results/                    # Output from latest run (gitignored)
    ├── provider_status.txt
    ├── tranco.txt
    ├── cloudflare_radar.txt
    ├── crux.txt
    ├── downdetector_apify.txt
    └── signal_report.txt
```

## Cost Per Run

| Service | Cost | Notes |
|---|---|---|
| Provider Status Pages | $0 | No auth needed |
| Tranco List | $0 | No auth needed |
| Cloudflare Radar | $0 | Free API token |
| CrUX | $0 | Free Google Cloud key |
| Downdetector (Apify) | ~$0.005/page | 9 companies = ~$0.045/run |
| OpenAI (Downdetector AI) | ~$0.01/run | gpt-4.1-mini, 9 calls |
| OpenAI (Signal Analysis) | ~$0.02/run | gpt-4.1-mini, 1 call |
| **Total per run** | **~$0.08** | **~$56/month at hourly runs** |
