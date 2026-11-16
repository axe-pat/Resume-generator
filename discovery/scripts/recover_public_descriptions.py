#!/usr/bin/env python3
"""Checkpoint public JD retrieval for the exact saved backlog; never search again."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from discovery.auto.public_job_description import fetch_public_listing, parse_public_listing
from discovery.scripts.audit_discovery_coverage import build_audit, listing_key, usable_jd
from discovery.scripts.recover_discovery_coverage import saved_jd_keys, saved_templates
from shared.discovery_identity import role_group_key


def recover(audit_path: Path, *, workers: int = 3, limit: int = 0,
            signed_in: bool = False, score: bool = False) -> Path:
    audit = json.loads(audit_path.read_text())
    source = Path(str(audit_path.with_suffix("")) + "-hydrate-input.json")
    recovered = saved_jd_keys(audit["since"])
    templates = saved_templates(audit["since"])
    cards = [c for c in json.loads(source.read_text())["cards"]
             if "linkedin.com/jobs/view/" in c.get("url", "")
             and listing_key(c) not in recovered and role_group_key(c) not in templates]
    cards.sort(key=lambda c: (
        not any(s in (c.get("title", "").lower()) for s in ("2027", "mba", "new grad", "graduate")),
        c.get("company", ""), c.get("title", ""),
    ))
    if limit:
        cards = cards[:limit]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output = ROOT / "discovery/auto/logs" / f"linkedin_live_raw_hydration_public_{stamp}.json"
    payload = {"status": "running", "method": "public_listing", "since": audit["since"],
               "source_raw_artifacts": [str(source)], "cards": [], "attempted": 0,
               "total": len(cards), "retrieval_counts": {}}

    def checkpoint():
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        temporary.replace(output)

    checkpoint()
    print(f"Public recovery: {len(cards)} saved listings; artifact: {output}", flush=True)
    counts = Counter()
    def save_result(card, result):
        item = {**card, **result, "retrieved_at": datetime.now().isoformat()}
        payload["cards"].append(item)
        payload["attempted"] += 1
        counts[result["retrieval_status"]] += 1
        payload["retrieval_counts"] = dict(counts)
        checkpoint()

    scored_keys = set()
    def score_survivors():
        if not score:
            return
        from discovery.scripts.audit_discovery_coverage import _current_classification
        from discovery.auto.linkedin_live import score_from_raw_artifacts
        import jobs as tracker
        blocked = tracker._load_blocklist()
        survivors = []
        for card in payload["cards"]:
            key = listing_key(card)
            if key in scored_keys or not usable_jd(card) or card.get("listing_availability") == "closed":
                continue
            current = _current_classification(card)
            if current.get("classification") == "keep" and not tracker._is_blocklisted(str(card.get("company") or ""), blocked):
                survivors.append(current)
                scored_keys.add(key)
        if survivors:
            path = output.with_name(output.stem + "-score-input.json")
            path.write_text(json.dumps({"jobs": survivors}, indent=2))
            try:
                score_from_raw_artifacts([str(path)], dry_run=False,
                                         model="claude-haiku-4-5-20251001", quiet=False)
            except Exception as exc:
                payload.setdefault("score_errors", []).append({"input": str(path), "error": str(exc)})
                checkpoint()
                print(f"Scoring deferred; retrieval continues: {exc}", flush=True)

    if signed_in:
        from playwright.async_api import async_playwright
        from discovery.auto.linkedin_live import _ensure_chrome_cdp
        _ensure_chrome_cdp(9222, launch_chrome=False, quiet=True)
        payload["method"] = "signed_in_listing"
        async def retrieve_signed_in():
          async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
            request = browser.contexts[0].request
            semaphore, pace = asyncio.Semaphore(workers), asyncio.Lock()
            last_start = 0.0
            async def retrieve(card):
                nonlocal last_start
                async with semaphore:
                    if payload.get("stop_reason"):
                        return
                    async with pace:
                        await asyncio.sleep(max(0, 1 - (time.monotonic() - last_start)))
                        last_start = time.monotonic()
                    try:
                        response = await request.get(card["url"], timeout=20000)
                        result = (parse_public_listing(await response.text(), requested_url=card["url"], final_url=response.url)
                                  if response.status == 200 else {"retrieval_status": f"http_{response.status}", "jd_text": ""})
                        await response.dispose()
                    except Exception as exc:
                        result = {"retrieval_status": "network_error", "retrieval_error": str(exc)[:300], "jd_text": ""}
                    save_result(card, result)
                    if result["retrieval_status"] in {"http_429", "http_999", "wrong_listing_or_login"}:
                        payload["stop_reason"] = "Signed-in access requires attention; pending listings preserved."
            for offset in range(0, len(cards), 30):
                await asyncio.gather(*(retrieve(card) for card in cards[offset:offset + 30]))
                print(f"Checked {payload['attempted']}/{len(cards)}; {dict(counts)}", flush=True)
                score_survivors()
                if payload.get("stop_reason"):
                    break
        asyncio.run(retrieve_signed_in())
    else:
      # Bounded groups avoid scheduling the entire backlog after a rate limit.
      with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, len(cards), 30):
            batch = cards[offset:offset + 30]
            futures = {executor.submit(fetch_public_listing, card): card for card in batch}
            for future in as_completed(futures):
                card = futures[future]
                result = future.result()
                save_result(card, result)
            print(f"Checked {payload['attempted']}/{len(cards)}; {dict(counts)}", flush=True)
            score_survivors()
            if counts["http_429"] or counts["http_999"]:
                payload["stop_reason"] = "Public access limited; preserving pending listings for another retrieval method."
                break
    payload["status"] = "completed" if payload["attempted"] == len(cards) and all(usable_jd(c) for c in payload["cards"]) else "partial"
    payload["finished_at"] = datetime.now().isoformat()
    checkpoint()
    score_survivors()
    print(f"Hydrated raw artifact: {output}", flush=True)
    updated = build_audit(audit["since"])
    print(f"Coverage audit: {updated}", flush=True)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--signed-in", action="store_true")
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("workers must be between 1 and 4")
    recover(args.audit, workers=args.workers, limit=args.limit,
            signed_in=args.signed_in, score=args.score)
