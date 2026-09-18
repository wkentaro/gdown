"""
Collect dependencies from one or more `requirements.txt`-formatted files.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import IO

from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version
from pip_requirements_parser import (
    InstallRequirement,
    InvalidRequirementLine,
    RequirementsFile,
)

from pip_audit._dependency_source import (
    DependencyFixError,
    DependencySource,
    DependencySourceError,
    InvalidRequirementSpecifier,
)
from pip_audit._fix import ResolvedFixVersion
from pip_audit._service import Dependency
from pip_audit._service.interface import ResolvedDependency, SkippedDependency
from pip_audit._state import AuditState
from pip_audit._virtual_env import VirtualEnv, VirtualEnvError

logger = logging.getLogger(__name__)

PINNED_SPECIFIER_RE = re.compile(r"==(?P<version>.+?)$", re.VERBOSE)


class RequirementSource(DependencySource):
    """
    Wraps `requirements.txt` dependency resolution as a dependency source.
    """

    def __init__(
        self,
        filenames: list[Path],
        *,
        require_hashes: bool = False,
        no_deps: bool = False,
        disable_pip: bool = False,
        skip_editable: bool = False,
        index_url: str | None = None,
        extra_index_urls: list[str] = [],
        state: AuditState = AuditState(),
    ) -> None:
        """
        Create a new `RequirementSource`.

        `filenames` provides the list of filepaths to parse.

        `require_hashes` controls the hash policy: if `True`, dependency collection
        will fail unless all requirements include hashes.

        `disable_pip` controls the dependency resolution policy: if `True`,
        dependency resolution is not performed and the inputs are checked
        and treated as "frozen".

        `no_deps` controls whether dependency resolution can be disabled even without
        hashed requirements (which implies a fully resolved requirements file): if `True`,
        `disable_pip` is allowed without a hashed requirements file.

        `skip_editable` controls whether requirements marked as "editable" are skipped.
        By default, editable requirements are not skipped.

        `index_url` is the base URL of the package index.

        `extra_index_urls` are the extra URLs of package indexes.

        `state` is an `AuditState` to use for state callbacks.
        """
        self._filenames = filenames
        self._require_hashes = require_hashes
        self._no_deps = no_deps
        self._disable_pip = disable_pip
        self._skip_editable = skip_editable
        self._index_url = index_url
        self._extra_index_urls = extra_index_urls
        self.state = state
        self._dep_cache: dict[Path, set[Dependency]] = {}

    def collect(self) -> Iterator[Dependency]:
        """
        Collect all of the dependencies discovered by this `RequirementSource`.

        Raises a `RequirementSourceError` on any errors.
        """

        collect_files = []
        tmp_files = []
        try:
            for filename in self._filenames:
                # We need to handle process substitution inputs so we can invoke
                # `pip-audit` like so:
                #
                #   pip-audit -r <(echo 'something')
                #
                # Since `/dev/fd/<n>` inputs are unique to the parent process,
                # we can't pass these file names to `pip` and expect `pip` to
                # able to read them.
                #
                # In order to get around this, we're going to copy each input
                # into a corresponding temporary file and then pass that set of
                # files into `pip`.
                if filename.is_fifo():
                    # Deliberately pass `delete=False` so that our temporary
                    # file doesn't get automatically deleted on close. We need
                    # to close it so that `pip` can use it however, we
                    # obviously want it to persist.
                    tmp_file = NamedTemporaryFile(mode="w", delete=False)
                    with filename.open("r") as f:
                        shutil.copyfileobj(f, tmp_file)

                    # Close the file since it's going to get re-opened by `pip`.
                    tmp_file.close()
                    filename = Path(tmp_file.name)
                    tmp_files.append(filename)

                collect_files.append(filename)

            # Now pass the list of filenames into the rest of our logic.
            yield from self._collect_from_files(collect_files)
        finally:
            # Since we disabled automatically deletion for these temporary
            # files, we need to manually delete them on the way out.
            for t in tmp_files:
                t.unlink()

    def _collect_from_files(self, filenames: list[Path]) -> Iterator[Dependency]:
        # Figure out whether we have a fully resolved set of dependencies.
        reqs: list[InstallRequirement] = []
        require_hashes: bool = self._require_hashes
        for filename in filenames:
            rf = RequirementsFile.from_file(filename)
            if len(rf.invalid_lines) > 0:
                invalid = rf.invalid_lines[0]
                raise InvalidRequirementSpecifier(
                    f"requirement file {filename} contains invalid specifier at "
                    f"line {invalid.line_number}: {invalid.error_message}"
                )

            # If one or more requirements have a hash, this implies `--require-hashes`.
            require_hashes = require_hashes or any(req.hash_options for req in rf.requirements)
            reqs.extend(rf.requirements)

        # If the user has supplied `--no-deps` or there are hashed requirements, we should assume
        # that we have a fully resolved set of dependencies and we should waste time by invoking
        # `pip`.
        if self._disable_pip:
            if not self._no_deps and not require_hashes:
                raise RequirementSourceError(
                    "the --disable-pip flag can only be used with a hashed requirements files or "
                    "if the --no-deps flag has been provided"
                )
            yield from self._collect_preresolved_deps(iter(reqs), require_hashes)
            return

        ve_args = []
        if self._require_hashes:
            ve_args.append("--require-hashes")
        for filename in filenames:
            ve_args.extend(["-r", str(filename)])

        # Try to install the supplied requirements files.
        ve = VirtualEnv(ve_args, self._index_url, self._extra_index_urls, self.state)
        try:
            with TemporaryDirectory() as ve_dir:
                ve.create(ve_dir)
        except VirtualEnvError as exc:
            raise RequirementSourceError(str(exc)) from exc

        # Now query the installed packages.
        for name, version in ve.installed_packages:
            yield ResolvedDependency(name=name, version=version)

    def fix(self, fix_version: ResolvedFixVersion) -> None:
        """
        Fixes a dependency version for this `RequirementSource`.
        """
        with ExitStack() as stack:
            # Make temporary copies of the existing requirements files. If anything goes wrong, we
            # want to copy them back into place and undo any partial application of the fix.
            tmp_files: list[IO[str]] = [
                stack.enter_context(NamedTemporaryFile(mode="r+")) for _ in self._filenames
            ]
            for filename, tmp_file in zip(self._filenames, tmp_files, strict=True):
                with filename.open("r") as f:
                    shutil.copyfileobj(f, tmp_file)

            try:
                # Now fix the files inplace
                for filename in self._filenames:
                    self.state.update_state(
                        f"Fixing dependency {fix_version.dep.name} ({fix_version.dep.version} => "
                        f"{fix_version.version})"
                    )
                    self._fix_file(filename, fix_version)
            except Exception as e:
                logger.warning(
                    f"encountered an exception while applying fixes, recovering original files: {e}"
                )
                self._recover_files(tmp_files)
                raise e

    def _fix_file(self, filename: Path, fix_version: ResolvedFixVersion) -> None:
        # Reparse the requirements file. We want to rewrite each line to the new requirements file
        # and only modify the lines that we're fixing.
        #
        # This time we're using the `RequirementsFile.parse` API instead of `Requirements.from_file`
        # since we want to access each line sequentially in order to rewrite the file.
        reqs = list(RequirementsFile.parse(filename=filename.as_posix()))

        # Check ahead of time for anything invalid in the requirements file since we don't want to
        # encounter this while writing out the file. Check for duplicate requirements and lines that
        # failed to parse.
        req_specifiers: dict[str, SpecifierSet] = {}

        for req in reqs:
            if (
                isinstance(req, InstallRequirement)
                and (req.marker is None or req.marker.evaluate())
                and req.req is not None
            ):
                duplicate_req_specifier = req_specifiers.get(req.name)

                if not duplicate_req_specifier:
                    req_specifiers[req.name] = req.specifier

                elif duplicate_req_specifier != req.specifier:
                    raise RequirementFixError(
                        f"package {req.name} has duplicate requirements: {str(req)}"
                    )
            elif isinstance(req, InvalidRequirementLine):
                raise RequirementFixError(
                    f"requirement file {filename} has invalid requirement: {str(req)}"
                )

        # Now write out the new requirements file
        with filename.open("w") as f:
            found = False
            for req in reqs:
                if (
                    isinstance(req, InstallRequirement)
                    and canonicalize_name(req.name) == fix_version.dep.canonical_name
                ):
                    found = True
                    if req.specifier.contains(
                        fix_version.dep.version
                    ) and not req.specifier.contains(fix_version.version):
                        req.req.specifier = SpecifierSet(f"=={fix_version.version}")
                print(req.dumps(), file=f)

            # The vulnerable dependency may not be explicitly listed in the requirements file if it
            # is a subdependency of a requirement. In this case, we should explicitly add the fixed
            # dependency into the requirements file.
            #
            # To know whether this is the case, we'll need to resolve dependencies if we haven't
            # already in order to figure out whether this subdependency belongs to this file or
            # another.
            if not found:
                logger.warning(
                    "added fixed subdependency explicitly to requirements file "
                    f"{filename}: {fix_version.dep.canonical_name}"
                )
                print(
                    "    # pip-audit: subdependency explicitly fixed",
                    file=f,
                )
                print(f"{fix_version.dep.canonical_name}=={fix_version.version}", file=f)

    def _recover_files(self, tmp_files: list[IO[str]]) -> None:
        for filename, tmp_file in zip(self._filenames, tmp_files, strict=True):
            try:
                tmp_file.seek(0)
                with filename.open("w") as f:
                    shutil.copyfileobj(tmp_file, f)
            except Exception as e:  # noqa: PERF203
                # Not much we can do at this point since we're already handling an exception. Just
                # log the error and try to recover the rest of the files.
                logger.warning(f"encountered an exception during file recovery: {e}")
                continue

    def _collect_preresolved_deps(
        self, reqs: Iterator[InstallRequirement], require_hashes: bool
    ) -> Iterator[Dependency]:
        """
        Collect pre-resolved (pinned) dependencies.
        """
        req_specifiers: dict[str, SpecifierSet] = {}
        for req in reqs:
            if not req.hash_options and require_hashes:
                raise RequirementSourceError(f"requirement {req.dumps()} does not contain a hash")
            if req.req is None:
                # PEP 508-style URL requirements don't have a pre-declared version, even
                # when hashed; the `#egg=name==version` syntax is non-standard and not supported
                # by `pip` itself.
                #
                # In this case, we can't audit the dependency so we should signal to the
                # caller that we're skipping it.
                yield SkippedDependency(
                    name=req.requirement_line.line,
                    skip_reason="could not deduce package version from URL requirement",
                )
                continue
            if self._skip_editable and req.is_editable:
                yield SkippedDependency(name=req.name, skip_reason="requirement marked as editable")
            if req.marker is not None and not req.marker.evaluate():
                # TODO(ww): Remove this `no cover` pragma once we're 3.10+.
                # See: https://github.com/nedbat/coveragepy/issues/198
                continue  # pragma: no cover

            duplicate_req_specifier = req_specifiers.get(req.name)

            if not duplicate_req_specifier:
                req_specifiers[req.name] = req.specifier

            # We have a duplicate requirement for the same package
            # but different specifiers, meaning a badly resolved requirements.txt
            elif duplicate_req_specifier != req.specifier:
                raise RequirementSourceError(
                    f"package {req.name} has duplicate requirements: {str(req)}"
                )
            else:
                # We have a duplicate requirement for the same package and the specifier matches
                # As they would return the same result from the audit, there no need to yield it a second time.
                continue  # pragma: no cover

            # NOTE: URL dependencies cannot be pinned, so skipping them
            # makes sense (under the same principle of skipping dependencies
            # that can't be found on PyPI). This is also consistent with
            # what `pip --no-deps` does (installs the URL dependency, but
            # not any subdependencies).
            if req.is_url:
                yield SkippedDependency(
                    name=req.name,
                    skip_reason="URL requirements cannot be pinned to a specific package version",
                )
            elif not req.specifier:
                raise RequirementSourceError(f"requirement {req.name} is not pinned: {str(req)}")
            else:
                pinned_specifier = PINNED_SPECIFIER_RE.match(str(req.specifier))
                if pinned_specifier is None:
                    raise RequirementSourceError(
                        f"requirement {req.name} is not pinned to an exact version: {str(req)}"
                    )

                yield ResolvedDependency(req.name, Version(pinned_specifier.group("version")))


class RequirementSourceError(DependencySourceError):
    """A requirements-parsing specific `DependencySourceError`."""

    pass


class RequirementFixError(DependencyFixError):
    """A requirements-fixing specific `DependencyFixError`."""

    pass
