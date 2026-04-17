# Signal Detection — Chat Log

## Data Sources

### Outage & Domain Ranking Sources

- **Cloudflare Radar** — https://radar.cloudflare.com/outage-center?dateRange=52w
- **Tranco List** — https://tranco-list.eu/ (includes CF Radar data)
  - Attribution: Uses lists from Cisco Umbrella (free), Majestic (CC BY 3.0), Farsight (default list only), CrUX (CC BY-SA 4.0), and Cloudflare Radar (CC BY-NC 4.0). Tranco is not affiliated with any of these providers.
- **DomainTools** — https://www.domaintools.com/resources/blog/mirror-mirror-on-the-wall-whos-the-fairest-website-of-them-all
- **CrUX (Chrome User Experience Report)** — Overview at Chrome for Developers

### Provider Status Pages

- https://www.akamaistatus.com/
- https://www.f5cloudstatus.com/
- https://www.cloudflarestatus.com/
- https://status.imperva.com/

### App Status Monitoring

- https://downdetector.com/

### Status Page Keywords

Search for: *network degradation*, *data center issues*, *link issue*, etc.

Keyword-to-impact mapping:
- Network → CDN / L3/4/7 DDoS
- Link issues → DDoS L3/4

---

## Target Companies (Sample)

Source: `companies_60.csv`

| Industry | Company              | Domain                  |
|----------|----------------------|-------------------------|
| Gaming   | Activision Blizzard  | activisionblizzard.com  |
| Gaming   | Electronic Arts      | ea.com                  |
| Gaming   | Ubisoft              | ubisoft.com             |
| Gaming   | Take-Two Interactive | take2games.com          |
| Gaming   | Epic Games           | epicgames.com           |
| Gaming   | Riot Games           | riotgames.com           |
| Gaming   | Nintendo             | nintendo.com            |
| Gaming   | Square Enix          | square-enix.com         |
| Gaming   | CD Projekt Red       | cdprojektred.com        |

---

## Scope & Approach

### Agreed Workflow

1. **Detect downtime** — Use the data sources above to identify companies whose services were unavailable (start with 1-month lookback; expand to 3 months if needed).
2. **Identify current provider** — Determine what the prospect is currently using (Cloudflare, Akamai, F5, etc.).
3. **Tailor outreach** — Position based on their situation (different incumbent = different pitch).

### Key Decision

The detection logic should be **provider-agnostic**. The signal is: *"this company's service went down"* — that's the pain point, regardless of which provider they're behind.

### Role of Cloudflare

Cloudflare is relevant in three ways, but is not the sole focus:

1. **Signal source** — Radar provides free, structured outage data. Practical starting point for MVP.
2. **Competitive intel** — Knowing a prospect is on CF (or Akamai, F5, etc.) informs positioning.
3. **Market context** — A large share of web-facing services sit behind CF, so it naturally appears in outage detection.

### Next Steps

- to take the company list and validate feasibility: can we find outage data for target companies, in what format, how reliable, and how we'd use it.

