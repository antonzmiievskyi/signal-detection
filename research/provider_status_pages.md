# Provider Status Pages — Detailed Research

*Research conducted: 2026-04-17 by querying live API endpoints*

## Overview

All four CDN/security providers — Cloudflare, Akamai, F5, and Imperva — publish operational status pages built on **Atlassian Statuspage** (https://www.atlassian.com/software/statuspage). This platform provides a standardized REST API, Atom/RSS feeds, and subscription mechanisms for operational transparency.

These pages track:
- Real-time operational status of each provider's services and infrastructure
- Active and historical incidents (outages, degraded performance)
- Scheduled maintenance windows
- Per-component and per-region health

Each provider maintains their own Statuspage instance. The pages are publicly accessible with no authentication required for API read access.

## Providers Covered

### Cloudflare

- **Status page URL:** https://www.cloudflarestatus.com
- **Statuspage page ID:** `yh6f0r4529hb`
- **RSS feed:** https://www.cloudflarestatus.com/history.rss
- **Atom feed:** https://www.cloudflarestatus.com/history.atom
- **API base:** https://www.cloudflarestatus.com/api/v2/

**Service component groups:**
1. **Cloudflare Sites and Services** — 117 sub-components including:
   - Abuse Reports, Access, AI Gateway, AI Search, Always Online, Analytics, API, API Shield, Argo Smart Routing, Billing, Bot Management, Browser Isolation, Cache / CDN, CASB, Cloudflare Dashboard, Cloudflare Images, Cloudflare Stream, Cloudflare Tunnel (Argo Tunnel), Cloudflare Workers, D1, Digital Experience Monitoring (DEX), DNS, Email Routing, Firewall, Gateway, Health Checks, Hyperdrive, KV, Load Balancing, Logpush, Magic Firewall, Magic Transit, Magic WAN, Notifications, Page Shield, Pages, Pub/Sub, Queues, R2, Radar, Registrar, Rules, SSL/TLS, Spectrum, Speed, Vectorize, Waiting Room, WAF, Web Analytics, Workers AI, Zero Trust, and many more
2. **Regional PoP groups** — Africa (35), Asia (97), Europe (59), Latin America & Caribbean (65), Middle East (21), North America (59), Oceania (14)

**Recent incidents (as of 2026-04-17):**
- 2026-04-16 | minor | CF1 Client DEX - Device analytics overtime gaps (resolved)
- 2026-04-16 | minor | API Analytics Delays (resolved)
- 2026-04-16 | none  | Workers script upload issues (resolved)
- 2026-04-16 | minor | Cloudflare API failures/errors (resolved)

**Incident frequency:** Very active — multiple incidents per day, mostly minor. Cloudflare reports granularly at the individual service level.

---

### Akamai

- **Status page URL:** https://www.akamaistatus.com
- **Statuspage page ID:** `tmd0zfspxwvp`
- **Atom feed:** https://www.akamaistatus.com/history.atom
- **RSS feed:** https://www.akamaistatus.com/history.rss
- **API base:** https://www.akamaistatus.com/api/v2/

**Service component groups:**
1. **Content Delivery** — Cloudlets, Edge Delivery, Global Traffic Management, Image Management, NetStorage
2. **App & Network Security** — Account Protector, Akamai Identity Cloud, Bot Management, Client-Side Protection & Compliance, DNS Posture Management, Edge DNS, Prolexic, Web Application Firewall
3. **Enterprise Security** — Akamai MFA, Enterprise Application Access (+ API Service, Configuration, Reporting), ETP/SIA (Client, Configuration, Connectors, Name Servers, Reporting, Web Proxy)
4. **Data Services** — Log Delivery, mPulse, Reporting, SIEM Data feeds, TrafficPeak, Web Security Analytics
5. **Configuration** — Configuration Deployment, Content Purge, TLS Provisioning (Certificates, CPS)
6. **Customer Service, Documentation and Community** — Akamai Control Center, Customer Community, Partner Community, Techdocs, Case Ticketing, Chat, Telephony

**Recent incidents (as of 2026-04-17):**
- 2026-04-16 | minor | NetStorage Issues — issues with new storage group creations (resolved)
- 2026-04-06 | minor | Edge Delivery Issues in Chicago, Illinois (resolved 2026-04-15)
- 2026-04-07 | minor | Data Services - Reporting Issues (resolved)
- 2026-04-07 | minor | Configuration Deployment Issues in Property Manager (resolved)
- 2026-04-07 | minor | Certificate Provisioning System Issues (resolved)

**Incident style:** Akamai provides detailed update messages with links to their community portal for additional details. Updates follow a structured cadence with next-update ETAs.

---

### F5 (Distributed Cloud)

- **Status page URL:** https://www.f5cloudstatus.com
- **Statuspage page ID:** `h7kz0y1dbjsv`
- **Atom feed:** https://www.f5cloudstatus.com/history.atom
- **RSS feed:** https://www.f5cloudstatus.com/history.rss
- **API base:** https://www.f5cloudstatus.com/api/v2/

**Service component groups:**
1. **Services** — Portal & Customer Login, Customer Dashboard, App Stack, Secure Mesh, Bot Defense, DNS, DNS Load Balancer, Multi-Cloud Networking, Synthetic Monitoring, Web App Scanning, and more (15 sub-components)
2. **Customer Support, Docs and Website** — Website, Customer Support, Software Distribution, Product Documentation
3. **Regional PoPs** — North America (15), South America (1), Europe (12), Asia (7), Oceania (2), Middle East (2)
4. **Silverline - Legacy** — Proxy Services and Routed Services across US West/East/UK (29 sub-components)
5. **Bot and Risk Mgt - Legacy** — F5 Bot Defense across many locations (56 sub-components)

**Recent incidents (as of 2026-04-17):**
- 2026-04-16 | none     | Informational: Introduction of New Regional Edge Cluster Chicago (monitoring)
- 2026-04-11 | minor    | Service Degradation - Delay in GLR logs (resolved)
- 2026-04-06 | minor    | DNS resolution failures for CDN domain (resolved)
- 2025-10-21 | critical | Informational: New IP ranges for Distributed Cloud Regional Edge sites (resolved)

**Incident style:** F5 uses informational incidents (impact=none) for infrastructure announcements (new PoPs, IP range changes). Actual outages are less frequent. Uses INC-number format for ticket tracking.

---

### Imperva

- **Status page URL:** https://status.imperva.com
- **Statuspage page ID:** `4dbnz6n8nkt2`
- **Atom feed:** https://status.imperva.com/history.atom
- **RSS feed:** https://status.imperva.com/history.rss
- **API base:** https://status.imperva.com/api/v2/

**Service component groups:**
1. **Protection Services** — Cloud WAF Protection, Web Application Performance, IGC WAF Protection, Cloud L7 DDoS Protection, Login Protect, File Upload Scan and Protect, Protected DNS, Managed DNS, L3/4 IP Protection, L3/4 Network DDoS Protection, Advanced BOT Protection, API Security, Account Takeover Protection, Client-Side Protection, Waiting Room
2. **Management and Analytics Services** — Cloud Security Management Platform, Configuration Changes, Account/User Mgmt, CDN and WAF Management, API Security Management, Network DDoS Management, DNS Protection Management, ABP Management, ATO Management, CSP Management, Waiting Room Management, Runtime Protection Deployment, SIEM Logs, Events Page, Attack Analytics, IP Reputation
3. **Additional services** — Support Ticketing System, Support Phone Systems, Documentation Portal
4. **Third Party Services** — Third Party Services
5. **Regional PoPs** — North American (17), EMEA (20), LATAM (7), APAC (17)
6. **Imperva for Google Cloud (IGC) Regions** — us-east1, us-east4, us-east5, us-central1, europe-west1
7. **Coming Soon** — Tokyo (NRT), Amsterdam (RTM), Frankfurt (HHN), Singapore (XSP)

**Recent incidents (as of 2026-04-17):**
- 2026-04-13 | major | [INC-1011] Imperva API Issue — CDN and WAF Management partial outage (resolved)
- 2026-04-09 | major | [INC-1009] Management Portal Cloud WAF Dashboard Issue (resolved)
- 2026-04-09 | major | [INC-1008] Advanced Bot Protection Issue (resolved)
- 2026-04-05 | minor | [INC-1004] Potential CWAF issue on multiple Data Center (resolved)
- 2026-03-27 | major | [INC-1001] GRE Performance Dashboard Issue across Multiple Data Center (resolved)

**Incident style:** Imperva uses INC-number tracking. Incidents tend to be rated "major" more frequently than other providers. Updates include boilerplate about proactive monitoring and transparent communication. Also note that Imperva has a "Coming Soon" group for planned new PoPs with scheduled dates (under_maintenance status).

---

## Statuspage API (Common to All)

All four providers use the Atlassian Statuspage public API v2. The API documentation is available at each provider's `/api` path (e.g., https://www.cloudflarestatus.com/api).

### Base URL Pattern

```
https://<statuspage-domain>/api/v2/<endpoint>.json
```

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/v2/summary.json` | Full summary: page info, current status, all components, active incidents, and scheduled maintenances |
| `/api/v2/status.json` | Overall page status indicator: `none`, `minor`, `major`, or `critical` with human-readable description |
| `/api/v2/components.json` | All components with current status, grouped by service category or region |
| `/api/v2/incidents.json` | All incidents (50 most recent), both resolved and unresolved |
| `/api/v2/incidents/unresolved.json` | Only incidents in `investigating`, `identified`, or `monitoring` state |
| `/api/v2/scheduled-maintenances.json` | All scheduled maintenance events |
| `/api/v2/scheduled-maintenances/upcoming.json` | Only upcoming scheduled maintenances |
| `/api/v2/scheduled-maintenances/active.json` | Only active (in-progress) scheduled maintenances |

### Authentication

**No authentication is required.** All endpoints are publicly accessible read-only APIs.

### Rate Limiting

The Statuspage API does not document explicit rate limits for public consumers, but reasonable polling intervals (every 30-60 seconds for unresolved incidents, every 5-10 minutes for full summaries) are advisable.

---

## Data Format

All responses are JSON. Key data structures observed from live API calls:

### Page Object
```json
{
  "id": "yh6f0r4529hb",
  "name": "Cloudflare",
  "url": "https://www.cloudflarestatus.com",
  "time_zone": "Etc/UTC",
  "updated_at": "2026-04-17T10:20:42.585Z"
}
```

### Status Object (from /api/v2/status.json)
```json
{
  "status": {
    "indicator": "minor",
    "description": "Minor Service Outage"
  }
}
```
Indicator values: `none`, `minor`, `major`, `critical`

### Component Object
```json
{
  "id": "57ctn3f2qsyj",
  "name": "Amsterdam, Netherlands - (AMS)",
  "status": "operational",
  "created_at": "2014-10-27T20:35:05.259Z",
  "updated_at": "2026-04-17T03:58:48.540Z",
  "position": 1,
  "description": null,
  "showcase": false,
  "start_date": null,
  "group_id": "zqxhg7y54vy8",
  "page_id": "yh6f0r4529hb",
  "group": false,
  "only_show_if_degraded": false
}
```
Component status values: `operational`, `degraded_performance`, `partial_outage`, `major_outage`, `under_maintenance`

Group components have `"group": true` and child components reference them via `group_id`.

### Incident Object
```json
{
  "id": "gyyz704fpjmj",
  "name": "CF1 Client DEX - Device analytics overtime gaps",
  "status": "resolved",
  "created_at": "2026-04-16T22:10:27.979Z",
  "updated_at": "2026-04-17T09:54:57.301Z",
  "monitoring_at": null,
  "resolved_at": "2026-04-17T09:54:57.284Z",
  "impact": "minor",
  "shortlink": "https://stspg.io/q6n170rsxwck",
  "started_at": "2026-04-16T22:10:27.970Z",
  "page_id": "yh6f0r4529hb",
  "incident_updates": [...],
  "components": [...]
}
```

Incident status values: `investigating`, `identified`, `monitoring`, `resolved`, `postmortem`

Incident impact values: `none`, `minor`, `major`, `critical`

### Incident Update Object
```json
{
  "id": "9182dxgh8dxv",
  "status": "resolved",
  "body": "This incident has been resolved.",
  "incident_id": "gyyz704fpjmj",
  "created_at": "2026-04-17T09:54:57.284Z",
  "updated_at": "2026-04-17T09:54:57.284Z",
  "display_at": "2026-04-17T09:54:57.284Z",
  "affected_components": [
    {
      "code": "nmp96vgn1hpl",
      "name": "Cloudflare Sites and Services - Digital Experience Monitoring (DEX)",
      "old_status": "degraded_performance",
      "new_status": "operational"
    }
  ],
  "deliver_notifications": true
}
```

### Scheduled Maintenance Object
Same structure as incidents, with additional fields:
- `scheduled_for` — planned start time
- `scheduled_until` — planned end time

---

## Python Integration

### Polling for Incidents

```python
import requests
from datetime import datetime

PROVIDERS = {
    "cloudflare": "https://www.cloudflarestatus.com",
    "akamai": "https://www.akamaistatus.com",
    "f5": "https://www.f5cloudstatus.com",
    "imperva": "https://status.imperva.com",
}

def get_unresolved_incidents(provider_name: str) -> list[dict]:
    """Fetch all unresolved incidents for a provider."""
    base_url = PROVIDERS[provider_name]
    resp = requests.get(f"{base_url}/api/v2/incidents/unresolved.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["incidents"]

def get_overall_status(provider_name: str) -> dict:
    """Get the overall status indicator for a provider."""
    base_url = PROVIDERS[provider_name]
    resp = requests.get(f"{base_url}/api/v2/status.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["status"]

def get_recent_incidents(provider_name: str) -> list[dict]:
    """Fetch 50 most recent incidents (resolved and unresolved)."""
    base_url = PROVIDERS[provider_name]
    resp = requests.get(f"{base_url}/api/v2/incidents.json", timeout=10)
    resp.raise_for_status()
    return resp.json()["incidents"]

def poll_all_providers() -> dict:
    """Poll all providers and return any active issues."""
    results = {}
    for name in PROVIDERS:
        try:
            status = get_overall_status(name)
            unresolved = get_unresolved_incidents(name)
            results[name] = {
                "indicator": status["indicator"],
                "description": status["description"],
                "unresolved_incidents": [
                    {
                        "id": inc["id"],
                        "name": inc["name"],
                        "impact": inc["impact"],
                        "status": inc["status"],
                        "started_at": inc["started_at"],
                        "components": [c["name"] for c in inc.get("components", [])],
                    }
                    for inc in unresolved
                ],
            }
        except requests.RequestException as e:
            results[name] = {"error": str(e)}
    return results
```

### Polling Interval Recommendation

- **For real-time detection:** Poll `/api/v2/incidents/unresolved.json` every 30-60 seconds
- **For periodic checks:** Poll `/api/v2/summary.json` every 5 minutes
- **For historical analysis:** Poll `/api/v2/incidents.json` every 15-30 minutes

---

## RSS/Atom Feeds

Each provider offers both Atom and RSS feeds of incident history:

| Provider   | Atom Feed | RSS Feed |
|------------|-----------|----------|
| Cloudflare | https://www.cloudflarestatus.com/history.atom | https://www.cloudflarestatus.com/history.rss |
| Akamai     | https://www.akamaistatus.com/history.atom | https://www.akamaistatus.com/history.rss |
| F5         | https://www.f5cloudstatus.com/history.atom | https://www.f5cloudstatus.com/history.rss |
| Imperva    | https://status.imperva.com/history.atom | https://status.imperva.com/history.rss |

All feeds return HTTP 200 and contain incident history entries with published/updated timestamps, incident titles, and HTML-formatted content with update details.

### Parsing with Python (feedparser)

```python
import feedparser

def get_feed_incidents(provider_url: str) -> list[dict]:
    """Parse Atom feed for a provider's status page."""
    feed = feedparser.parse(f"{provider_url}/history.atom")
    return [
        {
            "title": entry.title,
            "link": entry.link,
            "published": entry.published,
            "updated": entry.updated,
            "summary": entry.summary,
        }
        for entry in feed.entries
    ]
```

---

## Webhook Support

Atlassian Statuspage supports webhook subscriptions for real-time push notifications. However, webhook subscription is managed through the **Statuspage management interface** (requires the page owner to configure), not through the public API.

For consumers, real-time notification options available through each provider's status page include:
- **Email subscriptions** — subscribe via the status page UI
- **SMS subscriptions** — available on some pages
- **RSS/Atom feeds** — for feed reader consumption
- **Slack integration** — some providers offer direct Slack integration
- **Webhook (for page owners)** — page owners can configure outbound webhooks via their Statuspage admin panel

Cloudflare also offers its own notification system via the Cloudflare Dashboard for subscribers to receive status updates via email, PagerDuty, and webhooks (plan-dependent): https://developers.cloudflare.com/notifications/notification-available/#cloudflare-status

For programmatic consumers without page-owner access, **polling the REST API** or **monitoring the Atom/RSS feeds** are the primary integration methods.

---

## Limitations

1. **Only shows provider-acknowledged incidents.** If a provider has an issue but has not yet posted to their status page, it will not appear in the API. There can be a delay between an issue starting and the provider acknowledging it.

2. **Provider may be slow to acknowledge issues.** Based on observed incident patterns, providers may take 15-60 minutes to post an initial update after an issue begins. Some issues may never be posted if they are brief or limited in scope.

3. **Does not tell you which specific customers were affected.** These are provider-wide status pages. An "Edge Delivery Issue in Chicago" at Akamai does not tell you which Akamai customers route through Chicago.

4. **Impact ratings are subjective.** Each provider rates impact (none/minor/major/critical) based on their own criteria. Imperva tends to rate incidents as "major" more frequently, while Cloudflare and Akamai tend toward "minor" even for significant issues.

5. **Historical data is limited.** The `/api/v2/incidents.json` endpoint returns only the 50 most recent incidents. For longer history, the Atom/RSS feeds may provide more entries, but are still not exhaustive.

6. **Informational posts mixed with real incidents.** F5 in particular uses the incident system for informational announcements (new PoP deployments, IP range changes) with `impact: "none"`, which must be filtered out when looking for actual outages.

7. **No granular geographic impact data.** While Cloudflare shows per-datacenter status, an incident affecting "Analytics" does not specify which regions are impacted unless the incident update text mentions it.

8. **Scheduled maintenance data can be noisy.** Cloudflare posts frequent per-datacenter maintenance windows (multiple per week). These need to be filtered separately from unplanned incidents.

---

## Relevance to Our Use Case

These status pages show **provider-level outages**, not per-company outages. Their value to signal detection is as **correlation data**:

1. **Cross-reference pattern:** "Akamai had an Edge Delivery outage" + "Target company X uses Akamai CDN" = potential signal that company X experienced disruption. This requires a separate mapping of which companies use which CDN/security providers.

2. **Not primary detection:** A company's website could be down for reasons unrelated to their CDN provider (origin server failure, DNS misconfiguration, application bug). Conversely, a CDN outage may not affect a company if the outage is in a region they don't serve.

3. **Useful for incident enrichment:** When we detect that a company's website is down via direct monitoring, we can check these status pages to determine if the root cause is a provider-level issue, which affects the signal's meaning (provider outage vs. company-specific issue).

4. **Bulk impact detection:** A major CDN outage (impact=major or critical) affecting core services (Edge Delivery, WAF, DNS) could simultaneously impact hundreds of companies. This is valuable for generating multiple signals at once from a single provider event.

5. **Recommended integration approach:**
   - Poll `/api/v2/incidents/unresolved.json` for each provider every 60 seconds
   - When an unresolved incident is detected, look up which monitored companies use that provider
   - Generate potential outage signals for those companies
   - Use `/api/v2/status.json` for quick overall health checks
   - Store historical incidents for trend analysis and correlation with past detected outages
