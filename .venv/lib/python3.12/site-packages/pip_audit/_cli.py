"""
Command-line entrypoints for `pip-audit`.
"""

from __future__ import annotations

import argparse
import enum
import logging
import os
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import IO, NoReturn, cast

from pip_audit import __version__
from pip_audit._audit import AuditOptions, Auditor
from pip_audit._dependency_source import (
    DependencySource,
    DependencySourceError,
    PipSource,
    PyProjectSource,
    RequirementSource,
)
from pip_audit._dependency_source.pylock import PyLockSource
from pip_audit._fix import ResolvedFixVersion, SkippedFixVersion, resolve_fix_versions
from pip_audit._format import (
    ColumnsFormat,
    CycloneDxFormat,
    JsonFormat,
    MarkdownFormat,
    VulnerabilityFormat,
)
from pip_audit._service import EcosystemsService, OsvService, PyPIService
from pip_audit._service.interface import ConnectionError as VulnServiceConnectionError
from pip_audit._service.interface import (
    Dependency,
    ResolvedDependency,
    SkippedDependency,
    VulnerabilityResult,
    VulnerabilityService,
)
from pip_audit._state import AuditSpinner, AuditState
from pip_audit._util import assert_never

logging.basicConfig()
logger = logging.getLogger(__name__)

# NOTE: We configure the top package logger, rather than the root logger,
# to avoid overly verbose logging in third-party code by default.
package_logger = logging.getLogger("pip_audit")
package_logger.setLevel(os.environ.get("PIP_AUDIT_LOGLEVEL", "INFO").upper())


@contextmanager
def _output_io(name: Path) -> Iterator[IO[str]]:  # pragma: no cover
    """
    A context managing wrapper for pip-audit's `--output` flag. This allows us
    to avoid `argparse.FileType`'s "eager" file creation, which is generally
    the wrong/unexpected behavior when dealing with fallible processes.
    """
    if str(name) in {"stdout", "-"}:
        yield sys.stdout
    else:
        with name.open("w") as io:
            yield io


@enum.unique
class OutputFormatChoice(str, enum.Enum):
    """
    Output formats supported by the `pip-audit` CLI.
    """

    Columns = "columns"
    Json = "json"
    CycloneDxJson = "cyclonedx-json"
    CycloneDxXml = "cyclonedx-xml"
    Markdown = "markdown"

    def to_format(self, output_desc: bool, output_aliases: bool) -> VulnerabilityFormat:
        if self is OutputFormatChoice.Columns:
            return ColumnsFormat(output_desc, output_aliases)
        elif self is OutputFormatChoice.Json:
            return JsonFormat(output_desc, output_aliases)
        elif self is OutputFormatChoice.CycloneDxJson:
            return CycloneDxFormat(inner_format=CycloneDxFormat.InnerFormat.Json)
        elif self is OutputFormatChoice.CycloneDxXml:
            return CycloneDxFormat(inner_format=CycloneDxFormat.InnerFormat.Xml)
        elif self is OutputFormatChoice.Markdown:
            return MarkdownFormat(output_desc, output_aliases)
        else:
            assert_never(self)  # pragma: no cover

    def __str__(self) -> str:
        return self.value


@enum.unique
class VulnerabilityServiceChoice(str, enum.Enum):
    """
    Python vulnerability services supported by `pip-audit`.
    """

    Osv = "osv"
    Pypi = "pypi"
    Esms = "esms"

    def __str__(self) -> str:
        return self.value


@enum.unique
class VulnerabilityDescriptionChoice(str, enum.Enum):
    """
    Whether or not vulnerability descriptions should be added to the `pip-audit` output.
    """

    On = "on"
    Off = "off"
    Auto = "auto"

    def to_bool(self, format_: OutputFormatChoice) -> bool:
        if self is VulnerabilityDescriptionChoice.On:
            return True
        elif self is VulnerabilityDescriptionChoice.Off:
            return False
        elif self is VulnerabilityDescriptionChoice.Auto:
            return bool(format_ is OutputFormatChoice.Json)
        else:
            assert_never(self)  # pragma: no cover

    def __str__(self) -> str:
        return self.value


