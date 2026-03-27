#!/usr/bin/env python3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_targets as bt  # noqa: E402


def make_context() -> bt.BuildContext:
    return bt.BuildContext(
        architecture="linux_x86_64",
        cpu_level="x86_64_v4",
        matlab_release="R2022a",
        compiler_family="gcc",
        compiler_version="14",
        cmake_generator="Ninja",
        cmake_build_program="ninja",
    )


def test_linux_variants_use_psabi_cpu_level_march_names():
    metadata = bt.get_variant_metadata("linux_x86_64", make_context(), {})

    assert metadata["cpu_level"] == "x86_64_v4"
    assert metadata["compiler_flags"]["march"] == "x86-64-v4"
    assert "-flto=auto" in metadata["compiler_flags"]["cflags"]
    assert metadata["compiler_flags"]["ldflags"] == "-flto=auto"


def test_windows_v2_uses_a_valid_msvc_arch_flag():
    context = bt.BuildContext(
        architecture="windows_x86_64",
        cpu_level="x86_64_v2",
        matlab_release="R2022a",
        compiler_family="msvc",
        compiler_version="v143",
        cmake_generator="Ninja",
        cmake_build_program="ninja",
    )

    metadata = bt.get_variant_metadata("windows_x86_64", context, {})

    assert metadata["cpu_level"] == "x86_64_v2"
    assert metadata["compiler_flags"]["arch_flag"] == "/arch:SSE4.2"
    assert "/GL" in metadata["compiler_flags"]["cl_flags"]
    assert metadata["compiler_flags"]["link_flags"] == "/LTCG"


def test_linux_filename_uses_cpu_level_suffix():
    filename = bt.build_mhl_filename(
        {"name": "pkg", "version": "1.0.0"},
        {"architecture": "linux_x86_64", "cpu_level": "x86_64_v3"},
    )

    assert filename == "pkg-1.0.0-linux_x86_64-x86_64_v3.mhl"


def test_invalid_build_cpu_level_raises_clear_error(monkeypatch):
    monkeypatch.setenv("BUILD_CPU_LEVEL", "future_tier")

    with pytest.raises(ValueError, match="Unsupported BUILD_CPU_LEVEL"):
        bt.get_build_context_from_env()


def test_generic_linux_package_matches_baseline_cpu_leg():
    build = {"architectures": ["any"]}
    context = bt.BuildContext(
        architecture="linux_x86_64",
        cpu_level="x86_64_v1",
        matlab_release=None,
        compiler_family=None,
        compiler_version=None,
        cmake_generator=None,
        cmake_build_program=None,
    )

    assert bt.resolve_build_architecture(build, context) == "any"


def test_generic_linux_package_does_not_match_higher_cpu_legs():
    build = {"architectures": ["any"]}
    context = bt.BuildContext(
        architecture="linux_x86_64",
        cpu_level="x86_64_v3",
        matlab_release=None,
        compiler_family=None,
        compiler_version=None,
        cmake_generator=None,
        cmake_build_program=None,
    )

    assert bt.resolve_build_architecture(build, context) is None
