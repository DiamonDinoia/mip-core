#!/usr/bin/env python3
"""
Reference package-variant selection helpers.

Linux currently publishes one manylinux_2_28 tier, so runtime selection only
needs to consider architecture and CPU level.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from build_targets import CPU_LEVEL_ORDER, CPU_LEVELS

try:
    import archspec.cpu as archspec_cpu
except ImportError:  # pragma: no cover - optional runtime dependency
    archspec_cpu = None


__all__ = [
    "CPU_LEVELS",
    "candidate_sort_key",
    "detect_host_cpu_level",
    "normalize_cpu_level",
    "select_best_variant",
]


def normalize_cpu_level(value: Any) -> str | None:
    """Normalize a CPU level to one of the canonical x86_64_v* values."""
    if value is None:
        return None

    text = str(value).strip().lower()
    aliases = {
        "v1": "x86_64_v1",
        "v2": "x86_64_v2",
        "v3": "x86_64_v3",
        "v4": "x86_64_v4",
    }
    if text in aliases:
        return aliases[text]

    if text in CPU_LEVELS:
        return text

    return None


def detect_host_cpu_level() -> str | None:
    """
    Detect the host CPU level from runtime microarchitecture probing.

    This prefers the existing `archspec` package rather than maintaining a
    feature table in this repository.
    """
    if archspec_cpu is None:
        return None

    try:
        host = archspec_cpu.host()
    except Exception:  # pragma: no cover - detection is best effort
        return None

    for cpu_level in reversed(CPU_LEVELS[1:]):
        target = archspec_cpu.TARGETS.get(cpu_level)
        if target is not None and host >= target:
            return cpu_level

    return CPU_LEVELS[0]


def _architecture_matches(candidate_architecture: Any, architecture: str) -> bool:
    candidate = str(candidate_architecture or "any").strip().lower()
    target = str(architecture or "").strip().lower()
    return candidate in {target, "any"}


def _candidate_cpu_level(candidate: Mapping[str, Any]) -> str | None:
    if "cpu_level" not in candidate or candidate.get("cpu_level") is None:
        return CPU_LEVELS[0]
    return normalize_cpu_level(candidate.get("cpu_level"))


def _candidate_specificity(candidate: Mapping[str, Any]) -> int:
    score = 0
    if str(candidate.get("architecture", "any")).strip().lower() != "any":
        score += 1
    if normalize_cpu_level(candidate.get("cpu_level")) is not None:
        score += 1
    return score


def _candidate_release_number(candidate: Mapping[str, Any]) -> int:
    try:
        return int(candidate.get("release_number", 0))
    except (TypeError, ValueError):
        return 0


def candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[int, int, int]:
    """Sort by CPU level, specificity, then release number."""
    cpu_level = _candidate_cpu_level(candidate)
    return (
        CPU_LEVEL_ORDER.get(cpu_level, 0),
        _candidate_specificity(candidate),
        _candidate_release_number(candidate),
    )


def select_best_variant(
    variants: Sequence[Mapping[str, Any]],
    *,
    architecture: str,
    host_cpu_level: Any = None,
) -> Mapping[str, Any] | None:
    """
    Select the best variant for the current machine.

    This keeps only matching architectures and then chooses the highest CPU
    level that does not exceed the host capability.
    """
    if host_cpu_level is None:
        host_cpu_level = detect_host_cpu_level()
    host_cpu = normalize_cpu_level(host_cpu_level) or CPU_LEVELS[0]
    host_cpu_rank = CPU_LEVEL_ORDER[host_cpu]

    matching: list[Mapping[str, Any]] = []
    for variant in variants:
        if not _architecture_matches(variant.get("architecture"), architecture):
            continue

        candidate_cpu = _candidate_cpu_level(variant)
        if candidate_cpu is None:
            continue
        if CPU_LEVEL_ORDER[candidate_cpu] > host_cpu_rank:
            continue

        matching.append(variant)

    if not matching:
        return None

    return max(matching, key=candidate_sort_key)
