"""Read a public LinkedIn listing without browser navigation or model calls."""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import requests

from discovery.auto.scorer import _jd_quality_issue


def posting_id(url: str) -> str:
    match = re.search(r"/jobs/view/(?:[^/?#]*-)?(\d+)(?:[/?#]|$)", url)
    return match.group(1) if match else ""


def parse_public_listing(html: str, *, requested_url: str, final_url: str) -> dict:
    expected = posting_id(requested_url)
    actual = posting_id(final_url)
    if not expected or actual != expected:
        return {"retrieval_status": "wrong_listing_or_login", "jd_text": ""}
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".show-more-less-html__markup, .description__text")
    text = node.get_text("\n", strip=True) if node else ""
    if not text:
        # The signed-in layout uses generated CSS classes. Scope extraction to
        # the smallest description section headed by the visible job heading.
        heading = soup.find(string=lambda value: value and value.strip() == "About the job")
        if heading:
            for parent in heading.parents:
                candidate = parent.get_text("\n", strip=True)
                if len(candidate) > 200:
                    text = re.sub(r"^About the job\s*", "", candidate).strip()
                    break
    # Some public layouts expose the full description only in structured data.
    if not text:
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or script.get_text())
            except (TypeError, ValueError):
                continue
            objects = data if isinstance(data, list) else [data]
            for item in objects:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    text = BeautifulSoup(item.get("description", ""), "html.parser").get_text("\n", strip=True)
                    break
    issue = _jd_quality_issue(text)
    if issue:
        return {"retrieval_status": "invalid_description:" + issue, "jd_text": ""}
    title = soup.select_one(".top-card-layout__title, .topcard__title, h1")
    company = soup.select_one(".topcard__org-name-link, .topcard__flavor")
    body = soup.get_text(" ", strip=True)
    closed = bool(re.search(r"\bNo longer accepting applications\b", body, re.I))
    return {
        "retrieval_status": "retrieved",
        "jd_text": text,
        "retrieved_title": title.get_text(" ", strip=True) if title else "",
        "retrieved_company": company.get_text(" ", strip=True) if company else "",
        "retrieval_url": final_url,
        "listing_availability": "closed" if closed else "not_marked_closed",
    }


def fetch_public_listing(card: dict, *, timeout: float = 20) -> dict:
    url = str(card.get("url") or "")
    if urlsplit(url).hostname not in {"www.linkedin.com", "linkedin.com"}:
        return {"retrieval_status": "unsupported_host", "jd_text": ""}
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return {"retrieval_status": f"http_{response.status_code}", "jd_text": ""}
        return parse_public_listing(response.text, requested_url=url, final_url=response.url)
    except requests.RequestException as exc:
        return {"retrieval_status": "network_error", "retrieval_error": str(exc)[:300], "jd_text": ""}
