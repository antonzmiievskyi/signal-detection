# Downdetector -- Detailed Research

## Overview

Downdetector (downdetector.com) is a website that tracks user-reported outages and service disruptions for major online services, telecom providers, banks, gaming platforms, and other consumer-facing companies. It is owned by Ookla (the company behind Speedtest.net), which itself is a subsidiary of Ziff Davis.

How it works: Users visit Downdetector and submit reports when they experience issues with a service. The site aggregates these reports over time and displays a chart showing report volume in 15-minute intervals. When report volume significantly exceeds a baseline, Downdetector flags it as a potential outage. The site also collects user comments describing the nature of their issue and categorizes reports into types (e.g., "App", "Website", "Server Connection").

Downdetector covers thousands of services across multiple countries and localized domains (downdetector.com, downdetector.co.uk, downdetector.it, etc.).

## Official API (Paid)

Downdetector offers a commercial product called **Downdetector Explorer** aimed at enterprise customers. Key details based on publicly available information:

- Pricing is not publicly listed. It requires contacting Ookla/Downdetector sales for a quote. Enterprise pricing is generally understood to be significant (likely thousands of dollars per year), making it inaccessible for small projects or individual developers.
- The official API provides structured access to report data, outage alerts, historical data, and analytics.
- Enterprise features reportedly include: real-time alerts, historical outage data, comparative analytics across services, and integration capabilities.
- No free tier or developer tier is publicly advertised.

**Note:** Specific pricing figures are not publicly documented. The above reflects what can be reasonably inferred from Downdetector's commercial positioning and industry norms.

## Unofficial Access Methods

### downdetector-api (npm)

**Repository:** https://github.com/DavideViolante/downdetector-api
**npm package:** `downdetector-api` (latest v2.1.0, published June 2023)
**Stats:** ~910 downloads/month (as of April 2026), 22 GitHub stars
**License:** MIT

How it works:
- Uses **Puppeteer** (headless Chrome) to load the Downdetector page for a given service.
- Sets a realistic user-agent string to avoid basic bot detection.
- Uses **Cheerio** to parse the rendered HTML and extract chart data from embedded `<script>` tags.
- The chart data is embedded as JavaScript objects with `{ x: '<date>', y: <value> }` pairs.

Data extracted:
- **reports**: Array of `{ date, value }` objects showing report counts in 15-minute intervals (96 data points = 24 hours).
- **baseline**: Array of `{ date, value }` objects showing the normal baseline report level for comparison.

Reliability issues:
- The README explicitly warns: "It might not work sometimes (especially .com domain) due to the website being protected by Cloudflare."
- Open issue #17 suggests adding `puppeteer-extra-plugin-stealth` to better evade bot detection.
- Issue #11 reported "DownDetector Dont get Graph Data" -- indicating the scraping approach breaks when the site's HTML structure changes.
- Depends on the internal HTML/JS structure of Downdetector pages, which can change without notice.
- Requires a full Chromium browser instance, making it heavyweight.

Usage example:
```js
const { downdetector } = require('downdetector-api');
const response = await downdetector('steam');       // uses .com domain
const response = await downdetector('windtre', 'it'); // uses .it domain
```

### downdetector-scraper (Puppeteer)

**Repository:** https://github.com/erucix/downdetector-scraper
**Stats:** 6 GitHub stars, 0 forks
**License:** Not specified in repository

How it works:
- Uses Puppeteer with anti-detection measures (overrides `navigator.webdriver` to `undefined`).
- Launches a headless Chrome browser, navigates to `downdetector.com/status/<site>`.
- Waits for specific DOM selectors to load, then extracts data via `page.evaluate()`.
- Runs as a local HTTP server (port 3333) -- you request `http://localhost:3333/github` and get JSON back.

Data extracted (richer than downdetector-api):
- **logo**: URL of the service's logo image.
- **url**: The service's official URL (from the Downdetector page).
- **problems**: Breakdown of reported issue types with percentages (e.g., `{ app: "45", website: "30", server: "25" }`).
- **comments**: User-submitted comments with username, date, and comment text.
- **chart**: Report counts over time (`data` array) and `baseline` array, parsed from embedded JavaScript.

Dependencies and setup:
- Requires Node.js and Puppeteer (`npm i puppeteer`).
- On Linux, may need to set `EXEC_PATH` environment variable to point to a Chromium executable.
- Uses a persistent user data directory (`./crawler-profile/`) which may help with session persistence.
- Can be used as a library (import `downdetector.js`) or as a standalone HTTP server (`node app.js`).

### Direct Scraping Considerations

**Anti-bot protections:**
- Downdetector uses Cloudflare protection, which includes JavaScript challenges, CAPTCHAs, and browser fingerprinting.
- Simple HTTP requests (e.g., via `requests` or `axios` without a browser) are typically blocked.
- Even headless browsers can be detected; the `navigator.webdriver` property and other fingerprints may trigger blocks.
- The .com domain appears to have stronger protections than regional domains (.it, .co.uk, etc.).

