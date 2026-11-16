"""Posting identity independent of LinkedIn tracking links and trailing slashes."""
import re
import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical_listing_url(url: str) -> str:
    url = str(url or "").strip()
    linkedin = re.search(r"linkedin\.com/jobs/view/(\d+)", url, re.I)
    if linkedin:
        return "https://www.linkedin.com/jobs/view/" + linkedin.group(1)
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")
             and k.lower() not in {"gh_src", "trackingid", "refid", "source", "src"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                      parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def role_group_key(row: dict) -> tuple[str, str]:
    return tuple(re.sub(r"\s+", " ", str(value or "")).strip().casefold() for value in (
        row.get("company"), row.get("role_title") or row.get("title"),
    ))


def national_recruitment_templates(rows) -> dict[tuple[str, str], dict]:
    """Group only descriptions independently verified across national city ads.

    Different descriptions or genuine location-specific roles remain distinct.
    Every advertised URL stays available in the group's evidence.
    """
    groups = {}
    for row in rows:
        text = str(row.get("jd_text") or "").strip()
        if not text:
            continue
        key = role_group_key(row)
        signature = hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()
        versions = groups.setdefault(key, {})
        versions.setdefault(signature, {})[canonical_listing_url(row.get("url", ""))] = row
    verified = {}
    for key, versions in groups.items():
        if len(versions) != 1:
            continue
        signature, postings = next(iter(versions.items()))
        postings = {url: row for url, row in postings.items() if url}
        if len(postings) < 2:
            continue
        representative = postings[sorted(postings)[0]]
        text = representative["jd_text"]
        if not (re.search(r"\brecruit(?:ing)?\s+nationally\b", text, re.I)
                and re.search(r"\brelocat\w*\b", text, re.I)
                and re.search(r"\b(?:position|role|job)\s+is\s+based\b", text, re.I)):
            continue
        links = re.findall(r"https?://[^\s<>]+", text)
        canonical = next((url.rstrip(".,)") for url in links
                          if re.search(r"/jobs?/", url, re.I)), representative["url"])
        verified[key] = {
            "company": representative.get("company", ""),
            "role_title": representative.get("role_title") or representative.get("title"),
            "representative_url": representative["url"], "canonical_role_url": canonical,
            "description_sha256": signature, "verified_posting_urls": sorted(postings),
            "identical_description_count": len(postings),
        }
    return verified
