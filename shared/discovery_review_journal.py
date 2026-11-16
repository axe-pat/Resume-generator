"""Persist individual reviews before tracker/report writes; reuse unchanged inputs."""
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = ROOT / "discovery/auto/checkpoints/review-results.jsonl"

def review_batch(jobs, *, score_fn, journal=JOURNAL, **kwargs):
    policy = b""
    for path in [ROOT / "profile/profile.md", ROOT / "shared/job_eligibility.py", ROOT / "discovery/auto/scorer_prompt.md"]:
        policy += path.read_bytes()
    def key(row):
        body = {k: row.get(k) for k in ("url", "company", "role_title", "jd_text", "lane")}
        return hashlib.sha256(policy + json.dumps([kwargs.get("model"), body], sort_keys=True).encode()).hexdigest()
    cache = {}
    if journal.exists():
        for line in journal.read_text().splitlines():
            try:
                item = json.loads(line)
                if time.time() - item.get('saved_at', 0) < 7*86400:
                    cache[item["key"]] = item["result"]
            except (ValueError, KeyError):
                continue  # A torn final append does not invalidate earlier reviews.
    missing = [row for row in jobs if key(row) not in cache]
    original_keys = {str(row.get('url')): key(row) for row in missing}
    journal.parent.mkdir(parents=True, exist_ok=True)
    def save(result):
        if result.get("decision") in {None, "Error"} or result.get("_run_timeout_unscored"):
            return
        record = {"key": original_keys.get(str(result.get('url')), key(result)), "result": result, "saved_at": time.time()}
        with journal.open("a") as stream:
            stream.write(json.dumps(record, default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        cache[record["key"]] = result
    fresh = score_fn(missing, on_result=save, **kwargs) if missing else []
    by_key = {key(r): r for r in fresh}
    output = []
    for row in jobs:
        k = key(row)
        result = dict(by_key.get(k, cache.get(k, row)))
        result['review_journal_cache_hit'] = k in cache and k not in by_key
        output.append(result)
    return output
