"""Metadata-owned generation routing and the Lane C adapter boundary.

Queue lanes describe which generation system may handle an application.  They
are not resume archetypes and must be resolved before the PM/NONPM router sees
the job.  In particular, explicit ``lane: C`` metadata can never fall through
to the professional generator.

No Lane C generator is installed here.  The registry is an intentional seam:
until a caller registers an adapter, dispatch fails closed with an actionable
error instead of silently producing the wrong document shape.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping


class GenerationPath(str, Enum):
    PROFESSIONAL = "professional"
    LANE_C = "lane-c"


class GenerationRoutingError(RuntimeError):
    """Base class for failures that make safe route selection impossible."""


class GenerationMetadataError(GenerationRoutingError):
    """Raised when present metadata cannot be trusted for route selection."""


class LaneCGeneratorNotRegistered(GenerationRoutingError):
    """Raised rather than allowing Lane C to enter the PM/NONPM pipeline."""


@dataclass(frozen=True)
class LaneCGenerationRequest:
    company: str
    app_dir: Path
    jd_path: Path
    metadata: Mapping[str, object]
    options: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LaneCGenerationResult:
    success: bool
    artifacts: tuple[Path, ...] = ()
    error: str = ""


LaneCGeneratorAdapter = Callable[[LaneCGenerationRequest], LaneCGenerationResult]

_lane_c_generator: LaneCGeneratorAdapter | None = None


def read_generation_metadata(app_dir: Path) -> dict[str, object]:
    """Read metadata without swallowing errors that could conceal ``lane: C``.

    Legacy/manual application folders may have no metadata and remain eligible
    for the professional route.  A present but malformed metadata file is
    different: proceeding would make the route unknowable, so it blocks.
    """

    metadata_path = Path(app_dir) / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GenerationMetadataError(
            f"Cannot safely select a generator because {metadata_path} is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GenerationMetadataError(
            f"Cannot safely select a generator because {metadata_path} must contain a JSON object."
        )
    return payload


def resolve_generation_path(metadata: Mapping[str, object]) -> GenerationPath:
    """Resolve solely from explicit lane metadata; never infer from title/JD."""

    lane = str(metadata.get("lane") or "").strip().upper()
    if lane in {"", "A", "B"}:
        return GenerationPath.PROFESSIONAL
    if lane == "C":
        return GenerationPath.LANE_C
    raise GenerationMetadataError(
        f"Cannot safely select a generator because metadata lane={lane!r} is invalid; "
        "expected A, B, C, or a blank legacy value."
    )


def register_lane_c_generator(
    adapter: LaneCGeneratorAdapter,
    *,
    replace: bool = False,
) -> None:
    """Install the Lane C adapter at an application entrypoint."""

    if not callable(adapter):
        raise TypeError("Lane C generator adapter must be callable")
    global _lane_c_generator
    if _lane_c_generator is not None and not replace:
        raise RuntimeError("A Lane C generator adapter is already registered")
    _lane_c_generator = adapter


def clear_lane_c_generator() -> None:
    """Clear the process-local adapter registry (primarily for tests)."""

    global _lane_c_generator
    _lane_c_generator = None


def lane_c_generator_registered() -> bool:
    return _lane_c_generator is not None


def dispatch_lane_c_generation(request: LaneCGenerationRequest) -> LaneCGenerationResult:
    """Dispatch an explicit Lane C request or fail closed before generic work."""

    if resolve_generation_path(request.metadata) is not GenerationPath.LANE_C:
        raise ValueError("Lane C dispatch requires metadata with lane == C")
    if _lane_c_generator is None:
        raise LaneCGeneratorNotRegistered(
            "Lane C generation is not configured. Refusing to send metadata lane=C "
            "through the generic PM/NONPM generator. Register a Lane C generator "
            "adapter before retrying."
        )

    result = _lane_c_generator(request)
    if not isinstance(result, LaneCGenerationResult):
        raise TypeError("Lane C generator adapter must return LaneCGenerationResult")
    return result


__all__ = [
    "GenerationMetadataError",
    "GenerationPath",
    "GenerationRoutingError",
    "LaneCGenerationRequest",
    "LaneCGenerationResult",
    "LaneCGeneratorAdapter",
    "LaneCGeneratorNotRegistered",
    "clear_lane_c_generator",
    "dispatch_lane_c_generation",
    "lane_c_generator_registered",
    "read_generation_metadata",
    "register_lane_c_generator",
    "resolve_generation_path",
]