@enum.unique
class VulnerabilityAliasChoice(str, enum.Enum):
    """
    Whether or not vulnerability aliases should be added to the `pip-audit` output.
    """

    On = "on"
    Off = "off"
    Auto = "auto"

    def to_bool(self, format_: OutputFormatChoice) -> bool:
        if self is VulnerabilityAliasChoice.On:
            return True
        elif self is VulnerabilityAliasChoice.Off:
            return False
        elif self is VulnerabilityAliasChoice.Auto:
            return bool(format_ is OutputFormatChoice.Json)
        else:
            assert_never(self)  # pragma: no cover

    def __str__(self) -> str:
        return self.value


@enum.unique
class ProgressSpinnerChoice(str, enum.Enum):
    """
    Whether or not `pip-audit` should display a progress spinner.
    """

    On = "on"
    Off = "off"

    def __bool__(self) -> bool:
        return self is ProgressSpinnerChoice.On

    def __str__(self) -> str:
        return self.value


def _enum_help(msg: str, e: type[enum.Enum]) -> str:  # pragma: no cover
    """
    Render a `--help`-style string for the given enumeration.
    """
    return f"{msg} (choices: {', '.join(str(v) for v in e)})"


def _fatal(msg: str) -> NoReturn:  # pragma: no cover
    """
    Log a fatal error to the standard error stream and exit.
    """
    # NOTE: We buffer the logger when the progress spinner is active,
    # ensuring that the fatal message is formatted on its own line.
    logger.error(msg)
    sys.exit(1)


