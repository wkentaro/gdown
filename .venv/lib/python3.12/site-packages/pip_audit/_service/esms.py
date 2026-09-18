"""
Functionality for using the [Ecosyste.ms](https://ecosyste.ms/) API as a `VulnerabilityService`.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import requests
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from pip_audit._cache import caching_session
from pip_audit._service.interface import (
    ConnectionError,
    Dependency,
    ResolvedDependency,
    ServiceError,
    VulnerabilityID,
    VulnerabilityResult,
    VulnerabilityService,
)

logger = logging.getLogger(__name__)


class EcosystemsService(VulnerabilityService):
    """
    An implementation of `VulnerabilityService` that uses Ecosyste.ms to provide Python
    package vulnerability information.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        timeout: int | None = None,
    ):
        """
        Create a new `EcosystemsService`.

        `cache_dir` is an optional cache directory to use, for caching and reusing OSV API
        requests. If `None`, `pip-audit` will use its own internal caching directory.

        `timeout` is an optional argument to control how many seconds the component should wait for
        responses to network requests.
        """
        self.session = caching_session(cache_dir, use_pip=False)
        self.timeout = timeout

    def query(self, spec: Dependency) -> tuple[Dependency, list[VulnerabilityResult]]:
        """
        Queries Ecosyste.ms for the given `Dependency` specification.

        See `VulnerabilityService.query`.
        """
        url = "https://advisories.ecosyste.ms/api/v1/advisories"

        if spec.is_skipped():
            return spec, []
        spec = cast(ResolvedDependency, spec)

        query = {
            "ecosystem": "pypi",
            "package_name": spec.canonical_name,
        }

        try:
            response: requests.Response = self.session.get(
                f"{url}?{urlencode(query)}",
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.ConnectTimeout:
            raise ConnectionError("Could not connect to ESMS' vulnerability feed")
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
        for vuln in response_json:
            # Get the IDs, prioritising PYSEC and CVE.
            ids: list[VulnerabilityID] = vuln["identifiers"]

            # If the vulnerability has been withdrawn, we skip it entirely.
            withdrawn_at = vuln["withdrawn_at"]
            if withdrawn_at is not None:
                logger.debug(f"ESMS vuln entry '{ids[0]}' marked as withdrawn at {withdrawn_at}")
                continue

            # The title is intended to be shorter, so we prefer it over
            # description, if present. The Ecosyste.ms advisory metadata states that
            # these fields *should* always be of type `str`; we are being defensive
            # here and checking if the strings are empty.
            description = vuln["title"]
            if not description:
                description = vuln["description"]
            if not description:
                description = "N/A"

            # The "title" field should be a single line, but "description" might
            # be multiple (Markdown-formatted) lines. So, we normalize our
            # description into a single line (and potentially break the Markdown
            # formatting in the process).
            description = description.replace("\n", " ")

            seen_vulnerable = False
            fix_versions: set[Version] = set()
            for affected in vuln["packages"]:
                # We only care about PyPI versions.
                if (
                    affected["package_name"] != spec.canonical_name
                    or affected["ecosystem"] != "pypi"
                ):
                    continue

                for record in affected["versions"]:
                    # Very silly: OSV version specs use single `=` for exact matches, while PEP 440
                    # requires double `==`. All OSV operators have equivalent semantics to their
                    # PEP 440 counterparts, so we do some gross regex munging here to accommodate for
                    # the syntactical difference.
                    osv_spec: str = record["vulnerable_version_range"]
                    vulnerable = SpecifierSet(re.sub(r"(^|(, ))=", r"\1==", osv_spec))
                    if not vulnerable.contains(spec.version):
                        continue

                    seen_vulnerable = True
                    if (patched := record.get("first_patched_version")) is not None:
                        fix_versions.add(Version(patched))
                    break

            if not seen_vulnerable:
                continue

            results.append(
                VulnerabilityResult.create(
                    ids=ids,
                    description=description,
                    fix_versions=sorted(fix_versions),
                    published=self._parse_rfc3339(vuln.get("published")),
                )
            )

        return spec, results
