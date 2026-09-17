"""
Functionality for resolving fixed versions of dependencies.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

from packaging.version import Version

from pip_audit._service import (
    Dependency,
    ResolvedDependency,
    VulnerabilityResult,
    VulnerabilityService,
)
from pip_audit._state import AuditState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FixVersion:
    """
    Represents an abstract dependency fix version.

    This class cannot be constructed directly.
    """

    dep: ResolvedDependency

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
        """
        A stub constructor that always fails.
        """
        raise NotImplementedError

    def is_skipped(self) -> bool:
        """
        Check whether the `FixVersion` was unable to be resolved.
        """
        return self.__class__ is SkippedFixVersion


@dataclass(frozen=True)
class ResolvedFixVersion(FixVersion):
    """
    Represents a resolved fix version.
    """

    version: Version


@dataclass(frozen=True)
class SkippedFixVersion(FixVersion):
    """
    Represents a fix version that was unable to be resolved and therefore, skipped.
    """

    skip_reason: str


def resolve_fix_versions(
    service: VulnerabilityService,
    result: dict[Dependency, list[VulnerabilityResult]],
    state: AuditState = AuditState(),
) -> Iterator[FixVersion]:
    """
    Resolves a mapping of dependencies to known vulnerabilities to a series of fix versions without
    known vulnerabilities.
    """
    for dep, vulns in result.items():
        if dep.is_skipped():
            continue
        if not vulns:
            continue
        dep = cast(ResolvedDependency, dep)
        try:
            version = _resolve_fix_version(service, dep, vulns, state)
            yield ResolvedFixVersion(dep, version)
        except FixResolutionImpossible as fri:
            skip_reason = str(fri)
            logger.debug(skip_reason)
            yield SkippedFixVersion(dep, skip_reason)


def _resolve_fix_version(
    service: VulnerabilityService,
    dep: ResolvedDependency,
    vulns: list[VulnerabilityResult],
    state: AuditState,
) -> Version:
    # We need to upgrade to a fix version that satisfies all vulnerability results
    #
    # However, whenever we upgrade a dependency, we run the risk of introducing new vulnerabilities
    # so we need to run this in a loop and continue polling the vulnerability service on each
    # prospective resolved fix version
    current_version = dep.version
    current_vulns = vulns
    while current_vulns:
        state.update_state(f"Resolving fix version for {dep.name}, checking {current_version}")

        def get_earliest_fix_version(d: ResolvedDependency, v: VulnerabilityResult) -> Version:
            for fix_version in v.fix_versions:
                if fix_version > current_version:
                    return fix_version
            raise FixResolutionImpossible(
                f"failed to fix dependency {dep.name} ({dep.version}), unable to find fix version "
                f"for vulnerability {v.id}"
            )

        # We want to retrieve a version that potentially fixes all vulnerabilities
        current_version = max([get_earliest_fix_version(dep, v) for v in current_vulns])
        _, current_vulns = service.query(ResolvedDependency(dep.name, current_version))
    return current_version


class FixResolutionImpossible(Exception):
    """
    Raised when `resolve_fix_versions` fails to find a fix version without known vulnerabilities
    """

    pass
