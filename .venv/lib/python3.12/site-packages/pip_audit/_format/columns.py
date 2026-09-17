"""
Functionality for formatting vulnerability results as a set of human-readable columns.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from itertools import zip_longest
from typing import Any, cast

from packaging.version import Version

import pip_audit._fix as fix
import pip_audit._service as service

from .interface import VulnerabilityFormat, pypi_url, vuln_id_url

_OSC8_RE = re.compile(r"\033]8;;[^\033]*\033\\")


def _osc8_link(text: str, url: str) -> str:
    """Wrap text in an OSC 8 terminal hyperlink."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def _visible_len(s: str) -> int:
    """Return the visible length of a string, ignoring OSC 8 escape sequences."""
    return len(_OSC8_RE.sub("", s))


def _visible_ljust(s: str, width: int) -> str:
    """Left-justify a string to the given visible width, ignoring OSC 8 escapes."""
    return s + " " * (width - _visible_len(s))


def tabulate(rows: Iterable[Iterable[Any]]) -> tuple[list[str], list[int]]:
    """Return a list of formatted rows and a list of column sizes.
    For example::
    >>> tabulate([['foobar', 2000], [0xdeadbeef]])
    (['foobar     2000', '3735928559'], [10, 4])
    """
    rows = [tuple(map(str, row)) for row in rows]
    sizes = [max(map(_visible_len, col)) for col in zip_longest(*rows, fillvalue="")]
    table = [" ".join(map(_visible_ljust, row, sizes)).rstrip() for row in rows]
    return table, sizes


class ColumnsFormat(VulnerabilityFormat):
    """
    An implementation of `VulnerabilityFormat` that formats vulnerability results as a set of
    columns.
    """

    def __init__(self, output_desc: bool, output_aliases: bool):
        """
        Create a new `ColumnFormat`.

        `output_desc` is a flag to determine whether descriptions for each vulnerability should be
        included in the output as they can be quite long and make the output difficult to read.

        `output_aliases` is a flag to determine whether aliases (such as CVEs) for each
        vulnerability should be included in the output.
        """
        self.output_desc = output_desc
        self.output_aliases = output_aliases

    @property
    def is_manifest(self) -> bool:
        """
        See `VulnerabilityFormat.is_manifest`.
        """
        return False

    def format(
        self,
        result: dict[service.Dependency, list[service.VulnerabilityResult]],
        fixes: list[fix.FixVersion],
    ) -> str:
        """
        Returns a column formatted string for a given mapping of dependencies to vulnerability
        results.

        See `VulnerabilityFormat.format`.
        """
        vuln_data: list[list[Any]] = []
        header = ["Name", "Version", "ID", "Fix Versions"]
        if fixes:
            header.append("Applied Fix")
        if self.output_aliases:
            header.append("Aliases")
        if self.output_desc:
            header.append("Description")
        vuln_data.append(header)

        vuln_rows = [
            self._format_vuln(
                cast(service.ResolvedDependency, dep),
                vuln,
                next((f for f in fixes if f.dep == dep), None),
            )
            for dep, vulns in result.items()
            if not dep.is_skipped()
            for vuln in vulns
        ]

        vuln_data.extend(vuln_rows)

        columns_string = ""

        # If it's just a header, don't bother adding it to the output
        if len(vuln_data) > 1:
            vuln_strings, sizes = tabulate(vuln_data)

            # Create and add a separator.
            if len(vuln_data) > 0:
                vuln_strings.insert(1, " ".join("-" * x for x in sizes))

            for row in vuln_strings:
                if columns_string:
                    columns_string += "\n"
                columns_string += row

        # Now display the skipped dependencies
        skip_data = [
            self._format_skipped_dep(cast(service.SkippedDependency, dep))
            for dep in result.keys()
            if dep.is_skipped()
        ]

        if skip_data:
            skip_data.insert(0, ["Name", "Skip Reason"])
            skip_strings, sizes = tabulate(skip_data)
            skip_strings.insert(1, " ".join("-" * x for x in sizes))

            if columns_string:
                columns_string += "\n"
            for row in skip_strings:
                if columns_string:
                    columns_string += "\n"
                columns_string += row

        return columns_string

    def _format_vuln(
        self,
        dep: service.ResolvedDependency,
        vuln: service.VulnerabilityResult,
        applied_fix: fix.FixVersion | None,
    ) -> list[Any]:
        link = _osc8_link if sys.stdout.isatty() else lambda text, _url: text
        vuln_data = [
            link(dep.canonical_name, pypi_url(dep.canonical_name)),
            dep.version,
            link(vuln.id, vuln_id_url(vuln.id)),
            self._format_fix_versions(vuln.fix_versions),
        ]
        if applied_fix is not None:
            vuln_data.append(self._format_applied_fix(applied_fix))
        if self.output_aliases:
            vuln_data.append(", ".join(link(a, vuln_id_url(a)) for a in vuln.aliases))
        if self.output_desc:
            vuln_data.append(vuln.description)
        return vuln_data

    def _format_fix_versions(self, fix_versions: list[Version]) -> str:
        return ",".join([str(version) for version in fix_versions])

    def _format_skipped_dep(self, dep: service.SkippedDependency) -> list[Any]:
        return [
            dep.canonical_name,
            dep.skip_reason,
        ]

    def _format_applied_fix(self, applied_fix: fix.FixVersion) -> str:
        if applied_fix.is_skipped():
            applied_fix = cast(fix.SkippedFixVersion, applied_fix)
            return (
                f"Failed to fix {applied_fix.dep.canonical_name} ({applied_fix.dep.version}): "
                f"{applied_fix.skip_reason}"
            )
        applied_fix = cast(fix.ResolvedFixVersion, applied_fix)
        return (
            f"Successfully upgraded {applied_fix.dep.canonical_name} ({applied_fix.dep.version} "
            f"=> {applied_fix.version})"
        )
