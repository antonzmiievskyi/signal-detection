# Signal Detection — Data Source Cost & Access Report

*Generated: 2026-04-17*

## Executive Summary

Out of 5 data sources evaluated, **4 are completely free** to use. The only paid service is Downdetector, which also has the most problematic access. All free services were successfully tested with live data.

---

## Free Services

### 1. Provider Status Pages (Akamai, Cloudflare, F5, Imperva)

- **Cost:** $0
- **Auth required:** None
- **Status:** Fully operational — tested live, all 4 providers responding
- **Access:** Open REST API (Atlassian Statuspage), RSS/Atom feeds, webhook subscriptions
- **Rate limits:** Not documented; recommended polling every 30-60 seconds
- **Data:** Real-time provider incidents, component status, scheduled maintenance
- **Limitation:** Shows provider-level outages only, not which specific customers are affected

### 2. Tranco List (Domain Rankings)

- **Cost:** $0
- **Auth required:** No (API key only needed for custom list generation)
- **Status:** Fully operational — all 9 target companies found and ranked
- **Access:** Python package (`pip install tranco`), CSV download, REST API, Google BigQuery
- **Rate limits:** 1 query/second on API
- **Data:** Top 1M domain rankings, 30-day rank history per domain
- **Limitation:** Ranking data only, not an outage detector. 30-day averaging smooths out short-term changes

### 3. Cloudflare Radar (Outage Center)

- **Cost:** $0
- **Auth required:** Yes — free Cloudflare API token
  - Sign up at cloudflare.com (free plan is sufficient)
  - Create Custom Token: Account > Radar > Read permission
- **Status:** Ready to use once token is configured
- **Access:** REST API at `api.cloudflare.com/client/v4/radar/annotations/outages`
- **Rate limits:** Not documented (standard Cloudflare API limits likely apply: ~1200 requests per 5 minutes)
- **Data:** Internet outages by country and ASN, cause classification, scope, timestamps
- **Limitation:** Tracks network-level disruptions, not application-level or company-specific outages. License is CC BY-NC 4.0 — **cannot be used commercially** without separate agreement

### 4. CrUX — Chrome User Experience Report (Google)

- **Cost:** $0
- **Auth required:** Yes — free Google Cloud API key
  - Create at console.cloud.google.com/apis/credentials
  - Enable "Chrome UX Report API"
- **Status:** Ready to use once key is configured
- **Access:** REST API (150 queries/min), Google BigQuery (1 TB/month free)
- **Rate limits:** 150 queries per minute per Google Cloud project
- **Data:** Real-user performance metrics (LCP, INP, CLS, TTFB) per domain
- **Limitation:** **Largely unsuitable for outage detection.** Data is a 28-day rolling average with a 2-day lag. A 4-hour outage would shift the average by less than 1%. Measures performance of successful page loads, not availability. Lowest priority source for this project

---

## Paid Services

### 5. Downdetector (Ookla / Ziff Davis)

- **Cost:** Not publicly listed — enterprise pricing, estimated **thousands of dollars per year**
- **No free tier** or developer plan available
- **Official product:** Downdetector Explorer — contact sales at downdetector.com/for-business/
- **Official API provides:** Real-time alerts, historical outage data, comparative analytics, integration capabilities

**Unofficial (free) access options — all unreliable:**

| Method | How it works | Problem |
|---|---|---|
| downdetector-api (npm) | Puppeteer + Cheerio scraping | Cloudflare blocks .com domain |
| downdetector-scraper (npm) | Puppeteer with anti-detection | Small project (6 stars), fragile |
| Direct HTTP requests | Basic requests to status pages | Blocked — tested 8/9 companies got HTTP 403 |
| Playwright/Selenium | Headless browser scraping | May work temporarily, violates ToS |

**Live test results:** 8 out of 9 companies were blocked by Cloudflare protection. 1 company (Epic Games) got through and showed an active outage. This confirms unofficial access is not viable for production use.

---

## Cost Summary Table

| Service | Cost | Auth | Live Tested | Useful for Outage Detection |
|---|---|---|---|---|
| Provider Status Pages | Free | None | Yes — all working | Yes — provider-level incidents |
| Tranco List | Free | None | Yes — all 9 ranked | No — ranking only, enrichment data |
| Cloudflare Radar | Free | Free token | Needs token | Partial — network-level only |
| CrUX (Google) | Free | Free key | Needs key | No — 28-day average, too slow |
| Downdetector | $$$$$ | Paid API | Mostly blocked | Yes — best per-company data, but inaccessible |

---

## Recommendations

1. **Start immediately** with Provider Status Pages (free, working now, real-time data)
2. **Set up Cloudflare Radar** token for network-level correlation data (free, 5 minutes to configure)
3. **Use Tranco** for domain validation and enrichment (free, working now)
4. **Skip CrUX** for outage detection — it's not designed for this purpose
5. **Evaluate Downdetector Explorer** only if budget allows enterprise pricing — it has the best per-company outage data but is the only source that costs money
