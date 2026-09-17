"""
Functionality for using the [OSV](https://osv.dev/) API as a `VulnerabilityService`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import requests
from packaging.version import Version

from pip_audit._cache import caching_session
from pip_audit._service.interface import (
    ConnectionError,
    Dependency,
    ResolvedDependency,
    ServiceError,
    VulnerabilityResult,
    VulnerabilityService,
)

logger = logging.getLogger(__name__)


class OsvService(VulnerabilityService):
    """
    An implementation of `VulnerabilityService` that uses OSV to provide Python
    package vulnerability information.
    """

    DEFAULT_OSV_URL = "https://api.osv.dev/v1/query"

    def __init__(
        self,
        cache_dir: Path | None = None,
        timeout: int | None = None,
        osv_url: str = DEFAULT_OSV_URL,
    ):
        """
        Create a new `OsvService`.

        `cache_dir` is an optional cache directory to use, for caching and reusing OSV API
        requests. If `None`, `pip-audit` will use its own internal caching directory.

        `timeout` is an optional argument to control how many seconds the component should wait for
        responses to network requests.
        """
        self.session = caching_session(cache_dir, use_pip=False)
        self.timeout = timeout
        self.osv_url = osv_url

    def query(self, spec: Dependency) -> tuple[Dependency, list[VulnerabilityResult]]:
        """
        Queries OSV for the given `Dependency` specification.

        See `VulnerabilityService.query`.
        """
        if spec.is_skipped():
            return spec, []
        spec = cast(ResolvedDependency, spec)

        query = {
            "package": {"name": spec.canonical_name, "ecosystem": "PyPI"},
            "version": str(spec.version),
        }
        try:
            response: requests.Response = self.session.post(
                url=self.osv_url,
                data=json.dumps(query),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.ConnectTimeout:
            raise ConnectionError("Could not connect to OSV's vulnerability feed")
        except requests.HTTPError as http_error:
            raise ServiceError from http_error

        # If the response is empty, that means that the package/version pair doesn't have any
        # associated vulnerabilities
        #
        # In that case, return an empty list
        results: list[VulnerabilityResult] = []
        response_json = response.json()
        if not response_json:
            return spec, results

        vuln: dict[str, Any]
        for vuln in response_json["vulns"]:
            # Sanity check: only the v1 schema is specified at the moment,
            # and the code below probably won't work with future incompatible
            # schemas without additional changes.
            # The absence of a schema is treated as 1.0.0, per the OSV spec.
            schema_version = Version(vuln.get("schema_version", "1.0.0"))
            if schema_version.major != 1:
                logger.warning(f"Unsupported OSV schema version: {schema_version}")
                continue

            id = vuln["id"]

            # If the vulnerability has been withdrawn, we skip it entirely.
            withdrawn_at = vuln.get("withdrawn")
            if withdrawn_at is not None:
                logger.debug(f"OSV vuln entry '{id}' marked as withdrawn at {withdrawn_at}")
                continue

            # The summary is intended to be shorter, so we prefer it over
            # details, if present. However, neither is required.
            description = vuln.get("summary")
            if description is None:
                description = vuln.get("details")
            if description is None:
                description = "N/A"

            # The "summary" field should be a single line, but "details" might
            # be multiple (Markdown-formatted) lines. So, we normalize our
            # description into a single line (and potentially break the Markdown
            # formatting in the process).
            description = description.replace("\n", " ")

            # OSV doesn't mandate this field either. There's very little we
            # can do without it, so we skip any results that are missing it.
            affecteds = vuln.get("affected")
            if affecteds is None:
                logger.warning(f"OSV vuln entry '{id}' is missing 'affected' list")
                continue

            fix_versions: list[Version] = []
            for affected in affecteds:
                pkg = affected["package"]
                # We only care about PyPI versions
                if pkg["name"] == spec.canonical_name and pkg["ecosystem"] == "PyPI":
                    for ranges in affected.get("ranges", []):
                        if ranges["type"] == "ECOSYSTEM":
                            # Filter out non-fix versions
                            fix_version_strs = [
                                version["fixed"]
                                for version in ranges["events"]
                                if "fixed" in version
                            ]
                            # Convert them to version objects
                            fix_versions = [
                                Version(version_str) for version_str in fix_version_strs
                            ]
                            break

            # The ranges aren't guaranteed to come in chronological order
            fix_versions.sort()

            results.append(
                VulnerabilityResult.create(
                    ids=[id, *vuln.get("aliases", [])],
                    description=description,
                    fix_versions=fix_versions,
                    published=self._parse_rfc3339(vuln.get("published")),
                )
            )

        return spec, results
