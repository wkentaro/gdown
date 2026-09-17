"""
Collect dependencies from `pylock.toml` files.
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import tomli
from packaging.version import Version

from pip_audit._dependency_source import DependencyFixError, DependencySource, DependencySourceError
from pip_audit._fix import ResolvedFixVersion
from pip_audit._service import Dependency, ResolvedDependency
from pip_audit._service.interface import SkippedDependency

logger = logging.getLogger(__name__)


class PyLockSource(DependencySource):
    """
    Wraps `pylock.*.toml` dependency collection as a dependency source.
    """

    def __init__(self, filenames: list[Path]) -> None:
        """
        Create a new `PyLockSource`.

        `filenames` provides a list of `pylock.*.toml` files to parse.
        """

        self._filenames = filenames

    def collect(self) -> Iterator[Dependency]:
        """
        Collect all of the dependencies discovered by this `PyLockSource`.

        Raises a `PyLockSourceError` on any errors.
        """
        for filename in self._filenames:
            yield from self._collect_from_file(filename)

    def _collect_from_file(self, filename: Path) -> Iterator[Dependency]:
        """
        Collect dependencies from a single `pylock.*.toml` file.

        Raises a `PyLockSourceError` on any errors.
        """
        try:
            with filename.open(mode="rb") as f:
                pylock = tomli.load(f)
        except tomli.TOMLDecodeError as e:
            raise PyLockSourceError(f"{filename}: invalid TOML in lockfile") from e

        lock_version = pylock.get("lock-version")
        if not lock_version:
            raise PyLockSourceError(f"{filename}: missing lock-version in lockfile")

        lock_version = Version(lock_version)
        if lock_version.major != 1:
            raise PyLockSourceError(f"{filename}: lockfile version {lock_version} is not supported")

        packages = pylock.get("packages")
        if not packages:
            raise PyLockSourceError(f"{filename}: missing packages in lockfile")

        try:
            yield from self._collect_from_packages(packages)
        except PyLockSourceError as e:
            raise PyLockSourceError(f"{filename}: {e}") from e

    def _collect_from_packages(self, packages: list[dict]) -> Iterator[Dependency]:
        """
        Collect dependencies from a list of packages.

        Raises a `PyLockSourceError` on any errors.
        """
        for idx, package in enumerate(packages):
            name = package.get("name")
            if not name:
                raise PyLockSourceError(f"invalid package #{idx}: no name")

            version = package.get("version")
            if version:
                yield ResolvedDependency(name, Version(version))
            else:
                # Versions are optional in PEP 751, e.g. for source tree specifiers.
                # We mark these as skipped.
                yield SkippedDependency(name, "no version specified")

    def fix(self, fix_version: ResolvedFixVersion) -> None:  # pragma: no cover
        """
        Raises `NotImplementedError` if called.

        We don't support fixing dependencies in lockfiles, since
        lockfiles should be managed/updated by their packaging tool.
        """

        raise NotImplementedError(
            "lockfiles cannot be fixed directly; use your packaging tool to perform upgrades"
        )


class PyLockSourceError(DependencySourceError):
    """A pylock-parsing specific `DependencySourceError`."""

    pass


class PyLockFixError(DependencyFixError):
    """A pylock-fizing specific `DependencyFixError`."""

    pass
