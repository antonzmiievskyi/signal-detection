"""
Detect which CDN/edge provider serves a domain via HTTP response headers.

Used to scope provider-level status incidents to companies that actually
use the affected provider, instead of flagging every monitored company
when any provider has an issue.

Detection is best-effort: many sites are behind multiple layers, and some
hide their edge. None is returned when nothing matched. Results are
cached in .provider_cache.json (gitignored) to avoid hammering hosts.
"""

import json
import os
from typing import Optional

import requests

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", ".provider_cache.json")

# (provider_name, predicate over lowercased headers dict)
SIGNATURES = [
    ("Cloudflare", lambda h: h.get("server", "").lower() == "cloudflare" or "cf-ray" in h),
    ("Akamai", lambda h: "akamaighost" in h.get("server", "").lower()
                          or "x-akamai-transformed" in h
                          or h.get("server", "").lower().startswith("akamai")),
    ("Imperva", lambda h: "x-iinfo" in h or "imperva" in h.get("server", "").lower()),
    ("F5", lambda h: "bigip" in h.get("server", "").lower()
                      or h.get("server", "").lower().startswith("f5")),
]


def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _match_provider(headers: dict) -> Optional[str]:
    lowered = {k.lower(): v for k, v in headers.items()}
    for name, pred in SIGNATURES:
        if pred(lowered):
            return name
    return None


def _probe(domain: str, timeout: float = 5.0) -> Optional[str]:
    url = f"https://{domain}"
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        provider = _match_provider(resp.headers)
        if provider or resp.status_code < 400:
            return provider
        # HEAD blocked — fall back to a tiny GET
        resp = requests.get(url, timeout=timeout, allow_redirects=True, stream=True)
        try:
            return _match_provider(resp.headers)
        finally:
            resp.close()
    except requests.RequestException:
        return None


def detect_providers(domains: list[str], use_cache: bool = True) -> dict[str, Optional[str]]:
    """Resolve providers for many domains in one call (single cache load/save)."""
    cache = _load_cache() if use_cache else {}
    out: dict[str, Optional[str]] = {}
    dirty = False
    for d in domains:
        if not d:
            out[d] = None
            continue
        if use_cache and d in cache:
            out[d] = cache[d].get("provider")
            continue
        provider = _probe(d)
        out[d] = provider
        if use_cache:
            cache[d] = {"provider": provider}
            dirty = True
    if dirty and use_cache:
        _save_cache(cache)
    return out


def detect_provider(domain: str, use_cache: bool = True) -> Optional[str]:
    """Single-domain convenience wrapper."""
    return detect_providers([domain], use_cache=use_cache).get(domain)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python detect_provider.py <domain> [<domain> ...]")
        sys.exit(1)
    results = detect_providers(sys.argv[1:])
    for d, p in results.items():
        print(f"{d:<40} {p or '-'}")
