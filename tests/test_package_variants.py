#!/usr/bin/env python3
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import package_variants as pv  # noqa: E402


def test_selects_best_linux_variant_by_cpu_level():
    variants = [
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v1"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v2"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v4"},
    ]

    selected = pv.select_best_variant(
        variants,
        architecture="linux_x86_64",
        host_cpu_level="x86_64_v4",
    )

    assert selected["cpu_level"] == "x86_64_v4"


def test_more_specific_variant_wins_ties_over_legacy_generic_artifact():
    variants = [
        {"name": "pkg", "architecture": "linux_x86_64", "release_number": 9},
        {
            "name": "pkg",
            "architecture": "linux_x86_64",
            "cpu_level": "x86_64_v1",
            "release_number": 10,
        },
    ]

    selected = pv.select_best_variant(
        variants,
        architecture="linux_x86_64",
        host_cpu_level="x86_64_v1",
    )

    assert selected["release_number"] == 10


def test_windows_and_linux_share_the_same_cpu_level_ordering():
    linux_variants = [
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v1"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v3"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v4"},
    ]
    windows_variants = [
        {"name": "pkg", "architecture": "windows_x86_64", "cpu_level": "x86_64_v1"},
        {"name": "pkg", "architecture": "windows_x86_64", "cpu_level": "x86_64_v3"},
        {"name": "pkg", "architecture": "windows_x86_64", "cpu_level": "x86_64_v4"},
    ]

    linux_selected = pv.select_best_variant(
        linux_variants,
        architecture="linux_x86_64",
        host_cpu_level="x86_64_v4",
    )
    windows_selected = pv.select_best_variant(
        windows_variants,
        architecture="windows_x86_64",
        host_cpu_level="x86_64_v4",
    )

    assert linux_selected["cpu_level"] == "x86_64_v4"
    assert windows_selected["cpu_level"] == "x86_64_v4"


def test_architecture_any_is_treated_as_a_wildcard():
    variants = [
        {"name": "pkg", "architecture": "any", "cpu_level": "x86_64_v1"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v2"},
    ]

    selected = pv.select_best_variant(
        variants,
        architecture="linux_x86_64",
        host_cpu_level="x86_64_v2",
    )

    assert selected["architecture"] == "linux_x86_64"
    assert selected["cpu_level"] == "x86_64_v2"


def test_missing_cpu_level_defaults_to_baseline():
    variants = [
        {"name": "pkg", "architecture": "linux_x86_64"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v2"},
    ]

    selected = pv.select_best_variant(
        variants,
        architecture="linux_x86_64",
        host_cpu_level="x86_64_v1",
    )

    assert selected.get("cpu_level") is None


def test_unknown_cpu_level_is_rejected():
    variants = [
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "future_tier"},
        {"name": "pkg", "architecture": "linux_x86_64", "cpu_level": "x86_64_v2"},
    ]

    selected = pv.select_best_variant(
        variants,
        architecture="linux_x86_64",
        host_cpu_level="x86_64_v1",
    )

    assert selected is None


def test_detect_host_cpu_level_returns_none_without_archspec(monkeypatch):
    monkeypatch.setattr(pv, "archspec_cpu", None)
    assert pv.detect_host_cpu_level() is None


def test_detect_host_cpu_level_uses_archspec_tiers(monkeypatch):
    class FakeMicroarchitecture:
        def __init__(self, rank):
            self.rank = rank

        def __ge__(self, other):
            return self.rank >= other.rank

    monkeypatch.setattr(
        pv,
        "archspec_cpu",
        SimpleNamespace(
            host=lambda: FakeMicroarchitecture(3),
            TARGETS={
                "x86_64_v2": FakeMicroarchitecture(2),
                "x86_64_v3": FakeMicroarchitecture(3),
                "x86_64_v4": FakeMicroarchitecture(4),
            },
        ),
    )

    assert pv.detect_host_cpu_level() == "x86_64_v3"