**Legal/ToS considerations:**
- Downdetector's Terms of Service likely prohibit automated scraping.
- Both unofficial packages explicitly note they are "in no way affiliated with downdetector.com."
- Using scraped data commercially could carry legal risk.
- For a research/internal-use project, the legal risk is lower but still exists.

**Reliability:**
- Site structure changes can break scrapers at any time without warning.
- Cloudflare protection levels can be increased, blocking previously-working approaches.
- Rate limiting may apply; aggressive scraping could result in IP blocks.

## Data Available

Based on analysis of what the unofficial tools extract and what the Downdetector site displays:

- **Report counts over time**: 15-minute interval data points for the past 24 hours (96 data points). Each point has a timestamp and report count.
- **Baseline values**: Normal expected report levels for comparison, enabling detection of anomalous spikes.
- **Service names and categories**: Downdetector organizes services by category (Internet, Mobile, Gaming, Banking, Email, Social Media, etc.). The URL slug identifies the service (e.g., `/status/steam/`).
- **Types of reported issues**: Percentage breakdown by issue type (varies by service but typically includes categories like App, Website, Server Connection).
- **User comments**: Text reports from users describing their specific issues, with timestamps and usernames.
- **Geographic breakdown**: The Downdetector website shows an outage map with geographic distribution of reports. However, neither unofficial tool currently extracts this map data.
- **Regional coverage**: Different Downdetector domains cover different countries (e.g., downdetector.com for US, downdetector.co.uk for UK).

## Python Integration Options

### Using unofficial npm packages via subprocess
```python
import subprocess
import json

result = subprocess.run(
    ['node', '-e', '''
    const { downdetector } = require('downdetector-api');
    downdetector('steam').then(d => console.log(JSON.stringify(d)));
    '''],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
```
Requires Node.js and the npm package installed. Heavyweight due to Puppeteer/Chromium dependency.

### Direct HTTP requests (limited feasibility)
Direct requests to `downdetector.com` using Python `requests` will almost certainly be blocked by Cloudflare. This approach is not viable without additional tooling (e.g., `cloudscraper`, which itself has reliability issues).

### Selenium/Playwright scraping
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://downdetector.com/status/steam/')
    # Extract chart data from page scripts
    content = page.content()
    browser.close()
```
Playwright (Python-native) is the most practical option for direct Python integration. It avoids the Node.js subprocess overhead. The `playwright-stealth` package can help evade bot detection.

### Alternative: Monitor the Downdetector RSS/social feeds
Some Downdetector outage data surfaces on social media and other aggregators. Monitoring these secondary sources could be an alternative to direct scraping.

## Limitations

- **User-reported data, not verified outages**: Reports reflect user perception, not confirmed technical outages. False positives occur (e.g., a viral social media post can cause a spike in reports even without a real outage).
- **Bias toward consumer services**: Downdetector primarily covers consumer-facing services. B2B/enterprise infrastructure services (cloud providers' specific sub-services, internal tools) are underrepresented.
- **Anti-scraping protections**: Cloudflare protection makes unofficial access unreliable. Scrapers can break at any time due to site changes or increased protection levels.
- **Paid API cost may be prohibitive**: Enterprise pricing for Downdetector Explorer is not publicly listed but is likely expensive for a small project or startup.
- **Data granularity**: Only 24 hours of 15-minute interval data is available on the public site. Historical data beyond 24 hours requires the paid API.
- **No programmatic service discovery**: You must know the Downdetector URL slug for each service. There is no public directory API to list all monitored services.
- **Latency**: Report-based detection inherently lags behind the actual start of an outage, as it depends on users visiting Downdetector to file reports.

## Relevance to Our Use Case

- **Strengths**: Downdetector is excellent for detecting customer-facing outages at specific named companies (AWS, Cloudflare, GitHub, Slack, etc.). The report count time-series with baseline comparison provides a clear signal for anomaly detection. The issue-type breakdown and user comments add qualitative context.
- **Coverage**: Covers a broad range of services relevant to infrastructure monitoring -- cloud providers, CDNs, DNS services, SaaS platforms, ISPs, and more.
- **Access problem**: The primary challenge is reliable, legal access. Without paying for the official API, all access methods are fragile and potentially ToS-violating. For a production system, the unofficial scraping approach would be a constant maintenance burden.
- **Recommendation**: Downdetector data would be a valuable signal source if budget allows for the official API. For a free/low-cost approach, it could serve as a supplementary signal with the understanding that access may be intermittent. Playwright-based scraping from Python is the most practical unofficial approach, but should not be relied upon as a primary data source.
