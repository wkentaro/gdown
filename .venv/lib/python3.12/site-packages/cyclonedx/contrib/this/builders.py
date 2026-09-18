# This file is part of CycloneDX Python Library
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) OWASP Foundation. All Rights Reserved.

"""Representation of this very python library."""

__all__ = ['this_component', 'this_tool', ]

from ... import __version__ as __ThisVersion  # noqa: N812
from ...model import ExternalReference, ExternalReferenceType, XsUri
from ...model.component import Component, ComponentType
from ...model.license import DisjunctiveLicense, LicenseAcknowledgement
from ...model.tool import Tool

# !!! keep this file in sync with `pyproject.toml`


def this_component() -> Component:
    """Representation of this very python library as a :class:`cyclonedx.model.component.Component`."""
    return Component(
        type=ComponentType.LIBRARY,
        group='CycloneDX',
        name='cyclonedx-python-lib',
        version=__ThisVersion or 'UNKNOWN',
        description='Python library for CycloneDX',
        licenses=(DisjunctiveLicense(id='Apache-2.0',
                                     acknowledgement=LicenseAcknowledgement.DECLARED),),
        external_references=(
            # let's assume this is not a fork
            ExternalReference(
                type=ExternalReferenceType.WEBSITE,
                url=XsUri('https://github.com/CycloneDX/cyclonedx-python-lib/#readme')
            ),
            ExternalReference(
                type=ExternalReferenceType.DOCUMENTATION,
                url=XsUri('https://cyclonedx-python-library.readthedocs.io/')
            ),
            ExternalReference(
                type=ExternalReferenceType.VCS,
                url=XsUri('https://github.com/CycloneDX/cyclonedx-python-lib')
            ),
            ExternalReference(
                type=ExternalReferenceType.BUILD_SYSTEM,
                url=XsUri('https://github.com/CycloneDX/cyclonedx-python-lib/actions')
            ),
            ExternalReference(
                type=ExternalReferenceType.ISSUE_TRACKER,
                url=XsUri('https://github.com/CycloneDX/cyclonedx-python-lib/issues')
            ),
            ExternalReference(
                type=ExternalReferenceType.LICENSE,
                url=XsUri('https://github.com/CycloneDX/cyclonedx-python-lib/blob/main/LICENSE')
            ),
            ExternalReference(
                type=ExternalReferenceType.RELEASE_NOTES,
                url=XsUri('https://github.com/CycloneDX/cyclonedx-python-lib/blob/main/CHANGELOG.md')
            ),
            # we cannot assert where the lib was fetched from, but we can give a hint
            ExternalReference(
                type=ExternalReferenceType.DISTRIBUTION,
                url=XsUri('https://pypi.org/project/cyclonedx-python-lib/')
            ),
        ),
        # to be extended...
    )


def this_tool() -> Tool:
    """Representation of this very python library as a :class:`cyclonedx.model.tool.Tool`."""
    return Tool.from_component(this_component())
