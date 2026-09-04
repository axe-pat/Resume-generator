"""Deterministically inventory variants exposed by the live resume prompts.

The extractor is intentionally read-only with respect to the PM and NONPM prompt
files.  It records exact prompt text and prompt-owned selectability only; quality,
facts, role tags, and admission decisions belong to other layers.

Run from the repository root:

    PYTHONPATH=. venv/bin/python -m shared.prompt_variant_inventory --check
    PYTHONPATH=. venv/bin/python -m shared.prompt_variant_inventory --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = REPO_ROOT / "resume" / "freeform" / "prompts"
PM_PROMPT = PROMPT_DIR / "freeform_master_v2.txt"
NONPM_PROMPT = PROMPT_DIR / "freeform_master_nonpm.txt"
VARIANT_DIR = REPO_ROOT / "resume" / "variants"
SELECTABLE_SNAPSHOT = VARIANT_DIR / "live_prompt_variants.jsonl"
REFERENCE_SNAPSHOT = VARIANT_DIR / "prompt_reference_variants.jsonl"

SELECTABLE = "selectable"
PROHIBITED_REFERENCE = "prohibited-reference"
REFERENCE_ONLY = "reference-only"
SELECTABILITY_VALUES = frozenset(
    {SELECTABLE, PROHIBITED_REFERENCE, REFERENCE_ONLY}
)

_BRACKET_LABEL = re.compile(r"^\s*\[([^]]+)\]")
_PROJECT_LABEL = re.compile(r"^\s*(P-[A-Z]+)\s+\[([^]]+)\]")
_PM_STORY = re.compile(r"\bSTORY\s+([A-Z][A-Z0-9-]+)(?::|\s)")
_PM_OPTION = re.compile(r"\bOption\s+([A-Z][A-Z0-9-]+)(?::|\s)")
_NONPM_STORY = re.compile(r"^[A-Z]\d+\s+—\s+([A-Z][A-Z0-9-]+)")


@dataclass(frozen=True)
class PromptVariantRecord:
    """Exact text plus metadata derivable directly from a live prompt."""

    stable_id: str
    track: str
    story: str
    label: str
    source_path: str
    source_line: int
    selectability: str
    text: str
    text_sha256: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))


def _slug(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _find_marker(lines: Sequence[str], marker: str, *, start: int = 0) -> int:
    for index in range(start, len(lines)):
        if marker in lines[index]:
            return index
    raise ValueError(f"Prompt marker not found: {marker!r}")


def _quoted_text_after(lines: Sequence[str], label_index: int) -> str | None:
    """Return the next complete double-quoted block after a variant label."""
    chunks: list[str] = []
    opened = False
    # Selectable prose is below its label. A label annotation can itself quote
    # an opener example; treating that annotation as the variant silently
    # corrupts the snapshot (the G-PRICING funnel-synthesis label did this).
    for index in range(label_index + 1, min(len(lines), label_index + 12)):
        line = lines[index]
        if (
            _BRACKET_LABEL.match(line)
            or _PROJECT_LABEL.match(line)
            or _PM_STORY.search(line)
            or _PM_OPTION.search(line)
            or _NONPM_STORY.match(line)
        ):
            return None
        if not opened:
            if '"' not in line:
                continue
            _, remainder = line.split('"', 1)
            opened = True
        else:
            remainder = line
        if '"' in remainder:
            before_close, _ = remainder.split('"', 1)
            chunks.append(before_close.strip())
            return " ".join(chunk for chunk in chunks if chunk).strip()
        chunks.append(remainder.strip())
    return None


def _record(
    *,
    track: str,
    story: str,
    label: str,
    source_path: Path,
    source_line: int,
    selectability: str,
    text: str,
) -> PromptVariantRecord:
    if selectability not in SELECTABILITY_VALUES:
        raise ValueError(f"Unknown selectability {selectability!r}")
    stable_id = f"{track}/{_slug(story)}/{_slug(label)}"
    return PromptVariantRecord(
        stable_id=stable_id,
        track=track,
        story=story,
        label=label,
        source_path=_relative(source_path),
        source_line=source_line,
        selectability=selectability,
        text=text,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def extract_pm_variants(path: Path = PM_PROMPT) -> tuple[PromptVariantRecord, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    flairx_start = _find_marker(lines, "STORY POOL — FLAIRX AI")
    prohibited_start = _find_marker(lines, "LEGACY INTUIT STORY REFERENCE")
    fluo_start = _find_marker(lines, "VENTURE PRODUCT POOL — FLUO")
    summary_start = _find_marker(lines, "PROFESSIONAL SUMMARY POOL")
    checklist_start = _find_marker(lines, "PRE-GENERATION CHECKLIST")
    skills_start = _find_marker(lines, "SKILLS POOL — for SECTION 4")
    skills_end = _find_marker(lines, "SECTION 4 — SKILLS & INTERESTS", start=skills_start)

    records: list[PromptVariantRecord] = []
    current_story: str | None = None
    current_selectability: str | None = None

    for index, line in enumerate(lines):
        if index == flairx_start:
            current_selectability = SELECTABLE
            current_story = None
        elif index == prohibited_start:
            current_selectability = PROHIBITED_REFERENCE
            current_story = None
        elif index == fluo_start:
            current_selectability = SELECTABLE
            current_story = "FLUO"
        elif index == summary_start:
            current_selectability = REFERENCE_ONLY
            current_story = "SUMMARY"
        elif index == checklist_start:
            current_selectability = None
            current_story = None
        elif index == skills_start:
            current_selectability = SELECTABLE
            current_story = None
        elif index == skills_end:
            current_selectability = None
            current_story = None

        if current_selectability is None:
            continue

        story_match = _PM_STORY.search(line)
        option_match = _PM_OPTION.search(line)
        if option_match:
            current_story = option_match.group(1)
        elif story_match:
            current_story = story_match.group(1)
        elif "ANALYTICS / SKILLS ROW TEMPLATES" in line:
            current_story = "SKILLS-ANALYTICS"
        elif "COMMUNITY (pick one)" in line:
            current_story = "SKILLS-COMMUNITY"

        label_match = _BRACKET_LABEL.match(line)
        if not label_match or current_story is None:
            continue
        text = _quoted_text_after(lines, index)
        if text is None:
            continue
        records.append(
            _record(
                track="pm",
                story=current_story,
                label=label_match.group(1).strip(),
                source_path=path,
                source_line=index + 1,
                selectability=current_selectability,
                text=text,
            )
        )
    return tuple(records)


def extract_nonpm_variants(
    path: Path = NONPM_PROMPT,
) -> tuple[PromptVariantRecord, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    proof_start = _find_marker(lines, "FIRST-CLASS NON-PM PROOF UNITS")
    proof_end = _find_marker(lines, "Rules for using proof units", start=proof_start)
    experience_start = _find_marker(lines, "STORY POOL — GOJEK")
    summary_start = _find_marker(lines, "PROFESSIONAL SUMMARY POOL")
    summary_end = _find_marker(lines, "STRATEGY PROJECT ROW", start=summary_start)

    records: list[PromptVariantRecord] = []
    current_story: str | None = None
    active = False

    for index, line in enumerate(lines):
        if index == proof_start:
            active = True
            current_story = None
        elif index == proof_end:
            active = False
            current_story = None
        elif index == experience_start:
            active = True
            current_story = None
        elif index == summary_start:
            active = True
            current_story = "SUMMARY"
        elif index == summary_end:
            active = False
            current_story = None

        if not active:
            continue

        project_match = _PROJECT_LABEL.match(line)
        if project_match:
            story, label = project_match.groups()
            text = _quoted_text_after(lines, index)
            if text is not None:
                records.append(
                    _record(
                        track="nonpm",
                        story=story,
                        label=label.strip(),
                        source_path=path,
                        source_line=index + 1,
                        selectability=SELECTABLE,
                        text=text,
                    )
                )
            continue

        story_match = _NONPM_STORY.match(line)
        if story_match:
            current_story = story_match.group(1)
            continue

        label_match = _BRACKET_LABEL.match(line)
        if not label_match or current_story is None:
            continue
        text = _quoted_text_after(lines, index)
        if text is None:
            continue
        records.append(
            _record(
                track="nonpm",
                story=current_story,
                label=label_match.group(1).strip(),
                source_path=path,
                source_line=index + 1,
                selectability=SELECTABLE,
                text=text,
            )
        )
    return tuple(records)


def extract_prompt_inventory() -> tuple[PromptVariantRecord, ...]:
    """Return all variant records in deterministic prompt/source order."""
    records = extract_pm_variants() + extract_nonpm_variants()
    stable_ids = [record.stable_id for record in records]
    if len(stable_ids) != len(set(stable_ids)):
        duplicates = sorted(
            stable_id for stable_id in set(stable_ids) if stable_ids.count(stable_id) > 1
        )
        raise ValueError(f"Duplicate stable variant IDs: {duplicates}")
    return records


def partition_inventory(
    records: Iterable[PromptVariantRecord],
) -> tuple[tuple[PromptVariantRecord, ...], tuple[PromptVariantRecord, ...]]:
    records = tuple(records)
    selectable = tuple(
        record for record in records if record.selectability == SELECTABLE
    )
    references = tuple(
        record for record in records if record.selectability != SELECTABLE
    )
    return selectable, references


def render_jsonl(records: Iterable[PromptVariantRecord]) -> str:
    records = tuple(records)
    return "".join(f"{record.to_json()}\n" for record in records)


def write_snapshots() -> tuple[Path, Path]:
    """Write derived snapshots; never writes to a prompt file."""
    selectable, references = partition_inventory(extract_prompt_inventory())
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    SELECTABLE_SNAPSHOT.write_text(render_jsonl(selectable), encoding="utf-8")
    REFERENCE_SNAPSHOT.write_text(render_jsonl(references), encoding="utf-8")
    return SELECTABLE_SNAPSHOT, REFERENCE_SNAPSHOT


def check_snapshots() -> list[str]:
    """Return drift errors without mutating snapshots or prompts."""
    selectable, references = partition_inventory(extract_prompt_inventory())
    errors: list[str] = []
    expected = (
        (SELECTABLE_SNAPSHOT, render_jsonl(selectable)),
        (REFERENCE_SNAPSHOT, render_jsonl(references)),
    )
    for path, content in expected:
        if not path.exists():
            errors.append(f"missing snapshot: {_relative(path)}")
        elif path.read_text(encoding="utf-8") != content:
            errors.append(f"prompt inventory drift: {_relative(path)}")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if snapshots drift")
    mode.add_argument("--write", action="store_true", help="refresh derived snapshots")
    args = parser.parse_args(argv)

    if args.write:
        selectable_path, reference_path = write_snapshots()
        selectable, references = partition_inventory(extract_prompt_inventory())
        print(
            f"wrote {len(selectable)} selectable records to "
            f"{_relative(selectable_path)}"
        )
        print(
            f"wrote {len(references)} reference records to "
            f"{_relative(reference_path)}"
        )
        return 0

    errors = check_snapshots()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    selectable, references = partition_inventory(extract_prompt_inventory())
    print(f"prompt inventory current: {len(selectable)} selectable, {len(references)} reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