def _parser() -> argparse.ArgumentParser:  # pragma: no cover
    parser = argparse.ArgumentParser(
        prog="pip-audit",
        description="audit the Python environment for dependencies with known vulnerabilities",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    dep_source_args = parser.add_mutually_exclusive_group()
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="show only results for dependencies in the local environment",
    )
    dep_source_args.add_argument(
        "-r",
        "--requirement",
        type=Path,
        metavar="REQUIREMENT",
        action="append",
        dest="requirements",
        help="audit the given requirements file; this option can be used multiple times",
    )
    dep_source_args.add_argument(
        "project_path",
        type=Path,
        nargs="?",
        help="audit a local Python project at the given path",
    )
    parser.add_argument(
        "--locked",
        action="store_true",
        help="audit lock files from the local Python project. This "
        "flag only applies to auditing from project paths",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=OutputFormatChoice,
        choices=OutputFormatChoice,
        default=os.environ.get("PIP_AUDIT_FORMAT", OutputFormatChoice.Columns),
        metavar="FORMAT",
        help=_enum_help("the format to emit audit results in", OutputFormatChoice),
    )
    parser.add_argument(
        "-s",
        "--vulnerability-service",
        type=VulnerabilityServiceChoice,
        choices=VulnerabilityServiceChoice,
        default=os.environ.get("PIP_AUDIT_VULNERABILITY_SERVICE", VulnerabilityServiceChoice.Pypi),
        metavar="SERVICE",
        help=_enum_help(
            "the vulnerability service to audit dependencies against",
            VulnerabilityServiceChoice,
        ),
    )
    parser.add_argument(
        "--osv-url",
        type=str,
        metavar="OSV_URL",
        dest="osv_url",
        default=os.environ.get("PIP_AUDIT_OSV_URL", OsvService.DEFAULT_OSV_URL),
        help="URL to use for the OSV API instead of the default",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="without `--fix`: collect all dependencies but do not perform the auditing step; "
        "with `--fix`: perform the auditing step but do not perform any fixes",
    )
    parser.add_argument(
        "-S",
        "--strict",
        action="store_true",
        help="fail the entire audit if dependency collection fails on any dependency",
    )
    parser.add_argument(
        "--desc",
        type=VulnerabilityDescriptionChoice,
        choices=VulnerabilityDescriptionChoice,
        nargs="?",
        const=VulnerabilityDescriptionChoice.On,
        default=os.environ.get("PIP_AUDIT_DESC", VulnerabilityDescriptionChoice.Auto),
        help="include a description for each vulnerability; "
        "`auto` defaults to `on` for the `json` format. This flag has no "
        "effect on the `cyclonedx-json` or `cyclonedx-xml` formats.",
    )
    parser.add_argument(
        "--aliases",
        type=VulnerabilityAliasChoice,
        choices=VulnerabilityAliasChoice,
        nargs="?",
        const=VulnerabilityAliasChoice.On,
        default=VulnerabilityAliasChoice.Auto,
        help="includes alias IDs for each vulnerability; "
        "`auto` defaults to `on` for the `json` format. This flag has no "
        "effect on the `cyclonedx-json` or `cyclonedx-xml` formats.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="the directory to use as an HTTP cache for PyPI; uses the `pip` HTTP cache by default",
    )
    parser.add_argument(
        "--progress-spinner",
        type=ProgressSpinnerChoice,
        choices=ProgressSpinnerChoice,
        default=os.environ.get("PIP_AUDIT_PROGRESS_SPINNER", ProgressSpinnerChoice.On),
        help="display a progress spinner",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="set the socket timeout",  # Match the `pip` default
    )
    dep_source_args.add_argument(
        "--path",
        type=Path,
        metavar="PATH",
        action="append",
        dest="paths",
        default=[],
        help="restrict to the specified installation path for auditing packages; "
        "this option can be used multiple times",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="run with additional debug logging; supply multiple times to increase verbosity",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="automatically upgrade dependencies with known vulnerabilities",
    )
    parser.add_argument(
        "--require-hashes",
        action="store_true",
        help="require a hash to check each requirement against, for repeatable audits; this option "
        "is implied when any package in a requirements file has a `--hash` option.",
    )
    parser.add_argument(
        "--index-url",
        type=str,
        help="base URL of the Python Package Index; this should point to a repository compliant "
        "with PEP 503 (the simple repository API); this will be resolved by pip if not specified",
    )
    parser.add_argument(
        "--extra-index-url",
        type=str,
        metavar="URL",
        action="append",
        dest="extra_index_urls",
        default=[],
        help="extra URLs of package indexes to use in addition to `--index-url`; should follow the "
        "same rules as `--index-url`",
    )
    parser.add_argument(
        "--skip-editable",
        action="store_true",
        help="don't audit packages that are marked as editable",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="don't perform any dependency resolution; requires all requirements are pinned "
        "to an exact version",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="output results to the given file",
        default=os.environ.get("PIP_AUDIT_OUTPUT", "stdout"),
    )
    parser.add_argument(
        "--ignore-vuln",
        type=str,
        metavar="ID",
        action="append",
        dest="ignore_vulns",
        default=[],
        help=(
            "ignore a specific vulnerability by its vulnerability ID; "
            "this option can be used multiple times"
        ),
    )
    parser.add_argument(
        "--disable-pip",
        action="store_true",
        help="don't use `pip` for dependency resolution; "
        "this can only be used with hashed requirements files or if the `--no-deps` flag has been "
        "provided",
    )
    return parser


def _parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:  # pragma: no cover
    args = parser.parse_args()

    # Configure logging upfront, so that we don't miss anything.
    if args.verbose >= 1:
        package_logger.setLevel("DEBUG")
    if args.verbose >= 2:
        logging.getLogger().setLevel("DEBUG")

    logger.debug(f"parsed arguments: {args}")

    return args


def _dep_source_from_project_path(
    project_path: Path, index_url: str, extra_index_urls: list[str], locked: bool, state: AuditState
) -> DependencySource:  # pragma: no cover
    # If the user has passed `--locked`, we check for `pylock.*.toml` files.
    if locked:
        all_pylocks = list(project_path.glob("pylock.*.toml"))
        generic_pylock = project_path / "pylock.toml"
        if generic_pylock.is_file():
            all_pylocks.append(generic_pylock)

        if not all_pylocks:
            _fatal(f"no lockfiles found in {project_path}")

        return PyLockSource(all_pylocks)

    # Check for a `pyproject.toml`
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.is_file():
        return PyProjectSource(
            pyproject_path,
            index_url=index_url,
            extra_index_urls=extra_index_urls,
            state=state,
        )

    # TODO: Checks for setup.py and other project files will go here.

    _fatal(f"couldn't find a supported project file in {project_path}")


