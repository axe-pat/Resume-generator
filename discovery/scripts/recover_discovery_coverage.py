#!/usr/bin/env python3
"""Resume saved JD retrieval in small checkpoints, then score eligible survivors."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from collections import defaultdict
from itertools import zip_longest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from discovery.scripts.audit_discovery_coverage import build_audit, listing_key, usable_jd, _dated
from shared.discovery_identity import national_recruitment_templates, role_group_key


def saved_jd_keys(since: str) -> set[str]:
    keys = set()
    for path in (ROOT / "discovery/auto/logs").glob("linkedin_live_raw_hydrat*.json"):
        if not _dated(path, since):
            continue
        try:
            payload = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        keys.update(listing_key(card) for card in payload.get("cards", []) if usable_jd(card))
    return keys


def saved_templates(since: str) -> dict:
    rows = []
    for path in (ROOT / "discovery/auto/logs").glob("linkedin_live_raw_hydrat*.json"):
        if not _dated(path, since):
            continue
        try:
            payload = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        rows.extend(card for card in payload.get("cards", []) if usable_jd(card))
    return national_recruitment_templates(rows)


def recover(audit_path: Path, *, batch_size: int = 25, max_batches: int = 0,
            score: bool = False) -> Path:
    audit = json.loads(audit_path.read_text())
    stem = audit_path.with_suffix("")
    inputs = json.loads(Path(str(stem) + "-hydrate-input.json").read_text())
    cards = [c for c in inputs["cards"] if re.search(r"linkedin\.com/jobs/view/\d+", c.get("url", ""))]
    previous_count = len(cards)
    already_recovered = saved_jd_keys(audit["since"])
    cards = [card for card in cards if listing_key(card) not in already_recovered]
    templates = saved_templates(audit["since"])
    grouped_variants = [card for card in cards if role_group_key(card) in templates]
    cards = [card for card in cards if role_group_key(card) not in templates]
    group_inventory = []
    for key, template in templates.items():
        group_inventory.append({
            **template,
            "advertised_variants": [
                {"url": card.get("url"), "advertised_location": card.get("location")}
                for card in inputs["cards"] if role_group_key(card) == key
            ],
        })
    group_path = Path(str(stem) + "-location-ad-groups.json")
    group_path.write_text(json.dumps({"groups": group_inventory}, indent=2))
    cards.sort(key=lambda c: (
        not bool(re.search(r"2027|mba|new.?grad|graduate|university", c["title"], re.I)),
        not bool(re.search(r"product|strategy|solutions|deployed|program", c["title"], re.I)),
    ))
    # Visit different employer/role groups before returning to city variants.
    role_groups = defaultdict(list)
    for card in cards:
        role_groups[role_group_key(card)].append(card)
    cards = [card for round_rows in zip_longest(*role_groups.values())
             for card in round_rows if card is not None]
    state = {"audit": str(audit_path), "status": "running", "batches": [],
             "remaining_non_linkedin": len(inputs["cards"]) - previous_count,
             "reused_saved_descriptions": len(already_recovered & {listing_key(c) for c in inputs["cards"]}),
             "grouped_location_variants": grouped_variants,
             "verified_template_groups": list(templates.values()),
             "location_ad_groups": str(group_path)}
    progress = Path(str(stem) + "-recovery-progress.json")
    if progress.exists():
        backup = Path(str(stem) + "-recovery-progress-before-" + datetime.now().strftime("%H%M%S") + ".json")
        backup.write_text(progress.read_text())
    state["pending_linkedin_cards"] = len(cards)
    progress.write_text(json.dumps(state, indent=2))
    print(f"Grouped {len(grouped_variants)} redundant national city ads; {len(cards)} LinkedIn cards remain.", flush=True)
    for offset in range(0, len(cards), batch_size):
        if max_batches and len(state["batches"]) >= max_batches:
            break
        # A newly retrieved second sample can establish a template mid-run.
        templates = saved_templates(audit["since"])
        batch = []
        for card in cards[offset:offset + batch_size]:
            if role_group_key(card) in templates:
                state["grouped_location_variants"].append(card)
            else:
                batch.append(card)
        if not batch:
            continue
        batch_path = Path(str(stem) + f"-recovery-batch-{offset // batch_size:04d}.json")
        batch_path.write_text(json.dumps({"cards": batch, "count": len(batch),
                                         "coverage_audit": str(audit_path)}, indent=2))
        state["current_input"] = str(batch_path)
        state["current_offset"] = offset
        progress.write_text(json.dumps(state, indent=2))
        result = subprocess.run([
            sys.executable, "-u", "discovery/auto/linkedin_live.py",
            "--hydrate-from-raw", str(batch_path),
        ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout, end="", flush=True)
        pointers = [line.split(": ", 1)[1] for line in result.stdout.splitlines()
                    if line.startswith("Hydrated raw artifact: ")]
        record = {"input": str(batch_path), "returncode": result.returncode,
                  "artifact": pointers[-1] if pointers else "", "attempted": len(batch)}
        state["batches"].append(record)
        progress.write_text(json.dumps(state, indent=2))
        if not pointers:
            break
        saved = json.loads(Path(pointers[-1]).read_text())
        if not any(c.get("jd_text", "").strip() for c in saved.get("cards", [])):
            break
    updated = build_audit(audit["since"])
    if score:
        score_input = Path(str(updated.with_suffix("")) + "-score-input.json")
        if json.loads(score_input.read_text())["jobs"]:
            subprocess.run([
                sys.executable, "-u", "discovery/auto/linkedin_live.py",
                "--score-from-raw", str(score_input),
            ], cwd=ROOT, check=True)
            updated = build_audit(audit["since"])
    state.update({"status": json.loads(updated.read_text())["status"],
                  "updated_audit": str(updated),
                  "finished_at": datetime.now().isoformat()})
    progress.write_text(json.dumps(state, indent=2))
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-batches", type=int, default=0, help="0 processes the full saved backlog.")
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    path = recover(args.audit, batch_size=args.batch_size,
                   max_batches=args.max_batches, score=args.score)
    print(f"Coverage audit: {path}")
    raise SystemExit(0 if json.loads(path.read_text())["status"] == "reconciled" else 2)
