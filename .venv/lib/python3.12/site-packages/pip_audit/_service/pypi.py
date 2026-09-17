"""
Functionality for using the [PyPI](https://warehouse.pypa.io/api-reference/json.html)
API as a `VulnerabilityService`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import requests
from packaging.version import InvalidVersion, Version

from pip_audit._cache import caching_session
from pip_audit._service.interface import (
    ConnectionError,
    Dependency,
    ResolvedDependency,
    ServiceError,
    SkippedDependency,
    VulnerabilityResult,
    VulnerabilityService,
)

logger = logging.getLogger(__name__)


class PyPIService(VulnerabilityService):
    """
    An implementation of `VulnerabilityService` that uses PyPI to provide Python
    package vulnerability information.
    """

    def __init__(
        self, cache_dir: Path | None = None, timeout: int | None = None, **kwargs: dict
    ) -> None:
        """
        Create a new `PyPIService`.

        `cache_dir` is an optional cache directory to use, for caching and reusing PyPI API
        requests. If `None`, `pip-audit` will attempt to use `pip`'s cache directory before falling
        back on its own default cache directory.

        `timeout` is an optional argument to control how many seconds the component should wait for
        responses to network requests.
        """
        self.session = caching_session(cache_dir)
        self.timeout = timeout

    def query(self, spec: Dependency) -> tuple[Dependency, list[VulnerabilityResult]]:
        """
        Queries PyPI for the given `Dependency` specification.

        See `VulnerabilityService.query`.
        """
        if spec.is_skipped():
            return spec, []
        spec = cast(ResolvedDependency, spec)

        url = f"https://pypi.org/pypi/{spec.canonical_name}/{str(spec.version)}/json"

        try:
            response: requests.Response = self.session.get(url=url, timeout=self.timeout)
            response.raise_for_status()
        except requests.TooManyRedirects:
            # This should never happen with a healthy PyPI instance, but might
            # happen during an outage or network event.
            # Ref 2022-06-10: https://status.python.org/incidents/lgpr13fy71bk
            raise ConnectionError("PyPI is not redirecting properly")
        except requests.ConnectTimeout:
            # Apart from a normal network outage, this can happen for two main
            # reasons:
            # 1. PyPI's APIs are offline
            # 2. The user is behind a firewall or corporate network that blocks
            #    PyPI (and they're probably using custom indices)
            raise ConnectionError("Could not connect to PyPI's vulnerability feed")
        except requests.HTTPError as http_error:
            if response.status_code == 404:
                skip_reason = (
                    "Dependency not found on PyPI and could not be audited: "
                    f"{spec.canonical_name} ({spec.version})"
                )
                logger.debug(skip_reason)
                return SkippedDependency(name=spec.name, skip_reason=skip_reason), []
            raise ServiceError from http_error

        response_json = response.json()
        results: list[VulnerabilityResult] = []
        vulns = response_json.get("vulnerabilities")

        # No `vulnerabilities` key means that there are no vulnerabilities for any version
        if vulns is None:
            return spec, results

        for v in vulns:
            id = v["id"]

            # If the vulnerability has been withdrawn, we skip it entirely.
            withdrawn_at = v.get("withdrawn")
            if withdrawn_at is not None:
                logger.debug(f"PyPI vuln entry '{id}' marked as withdrawn at {withdrawn_at}")
                continue

            # Put together the fix versions list
            try:
                fix_versions = [Version(fixed_in) for fixed_in in v["fixed_in"]]
            except InvalidVersion as iv:
                raise ServiceError(f"Received malformed version from PyPI: {v['fixed_in']}") from iv

            # The ranges aren't guaranteed to come in chronological order
            fix_versions.sort()

            description = v.get("summary")
            if description is None:
                description = v.get("details")

            if description is None:
                description = "N/A"

            # The "summary" field should be a single line, but "details" might
            # be multiple (Markdown-formatted) lines. So, we normalize our
            # description into a single line (and potentially break the Markdown
            # formatting in the process).
            description = description.replace("\n", " ")

            results.append(
                VulnerabilityResult.create(
                    ids=[id, *v["aliases"]],
                    description=description,
                    fix_versions=fix_versions,
                    published=self._parse_rfc3339(v.get("published")),
                )
            )

        return spec, results