def audit() -> None:  # pragma: no cover
    """
    The primary entrypoint for `pip-audit`.
    """
    parser = _parser()
    args = _parse_args(parser)

    service: VulnerabilityService
    if args.vulnerability_service is VulnerabilityServiceChoice.Osv:
        service = OsvService(cache_dir=args.cache_dir, timeout=args.timeout, osv_url=args.osv_url)
    elif args.vulnerability_service is VulnerabilityServiceChoice.Pypi:
        service = PyPIService(cache_dir=args.cache_dir, timeout=args.timeout)
    elif args.vulnerability_service is VulnerabilityServiceChoice.Esms:
        service = EcosystemsService(cache_dir=args.cache_dir, timeout=args.timeout)
    else:
        assert_never(args.vulnerability_service)  # pragma: no cover

    output_desc = args.desc.to_bool(args.format)
    output_aliases = args.aliases.to_bool(args.format)
    formatter = args.format.to_format(output_desc, output_aliases)

    # Check for flags that are only valid with project paths
    if args.project_path is None:
        if args.locked:
            parser.error("The --locked flag can only be used with a project path")

    # Check for flags that are only valid with requirements files
    if args.requirements is None:
        if args.require_hashes:
            parser.error("The --require-hashes flag can only be used with --requirement (-r)")
        elif args.index_url:
            parser.error("The --index-url flag can only be used with --requirement (-r)")
        elif args.extra_index_urls:
            parser.error("The --extra-index-url flag can only be used with --requirement (-r)")
        elif args.no_deps:
            parser.error("The --no-deps flag can only be used with --requirement (-r)")
        elif args.disable_pip:
            parser.error("The --disable-pip flag can only be used with --requirement (-r)")

    # Nudge users to consider alternate workflows.
    if args.require_hashes and args.no_deps:
        logger.warning("The --no-deps flag is redundant when used with --require-hashes")

    if args.require_hashes and isinstance(service, OsvService):
        logger.warning(
            "The --require-hashes flag with --service osv only enforces hash presence NOT hash "
            "validity. Use --service pypi to enforce hash validity."
        )

    if args.no_deps:
        logger.warning(
            "--no-deps is supported, but users are encouraged to fully hash their "
            "pinned dependencies"
        )
        logger.warning(
            "Consider using a tool like `pip-compile`: "
            "https://pip-tools.readthedocs.io/en/latest/#using-hashes"
        )

    with ExitStack() as stack:
        actors = []
        if args.progress_spinner:
            actors.append(AuditSpinner("Collecting inputs"))
        state = stack.enter_context(AuditState(members=actors))

        source: DependencySource
        if args.requirements is not None:
            for req in args.requirements:
                if not req.exists():
                    _fatal(f"invalid requirements input: {req}")

            source = RequirementSource(
                args.requirements,
                require_hashes=args.require_hashes,
                no_deps=args.no_deps,
                disable_pip=args.disable_pip,
                skip_editable=args.skip_editable,
                index_url=args.index_url,
                extra_index_urls=args.extra_index_urls,
                state=state,
            )
        elif args.project_path is not None:
            # NOTE: We'll probably want to support --skip-editable here,
            # once PEP 660 is more widely supported: https://www.python.org/dev/peps/pep-0660/

            # Determine which kind of project file exists in the project path
            source = _dep_source_from_project_path(
                args.project_path,
                args.index_url,
                args.extra_index_urls,
                args.locked,
                state,
            )
        else:
            source = PipSource(
                local=args.local,
                paths=args.paths,
                skip_editable=args.skip_editable,
                state=state,
            )

        # `--dry-run` only affects the auditor if `--fix` is also not supplied,
        # since the combination of `--dry-run` and `--fix` implies that the user
        # wants to dry-run the "fix" step instead of the "audit" step
        auditor = Auditor(service, options=AuditOptions(dry_run=args.dry_run and not args.fix))

        result: dict[Dependency, list[VulnerabilityResult]] = {}
        pkg_count = 0
        vuln_count = 0
        skip_count = 0
        vuln_ignore_count = 0
        vulns_to_ignore = set(args.ignore_vulns)
        try:
            for spec, vulns in auditor.audit(source):
                if spec.is_skipped():
                    spec = cast(SkippedDependency, spec)
                    if args.strict:
                        _fatal(f"{spec.name}: {spec.skip_reason}")
                    else:
                        state.update_state(f"Skipping {spec.name}: {spec.skip_reason}")
                    skip_count += 1
                else:
                    spec = cast(ResolvedDependency, spec)
                    logger.debug(f"Auditing {spec.name} ({spec.version})")
                    state.update_state(f"Auditing {spec.name} ({spec.version})")
                if vulns_to_ignore:
                    filtered_vulns = [v for v in vulns if not v.has_any_id(vulns_to_ignore)]
                    vuln_ignore_count += len(vulns) - len(filtered_vulns)
                    vulns = filtered_vulns
                result[spec] = vulns
                if len(vulns) > 0:
                    pkg_count += 1
                    vuln_count += len(vulns)
        except DependencySourceError as e:
            _fatal(str(e))
        except VulnServiceConnectionError as e:
            # The most common source of connection errors is corporate blocking,
            # so we offer a bit of advice.
            logger.error(str(e))
            _fatal(
                "Tip: your network may be blocking this service. "
                "Try another service with `-s SERVICE`"
            )

        # If the `--fix` flag has been applied, find a set of suitable fix versions and upgrade the
        # dependencies at the source
        fixes = []
        fixed_pkg_count = 0
        fixed_vuln_count = 0
        if args.fix:
            for fix in resolve_fix_versions(service, result, state):
                if args.dry_run:
                    if fix.is_skipped():
                        fix = cast(SkippedFixVersion, fix)
                        logger.info(
                            f"Dry run: would have skipped {fix.dep.name} "
                            f"upgrade because {fix.skip_reason}"
                        )
                    else:
                        fix = cast(ResolvedFixVersion, fix)
                        logger.info(f"Dry run: would have upgraded {fix.dep.name} to {fix.version}")
                    continue

                if not fix.is_skipped():
                    fix = cast(ResolvedFixVersion, fix)
                    try:
                        source.fix(fix)
                        fixed_pkg_count += 1
                        fixed_vuln_count += len(result[fix.dep])
                    except DependencySourceError as dse:
                        skip_reason = str(dse)
                        logger.debug(skip_reason)
                        fix = SkippedFixVersion(fix.dep, skip_reason)
                fixes.append(fix)

    if vuln_count > 0:
        if vuln_ignore_count:
            ignored = f", ignored {vuln_ignore_count}"
        else:
            ignored = ""

        summary_msg = (
            f"Found {vuln_count} known "
            f"{'vulnerability' if vuln_count == 1 else 'vulnerabilities'}"
            f"{ignored} in {pkg_count} {'package' if pkg_count == 1 else 'packages'}"
        )
        if args.fix:
            summary_msg += (
                f" and fixed {fixed_vuln_count} "
                f"{'vulnerability' if fixed_vuln_count == 1 else 'vulnerabilities'} "
                f"in {fixed_pkg_count} "
                f"{'package' if fixed_pkg_count == 1 else 'packages'}"
            )
        print(summary_msg, file=sys.stderr)
        with _output_io(args.output) as io:
            print(formatter.format(result, fixes), file=io)
        if pkg_count != fixed_pkg_count:
            sys.exit(1)
    else:
        summary_msg = "No known vulnerabilities found"
        if vuln_ignore_count:
            summary_msg += f", {vuln_ignore_count} ignored"

        print(
            summary_msg,
            file=sys.stderr,
        )
        # If our output format is a "manifest" format we always emit it,
        # even if nothing other than a dependency summary is present.
        if skip_count > 0 or formatter.is_manifest:
            with _output_io(args.output) as io:
                print(formatter.format(result, fixes), file=io)
