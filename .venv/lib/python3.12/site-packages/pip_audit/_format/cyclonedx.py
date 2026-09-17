"""
Functionality for formatting vulnerability results using the CycloneDX SBOM format.
"""

from __future__ import annotations

import enum
import logging
from typing import cast

from cyclonedx import output
from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component
from cyclonedx.model.vulnerability import BomTarget, Vulnerability

import pip_audit._fix as fix
import pip_audit._service as service

from .interface import VulnerabilityFormat

logger = logging.getLogger(__name__)


def _pip_audit_result_to_bom(
    result: dict[service.Dependency, list[service.VulnerabilityResult]],
) -> Bom:
    vulnerabilities = []
    components = []

    for dep, vulns in result.items():
        # TODO(alex): Is there anything interesting we can do with skipped dependencies in
        # the CycloneDX format?
        if dep.is_skipped():
            continue
        dep = cast(service.ResolvedDependency, dep)

        c = Component(name=dep.name, version=str(dep.version))
        vuln_list = [
            Vulnerability(
                id=vuln.id,
                description=vuln.description,
                recommendation="Upgrade",
                # BomTarget expects str in type hints, but accepts BomRef at runtime
                affects=[BomTarget(ref=c.bom_ref)],  # type: ignore[arg-type]
            )
            for vuln in vulns
        ]
        vulnerabilities.extend(vuln_list)
        components.append(c)

    return Bom(components=components, vulnerabilities=vulnerabilities)


class CycloneDxFormat(VulnerabilityFormat):
    """
    An implementation of `VulnerabilityFormat` that formats vulnerability results using CycloneDX.
    The container format used by CycloneDX can be additionally configured.
    """

    @enum.unique
    class InnerFormat(enum.Enum):
        """
        Valid container formats for CycloneDX.
        """

        Json = output.OutputFormat.JSON
        Xml = output.OutputFormat.XML

    def __init__(self, inner_format: CycloneDxFormat.InnerFormat):
        """
        Create a new `CycloneDxFormat`.

        `inner_format` determines the container format used by CycloneDX.
        """

        self._inner_format = inner_format

    @property
    def is_manifest(self) -> bool:
        """
        See `VulnerabilityFormat.is_manifest`.
        """
        return True

    def format(
        self,
        result: dict[service.Dependency, list[service.VulnerabilityResult]],
        fixes: list[fix.FixVersion],
    ) -> str:
        """
        Returns a CycloneDX formatted string for a given mapping of dependencies to vulnerability
        results.

        See `VulnerabilityFormat.format`.
        """
        if fixes:
            logger.warning("--fix output is unsupported by CycloneDX formats")

        bom = _pip_audit_result_to_bom(result)
        formatter = output.make_outputter(
            bom=bom,
            output_format=self._inner_format.value,
            schema_version=output.SchemaVersion.V1_4,
        )

        return formatter.output_as_string()
