#!/usr/bin/env python3
"""
Helpers for concrete build target selection and metadata.

The build pipeline prepares one concrete target per job. Jobs select targets
through environment variables such as BUILD_ARCHITECTURE and BUILD_CPU_LEVEL.
This module keeps the matching and metadata rules in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


CPU_LEVELS = (
    "x86_64_v1",
    "x86_64_v2",
    "x86_64_v3",
    "x86_64_v4",
)

CPU_LEVEL_ORDER = {cpu_level: index for index, cpu_level in enumerate(CPU_LEVELS, start=1)}
BASELINE_CPU_LEVEL = CPU_LEVELS[0]
LTO_FLAG_GCC = "-flto=auto"
LTO_FLAG_MSVC = "/GL"
LTO_LINK_FLAG_MSVC = "/LTCG"

# Representative microarchitectures for tuning within each ISA level.
LINUX_X86_64_CPU_PROFILES = {
    "x86_64_v1": {
        "march": "x86-64",
        "mtune": "generic",
    },
    "x86_64_v2": {
        "march": "x86-64-v2",
        "mtune": "nehalem",
    },
    "x86_64_v3": {
        "march": "x86-64-v3",
        "mtune": "haswell",
    },
    "x86_64_v4": {
        "march": "x86-64-v4",
        "mtune": "skylake-avx512",
    },
}

WINDOWS_X86_64_CPU_PROFILES = {
    "x86_64_v1": {
        "arch_flag": "/arch:SSE2",
        "favor_flag": "/favor:blend",
    },
    "x86_64_v2": {
        "arch_flag": "/arch:SSE4.2",
        "favor_flag": "/favor:blend",
    },
    "x86_64_v3": {
        "arch_flag": "/arch:AVX2",
        "favor_flag": "/favor:blend",
    },
    "x86_64_v4": {
        "arch_flag": "/arch:AVX512",
        "favor_flag": "/favor:blend",
    },
}


@dataclass(frozen=True)
class BuildContext:
    architecture: str
    cpu_level: Optional[str]
    matlab_release: Optional[str]
    compiler_family: Optional[str]
    compiler_version: Optional[str]
    cmake_generator: Optional[str]
    cmake_build_program: Optional[str]


def get_build_context_from_env() -> BuildContext:
    """Read the concrete target requested by the current job."""
    architecture = os.environ.get("BUILD_ARCHITECTURE", "any")
    cpu_level = _strip_or_none(os.environ.get("BUILD_CPU_LEVEL"))
    if cpu_level is not None and cpu_level not in CPU_LEVELS:
        raise ValueError(f"Unsupported BUILD_CPU_LEVEL: {cpu_level}")
    matlab_release = _strip_or_none(os.environ.get("BUILD_MATLAB_RELEASE"))
    compiler_family = _strip_or_none(os.environ.get("BUILD_COMPILER_FAMILY"))
    compiler_version = _strip_or_none(os.environ.get("BUILD_COMPILER_VERSION"))
    cmake_generator = _strip_or_none(os.environ.get("BUILD_CMAKE_GENERATOR"))
    cmake_build_program = _strip_or_none(os.environ.get("BUILD_CMAKE_BUILD_PROGRAM"))
    return BuildContext(
        architecture=architecture,
        cpu_level=cpu_level,
        matlab_release=matlab_release,
        compiler_family=compiler_family,
        compiler_version=compiler_version,
        cmake_generator=cmake_generator,
        cmake_build_program=cmake_build_program,
    )


def resolve_build_architecture(build: Dict[str, Any], context: BuildContext) -> Optional[str]:
    """
    Return the concrete architecture tag to emit for a build entry, or None if
    the entry does not match the current job context.

    Generic `architectures: [any]` packages continue to build on the Linux
    baseline CPU leg so pure-MATLAB packages are still published once.
    """
    architectures = build.get("architectures", [])
    matched_architecture: Optional[str] = None

    if context.architecture in architectures:
        matched_architecture = context.architecture
    elif "any" in architectures and _should_build_generic_linux_package(context):
        matched_architecture = "any"
    else:
        return None

    selected_cpu_level = None if matched_architecture == "any" else context.cpu_level
    if not _match_optional_dimension(build.get("cpu_levels"), selected_cpu_level):
        return None

    return matched_architecture


def get_variant_metadata(
    matched_architecture: str,
    context: BuildContext,
    resolved_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build metadata for the selected concrete variant."""
    metadata: Dict[str, Any] = {
        "architecture": matched_architecture,
    }
    compiler_env: Dict[str, str] = {}
    compiler_flags: Dict[str, str] = {}
    compiler_family = resolved_config.get("compiler_family") or context.compiler_family
    compiler_version = resolved_config.get("compiler_version") or context.compiler_version
    matlab_release = resolved_config.get("matlab_release") or context.matlab_release

    if matched_architecture == "linux_x86_64" and context.cpu_level:
        if context.cpu_level not in CPU_LEVELS:
            raise ValueError(f"Unsupported cpu_level for linux_x86_64: {context.cpu_level}")
        metadata["cpu_level"] = context.cpu_level
        profile = LINUX_X86_64_CPU_PROFILES[context.cpu_level]
        march = str(profile["march"])
        base_flags = f"-march={march} -mtune={profile['mtune']} {LTO_FLAG_GCC}"
        compiler_flags = {
            "march": march,
            "mtune": profile["mtune"],
            "cflags": base_flags,
            "cxxflags": base_flags,
            "fflags": base_flags,
            "ldflags": LTO_FLAG_GCC,
        }
        compiler_env.update(
            {
                "MIP_CPU_LEVEL": context.cpu_level,
                "MIP_MARCH": march,
                "MIP_MTUNE": profile["mtune"],
                "MIP_CFLAGS": compiler_flags["cflags"],
                "MIP_CXXFLAGS": compiler_flags["cxxflags"],
                "MIP_FFLAGS": compiler_flags["fflags"],
                "MIP_LDFLAGS": compiler_flags["ldflags"],
            }
        )

    if matched_architecture == "windows_x86_64" and context.cpu_level:
        if context.cpu_level not in CPU_LEVELS:
            raise ValueError(f"Unsupported cpu_level for windows_x86_64: {context.cpu_level}")
        metadata["cpu_level"] = context.cpu_level
        profile = WINDOWS_X86_64_CPU_PROFILES[context.cpu_level]
        compiler_flags = {
            "arch_flag": profile["arch_flag"],
            "favor_flag": profile["favor_flag"],
            "cl_flags": f"{profile['arch_flag']} {profile['favor_flag']} {LTO_FLAG_MSVC}".strip(),
            "link_flags": LTO_LINK_FLAG_MSVC,
        }
        compiler_env.update(
            {
                "MIP_CPU_LEVEL": context.cpu_level,
                "MIP_CL_FLAGS": compiler_flags["cl_flags"],
                "MIP_LINK_FLAGS": compiler_flags["link_flags"],
            }
        )

    if compiler_family is None:
        if matched_architecture.startswith("windows_") and context.cpu_level:
            compiler_family = "msvc"
        elif matched_architecture.startswith("linux_") and context.cpu_level:
            compiler_family = "gcc"

    if compiler_family:
        metadata["compiler_family"] = compiler_family
    if compiler_version:
        metadata["compiler_version"] = compiler_version
    if matlab_release:
        metadata["matlab_release"] = matlab_release
    if context.cmake_generator:
        compiler_env["MIP_CMAKE_GENERATOR"] = context.cmake_generator
    if context.cmake_build_program:
        compiler_env["MIP_CMAKE_BUILD_PROGRAM"] = context.cmake_build_program
    if compiler_env:
        override_env = resolved_config.get("compiler_env", {})
        compiler_env.update({k: str(v) for k, v in override_env.items()})
        metadata["compiler_env"] = compiler_env
    if compiler_flags:
        override_flags = resolved_config.get("compiler_flags", {})
        compiler_flags.update({k: str(v) for k, v in override_flags.items()})
        metadata["compiler_flags"] = compiler_flags

    return metadata


def build_mhl_filename(package_data: Dict[str, Any], variant_metadata: Dict[str, Any]) -> str:
    """Generate the .mhl filename for a concrete build variant."""
    segments = [
        package_data["name"],
        package_data["version"],
        variant_metadata["architecture"],
    ]
    cpu_level = variant_metadata.get("cpu_level")
    if cpu_level:
        segments.append(cpu_level)
    return "-".join(segments) + ".mhl"


def _match_optional_dimension(allowed_values: Any, selected_value: Optional[str]) -> bool:
    if selected_value is None:
        return allowed_values in (None, [], ())
    if not allowed_values:
        return False
    return selected_value in allowed_values


def _should_build_generic_linux_package(context: BuildContext) -> bool:
    return context.architecture == "linux_x86_64" and context.cpu_level in (None, BASELINE_CPU_LEVEL)


def _strip_or_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None
