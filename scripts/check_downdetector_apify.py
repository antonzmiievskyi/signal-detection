"""
Downdetector Outage Checker (Apify + AI version)

Uses the Apify ScrapeUnblocker actor to fetch Downdetector pages
through Cloudflare protection, then uses OpenAI to analyze the page
content — extracting status, report counts, and user comment insights.

Requires: APIFY_TOKEN and OPENAI_API_KEY environment variables.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

from apify_client import ApifyClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "..", "companies.json")
BASE_URL = "https://downdetector.com/status"
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ACTOR_ID = "scrapeunblocker/scrapeunblocker"


def load_companies() -> list[dict]:
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def fetch_page_via_apify(url: str) -> dict:
    """Fetch a single Cloudflare-protected page using Apify ScrapeUnblocker.

    Returns dict with 'html' on success or 'error' on failure.
    """
    client = ApifyClient(APIFY_TOKEN)

    try:
        run = client.actor(ACTOR_ID).call(
            run_input={"url": url, "renderJs": True},
            timeout_secs=120,
        )

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return {"error": f"No dataset returned (status: {run.get('status')})"}

        items = list(client.dataset(dataset_id).iterate_items())
        if not items:
            return {"error": "Empty dataset returned"}

        item = items[0]
        html = item.get("html") or item.get("body") or item.get("content") or ""

        if not html:
            return {"error": f"No HTML in response. Keys: {list(item.keys())}"}

        return {"html": html, "status_code": item.get("statusCode", 200)}

    except Exception as e:
        return {"error": str(e)}


def fetch_pages_via_apify(urls: list[str]) -> dict[str, dict]:
    """Fetch multiple pages sequentially via Apify ScrapeUnblocker.

    Returns dict mapping URL -> {'html': ..., 'status_code': ...} or {'error': ...}.
    """
    results = {}
    for url in urls:
        results[url] = fetch_page_via_apify(url)
    return results


def extract_visible_text(html: str) -> str:
    """Extract visible text from HTML, stripping tags, scripts, styles, and i18n JSON."""
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL)
    # Remove RSC payload (self.__next_f.push) — contains translation strings
    text = re.sub(r'self\.__next_f\.push\([^)]+\)', ' ', text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode HTML entities
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'&\w+;', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_title(html: str) -> str:
    """Extract the page title."""
    title = re.search(r'<title>\s*(.+?)\s*</title>', html, re.DOTALL)
    return title.group(1).strip() if title else ""


def extract_comments_section(html: str) -> str:
    """Extract user comments from the HTML for AI analysis."""
    # Comments are in the rendered HTML as text content
    # Look for comment-like patterns: username + timestamp + text
    comments = []

    # Try to find comment blocks in rendered HTML
    comment_blocks = re.findall(
        r'(?:ago|minutes?\s+ago|hours?\s+ago|days?\s+ago)[^<]{0,500}',
        html, re.IGNORECASE
    )
    for block in comment_blocks[:30]:  # limit to 30 comments
        clean = re.sub(r'<[^>]+>', ' ', block)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 10:
            comments.append(clean)

    return "\n".join(comments) if comments else ""


def analyze_with_ai(company: str, title: str, visible_text: str, comments: str) -> dict:
    """Use OpenAI to analyze Downdetector page content.

    Returns structured analysis with status, severity, and comment insights.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Truncate visible text to avoid token limits
    text_sample = visible_text[:3000]
    comments_sample = comments[:2000] if comments else "No comments found."

    prompt = f"""Analyze this Downdetector status page data for "{company}".

PAGE TITLE: {title or "Not available"}

VISIBLE PAGE TEXT (excerpt):
{text_sample}

USER COMMENTS (excerpt):
{comments_sample}

Extract the following as JSON (no markdown, just raw JSON):
{{
  "outage_detected": true/false/null,
  "severity": "none" | "minor" | "major" | "critical",
  "status_summary": "one-line status description",
  "report_trend": "rising" | "falling" | "stable" | "unknown",
  "issue_types": ["list of reported issue categories, e.g. server, login, app, website"],
  "comment_count": number or null,
  "comment_sentiment": "positive" | "negative" | "mixed" | "neutral" | "unknown",
  "comment_summary": "2-3 sentence summary of what users are reporting",
  "geographic_pattern": "any geographic concentration mentioned, or null",
  "confidence": "high" | "medium" | "low"
}}

Rules:
- outage_detected: true if there are active problems, false if no problems, null if can't determine
- severity: based on report volume and user sentiment
- If the page title says "down?" or "outages" that's a strong outage signal
- If page title says "no problems" that means no outage
- If you can't find meaningful status data, set confidence to "low"
- Do NOT infer from translation/template strings like "methodology_status_*"
- Focus on ACTUAL reported issues and user comments"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        return {
            "outage_detected": None,
            "severity": "unknown",
            "status_summary": f"AI analysis failed: {e}",
            "confidence": "low",
        }


def parse_downdetector_html(html: str, slug: str) -> dict:
    """Parse Downdetector HTML using AI analysis.

    Extracts visible text and comments, sends to OpenAI for structured analysis.
    Falls back to title-based detection if OPENAI_API_KEY is not set.
    """
    result = {"status": "ok", "url": f"{BASE_URL}/{slug}/"}
    title = extract_title(html)
    company = slug.replace("-", " ").title()

    if OPENAI_API_KEY:
        visible_text = extract_visible_text(html)
        comments = extract_comments_section(html)
        ai_result = analyze_with_ai(company, title, visible_text, comments)

        result["outage_detected"] = ai_result.get("outage_detected")
        result["severity"] = ai_result.get("severity", "unknown")
        result["detail"] = ai_result.get("status_summary", "")
        result["report_trend"] = ai_result.get("report_trend", "unknown")
        result["issue_types"] = ai_result.get("issue_types", [])
        result["comment_sentiment"] = ai_result.get("comment_sentiment", "unknown")
        result["comment_summary"] = ai_result.get("comment_summary", "")
        result["geographic_pattern"] = ai_result.get("geographic_pattern")
        result["confidence"] = ai_result.get("confidence", "low")
    else:
        # Fallback: title-based detection (no AI)
        if title:
            title_lower = title.lower()
            if "no problems" in title_lower or "no issues" in title_lower:
                result["outage_detected"] = False
                result["detail"] = f"No problems (title: {title})"
            elif " down?" in title_lower or "outage" in title_lower or "problems" in title_lower:
                result["outage_detected"] = True
                result["detail"] = f"Outage detected (title: {title})"
            else:
                result["outage_detected"] = None
                result["detail"] = f"Status unclear (title: {title})"
        else:
            result["outage_detected"] = None
            result["detail"] = "Status unclear — no title and no AI key"

    return result


def process_fetch_result(fetch_result: dict, slug: str) -> dict:
    """Process a single fetch result into a Downdetector check result."""
    if "error" in fetch_result:
        return {"status": "error", "detail": fetch_result["error"]}

    html = fetch_result["html"]

    if "cf-browser-verification" in html or "challenge-platform" in html:
        return {"status": "blocked", "detail": "Cloudflare challenge not bypassed"}

    return parse_downdetector_html(html, slug)


def main():
    if not APIFY_TOKEN:
        print("ERROR: Set APIFY_TOKEN environment variable.")
        print("  Sign up free at https://console.apify.com/sign-up")
        print("  Get your token at https://console.apify.com/account/integrations")
        sys.exit(1)

    if not OPENAI_API_KEY:
        print("WARNING: OPENAI_API_KEY not set. Using title-based detection only (no AI analysis).")

    companies = load_companies()
    valid_companies = [c for c in companies if c.get("downdetector_slug")]

    print("Downdetector Outage Checker (Apify + AI Analysis)")
    print(f"Checking {len(valid_companies)} companies")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Actor: {ACTOR_ID}")
    print(f"AI analysis: {'enabled' if OPENAI_API_KEY else 'disabled'}")
    print("=" * 70)

    # Build URL list and slug mapping
    url_to_company = {}
    for company in valid_companies:
        slug = company["downdetector_slug"]
        url = f"{BASE_URL}/{slug}/"
        url_to_company[url] = {"company": company["company"], "slug": slug}

    urls = list(url_to_company.keys())
    print(f"\n  Fetching {len(urls)} pages...", flush=True)

    fetch_results = fetch_pages_via_apify(urls)

    # Process results
    results = []
    for url, info in url_to_company.items():
        name = info["company"]
        slug = info["slug"]

        print(f"\n  Analyzing {name}...", end="", flush=True)
        fetch_result = fetch_results.get(url, {"error": "URL not in results"})
        result = process_fetch_result(fetch_result, slug)
        result["company"] = name
        result["slug"] = slug
        results.append(result)

        if result["status"] == "blocked":
            print(f" BLOCKED - {result['detail']}")
        elif result["status"] == "error":
            print(f" ERROR - {result['detail']}")
        elif result["status"] == "ok":
            outage = result.get("outage_detected")
            severity = result.get("severity", "")
            confidence = result.get("confidence", "")

            if outage:
                sev_label = f" [{severity.upper()}]" if severity and severity != "unknown" else ""
                print(f" *** OUTAGE{sev_label} ***")
                print(f"    Status: {result.get('detail', '')}")
                if result.get("issue_types"):
                    print(f"    Issues: {', '.join(result['issue_types'])}")
                if result.get("report_trend") and result["report_trend"] != "unknown":
                    print(f"    Trend: {result['report_trend']}")
                if result.get("comment_summary"):
                    print(f"    Comments ({result.get('comment_sentiment', '?')}): {result['comment_summary']}")
                if result.get("geographic_pattern"):
                    print(f"    Geography: {result['geographic_pattern']}")
                if confidence:
                    print(f"    Confidence: {confidence}")
            elif outage is False:
                print(f" No problems")
                if result.get("detail"):
                    print(f"    {result['detail']}")
            else:
                print(f" {result.get('detail', 'Unknown')}")

    # Summary
    print(f"\n{'='*70}")
    print("Summary:")
    ok = [r for r in results if r["status"] == "ok"]
    outages = [r for r in results if r.get("outage_detected")]
    errors = [r for r in results if r["status"] == "error"]
    blocked = [r for r in results if r["status"] == "blocked"]
    print(f"  Checked: {len(results)} | OK: {len(ok)} | Errors: {len(errors)} | Blocked: {len(blocked)}")
    if outages:
        print(f"  OUTAGES DETECTED:")
        for r in outages:
            sev = f" [{r.get('severity', '?').upper()}]" if r.get("severity") else ""
            print(f"    - {r['company']}{sev}: {r.get('detail', '')}")
    else:
        print(f"  No outages detected.")


if __name__ == "__main__":
    main()
