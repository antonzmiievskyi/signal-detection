# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Signal Detection — detects service outages for target companies (starting with gaming industry) to identify sales opportunities. The workflow: detect downtime via multiple data sources → cross-reference signals → identify current provider (Cloudflare, Akamai, F5, etc.) → tailor outreach. Detection logic is provider-agnostic; the signal is "this company's service went down."

## Development Environment

- Python 3.10 in a Docker dev container (python:3.10-slim)
- Package manager: pip (install to `--user`)
- Port 8000 is forwarded for local dev server
- API keys stored in `.env` (loaded via python-dotenv)

## Commands

```bash
# Install dependencies
pip install --user -r requirements.txt

# Run all tests
pytest

# Run a single test file
pytest tests/test_tranco.py

# Run a single test
pytest tests/test_tranco.py::TestAnalyzeRankTrend::test_stable_trend

# Run individual checker scripts
python scripts/check_provider_status.py    # no auth needed
python scripts/check_tranco.py             # no auth needed
python scripts/check_cloudflare_radar.py   # needs CLOUDFLARE_RADAR_TOKEN
python scripts/check_crux.py              # needs CRUX_API_KEY
python scripts/check_downdetector_apify.py # needs APIFY_TOKEN

# Run cross-vendor signal analysis
python scripts/analyze_signals.py          # needs OPENAI_API_KEY, reads from results/
```

## Environment Variables (.env)

```
CLOUDFLARE_RADAR_TOKEN=   # Free — https://dash.cloudflare.com/profile/api-tokens (Account > Radar > Read)
CRUX_API_KEY=             # Free — https://console.cloud.google.com/apis/credentials
APIFY_TOKEN=              # Free tier $5/mo — https://console.apify.com/account/integrations
OPENAI_API_KEY=           # For signal analysis summary
```

All scripts auto-load from `.env` via `python-dotenv`.

## Architecture

### Data Sources (scripts/)

Each checker script is independent — reads `companies.json`, calls one external API, prints results to stdout.

| Script | Source | Auth | What it detects |
|---|---|---|---|
| `check_provider_status.py` | Akamai, Cloudflare, F5, Imperva status pages | None | Provider-level incidents (Statuspage API) |
| `check_tranco.py` | Tranco List API | None | Domain ranking changes (1 req/sec rate limit) |
| `check_cloudflare_radar.py` | Cloudflare Radar CROC API | Token | Network-level outages by country/ASN |
| `check_crux.py` | Google CrUX API | Key | Site performance metrics (28-day avg, not real-time) |
| `check_downdetector_apify.py` | Downdetector via Apify ScrapeUnblocker | Token | User-reported outages per company |

### Signal Analysis (scripts/analyze_signals.py)

Reads all `results/*.txt` files, builds a per-company cross-reference table, sends to OpenAI for signal strength rating and actionable recommendations. Output saved to `results/signal_report.txt`.

### Key Files

- `companies.json` — target company list (name, domain, country, downdetector_slug)
- `research/` — detailed vendor research docs and cost report
- `results/` — output from checker scripts (gitignored, regenerated on each run)
- `.env` — API keys (gitignored)

### Downdetector Parsing

Downdetector is a Next.js app with Cloudflare protection. The Apify `scrapeunblocker/scrapeunblocker` actor bypasses Cloudflare and returns server-rendered HTML. Status detection relies on the `<title>` tag (e.g., "EA down? Current outages and problems") since the actual status text is rendered client-side via React and not available in the initial HTML. Translation JSON strings in the RSC payload contain status keywords ("No problems", "Possible problems") but must be excluded to avoid false positives.
