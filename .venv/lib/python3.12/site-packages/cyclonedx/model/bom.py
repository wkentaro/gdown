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


from collections.abc import Generator, Iterable
from datetime import datetime
from enum import Enum
from itertools import chain
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID, uuid4
from warnings import warn

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from .._internal.time import get_now_utc as _get_now_utc
from ..exception.model import LicenseExpressionAlongWithOthersException, UnknownComponentDependencyException
from ..schema.deprecation import SchemaDeprecationWarning1Dot6
from ..schema.schema import (
    SchemaVersion1Dot0,
    SchemaVersion1Dot1,
    SchemaVersion1Dot2,
    SchemaVersion1Dot3,
    SchemaVersion1Dot4,
    SchemaVersion1Dot5,
    SchemaVersion1Dot6,
    SchemaVersion1Dot7,
)
from ..serialization import UrnUuidHelper
from . import _BOM_LINK_PREFIX, ExternalReference, Property
from .bom_ref import BomRef
from .component import Component
from .contact import OrganizationalContact, OrganizationalEntity
from .definition import Definitions
from .dependency import Dependable, Dependency
from .license import License, LicenseExpression, LicenseRepository, _LicenseRepositorySerializationHelper
from .lifecycle import Lifecycle, LifecycleRepository, _LifecycleRepositoryHelper
from .service import Service
from .tool import Tool, ToolRepository, _ToolRepositoryHelper
from .vulnerability import Vulnerability

if TYPE_CHECKING:  # pragma: no cover
    from packageurl import PackageURL


@serializable.serializable_enum
class TlpClassification(str, Enum):
    """
    Enum object that defines the Traffic Light Protocol (TLP) classification that controls the sharing and distribution
    of the data that the BOM describes.

    .. note::
        Introduced in CycloneDX v1.7

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_tlpClassificationType
    """

    CLEAR = 'CLEAR'
    GREEN = 'GREEN'
    AMBER = 'AMBER'
    AMBER_AND_STRICT = 'AMBER_AND_STRICT'
    RED = 'RED'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class DistributionConstraints:
    """
    Our internal representation of the `distributionConstraints` complex type.
    Conditions and constraints governing the sharing and distribution of the data or components described by this BOM.

    .. note::
        Introduced in CycloneDX v1.7

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_metadata
    """

    def __init__(
        self, *,
        tlp: Optional[TlpClassification] = None,
    ) -> None:
        self.tlp = tlp or TlpClassification.CLEAR

    @property
    @serializable.xml_sequence(0)
    def tlp(self) -> TlpClassification:
        """
        The Traffic Light Protocol (TLP) classification that controls the sharing and distribution of the data that the
        BOM describes.

        Returns:
            `TlpClassification` enum value
        """
        return self._tlp

    @tlp.setter
    def tlp(self, tlp: TlpClassification) -> None:
        self._tlp = tlp

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple(self.tlp)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DistributionConstraints):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, DistributionConstraints):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<DistributionConstraints tlp={self.tlp}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class BomMetaData:
    """
    This is our internal representation of the metadata complex type within the CycloneDX standard.

    .. note::
        See the CycloneDX Schema for Bom metadata: https://cyclonedx.org/docs/1.7/xml/#type_metadata
    """

    def __init__(
        self, *,
        tools: Optional[Union[Iterable[Tool], ToolRepository]] = None,
        authors: Optional[Iterable[OrganizationalContact]] = None,
        component: Optional[Component] = None,
        supplier: Optional[OrganizationalEntity] = None,
        licenses: Optional[Iterable[License]] = None,
        properties: Optional[Iterable[Property]] = None,
        timestamp: Optional[datetime] = None,
        manufacturer: Optional[OrganizationalEntity] = None,
        lifecycles: Optional[Iterable[Lifecycle]] = None,
        distribution_constraints: Optional[DistributionConstraints] = None,
        # Deprecated as of v1.6
        manufacture: Optional[OrganizationalEntity] = None,
    ) -> None:
        self.timestamp = timestamp or _get_now_utc()
        self.tools = tools or []
        self.authors = authors or []
        self.component = component
        self.supplier = supplier
        self.licenses = licenses or []
        self.properties = properties or []
        self.manufacturer = manufacturer
        self.lifecycles = lifecycles or []
        self.distribution_constraints = distribution_constraints
        # deprecated properties below
        self.manufacture = manufacture

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(1)
    def timestamp(self) -> datetime:
        """
        The date and time (in UTC) when this BomMetaData was created.

        Returns:
            `datetime` instance in UTC timezone
        """
        return self._timestamp

    @timestamp.setter
    def timestamp(self, timestamp: datetime) -> None:
        self._timestamp = timestamp

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.type_mapping(_LifecycleRepositoryHelper)
    @serializable.xml_sequence(2)
    def lifecycles(self) -> LifecycleRepository:
        """
        An optional list of BOM lifecycle stages.

        Returns:
            Set of `Lifecycle`
        """
        return self._lifecycles

    @lifecycles.setter
    def lifecycles(self, lifecycles: Iterable[Lifecycle]) -> None:
        self._lifecycles = LifecycleRepository(lifecycles)

    @property
    @serializable.type_mapping(_ToolRepositoryHelper)
    @serializable.xml_sequence(3)
    def tools(self) -> ToolRepository:
        """
        Tools used to create this BOM.

        Returns:
            :class:`ToolRepository` object.
        """
        return self._tools

    @tools.setter
    def tools(self, tools: Union[Iterable[Tool], ToolRepository]) -> None:
        self._tools = tools \
            if isinstance(tools, ToolRepository) \
            else ToolRepository(tools=tools)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'author')
    @serializable.xml_sequence(4)
    def authors(self) -> 'SortedSet[OrganizationalContact]':
        """
        The person(s) who created the BOM.

        Authors are common in BOMs created through manual processes.

        BOMs created through automated means may not have authors.

        Returns:
            Set of `OrganizationalContact`
        """
        return self._authors

    @authors.setter
    def authors(self, authors: Iterable[OrganizationalContact]) -> None:
        self._authors = SortedSet(authors)

    @property
    @serializable.xml_sequence(5)
    def component(self) -> Optional[Component]:
        """
        The (optional) component that the BOM describes.

        Returns:
            `cyclonedx.model.component.Component` instance for this Bom Metadata.
        """
        return self._component

    @component.setter
    def component(self, component: Optional[Component]) -> None:
        """
        The (optional) component that the BOM describes.

        Args:
            component
                `cyclonedx.model.component.Component` instance to add to this Bom Metadata.

        Returns:
            None
        """
        self._component = component

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(6)
    def manufacture(self) -> Optional[OrganizationalEntity]:
        """
        The organization that manufactured the component that the BOM describes.

        Returns:
            `OrganizationalEntity` if set else `None`
        """
        return self._manufacture

    @manufacture.setter
    def manufacture(self, manufacture: Optional[OrganizationalEntity]) -> None:
        """
        @todo Based on https://github.com/CycloneDX/specification/issues/346,
              we should set this data on `.component.manufacturer`.
        """
        if manufacture is not None:
            SchemaDeprecationWarning1Dot6._warn('bom.metadata.manufacture', 'bom.metadata.component.manufacturer')
        self._manufacture = manufacture

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(7)
    def manufacturer(self) -> Optional[OrganizationalEntity]:
        """
        The organization that created the BOM.
        Manufacturer is common in BOMs created through automated processes. BOMs created through manual means may have
        `@.authors` instead.

        Returns:
            `OrganizationalEntity` if set else `None`
        """
        return self._manufacturer

    @manufacturer.setter
    def manufacturer(self, manufacturer: Optional[OrganizationalEntity]) -> None:
        self._manufacturer = manufacturer

    @property
    @serializable.xml_sequence(8)
    def supplier(self) -> Optional[OrganizationalEntity]:
        """
        The organization that supplied the component that the BOM describes.

        The supplier may often be the manufacturer, but may also be a distributor or repackager.

        Returns:
            `OrganizationalEntity` if set else `None`
        """
        return self._supplier

    @supplier.setter
    def supplier(self, supplier: Optional[OrganizationalEntity]) -> None:
        self._supplier = supplier

    @property
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.type_mapping(_LicenseRepositorySerializationHelper)
    @serializable.xml_sequence(9)
    def licenses(self) -> LicenseRepository:
        """
        A optional list of statements about how this BOM is licensed.

        Returns:
            Set of `LicenseChoice`
        """
        return self._licenses

    @licenses.setter
    def licenses(self, licenses: Iterable[License]) -> None:
        self._licenses = LicenseRepository(licenses)

    @property
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    @serializable.xml_sequence(10)
    def properties(self) -> 'SortedSet[Property]':
        """
        Provides the ability to document properties in a key/value store. This provides flexibility to include data not
        officially supported in the standard without having to use additional namespaces or create extensions.

        Property names of interest to the general public are encouraged to be registered in the CycloneDX Property
        Taxonomy - https://github.com/CycloneDX/cyclonedx-property-taxonomy. Formal registration is OPTIONAL.

        Return:
            Set of `Property`
        """
        return self._properties

    @properties.setter
    def properties(self, properties: Iterable[Property]) -> None:
        self._properties = SortedSet(properties)

    @property
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(11)
    def distribution_constraints(self) -> Optional[DistributionConstraints]:
        """
        Conditions and constraints governing the sharing and distribution of the data or components described by this
        BOM.

        Returns:
            `DistributionConstraints` or `None`
        """
        return self._distribution_constraints

    @distribution_constraints.setter
    def distribution_constraints(self, distribution_constraints: Optional[DistributionConstraints]) -> None:
        self._distribution_constraints = distribution_constraints

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            _ComparableTuple(self.authors), self.component, _ComparableTuple(self.licenses), self.manufacture,
            _ComparableTuple(self.properties), self.distribution_constraints,
            _ComparableTuple(self.lifecycles), self.supplier, self.timestamp, self.tools, self.manufacturer
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BomMetaData):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, BomMetaData):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<BomMetaData timestamp={self.timestamp}, component={self.component}>'


@serializable.serializable_class(
    ignore_during_deserialization={
        '$schema', 'bom_format', 'spec_version',  # JSON-implementation's format hints
    },
    ignore_unknown_during_deserialization=True
)
class Bom:
    """
    This is our internal representation of a bill-of-materials (BOM).

    Once you have an instance of `cyclonedx.model.bom.Bom`, you can pass this to an instance of
    `cyclonedx.output.BaseOutput` to produce a CycloneDX document according to a specific schema version and format.
    """

    def __init__(
        self, *,
        components: Optional[Iterable[Component]] = None,
        services: Optional[Iterable[Service]] = None,
        external_references: Optional[Iterable[ExternalReference]] = None,
        serial_number: Optional[UUID] = None,
        version: int = 1,
        metadata: Optional[BomMetaData] = None,
        dependencies: Optional[Iterable[Dependency]] = None,
        vulnerabilities: Optional[Iterable[Vulnerability]] = None,
        properties: Optional[Iterable[Property]] = None,
        definitions: Optional[Definitions] = None,
    ) -> None:
        """
        Create a new Bom that you can manually/programmatically add data to later.

        Returns:
            New, empty `cyclonedx.model.bom.Bom` instance.
        """
        self.serial_number = serial_number or uuid4()
        self.version = version
        self.metadata = metadata or BomMetaData()
        self.components = components or []
        self.services = services or []
        self.external_references = external_references or []
        self.vulnerabilities = vulnerabilities or []
        self.dependencies = dependencies or []
        self.properties = properties or []
        self.definitions = definitions or Definitions()

    @property
    @serializable.type_mapping(UrnUuidHelper)
    @serializable.view(SchemaVersion1Dot1)
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_attribute()
    def serial_number(self) -> UUID:
        """
        Unique UUID for this BOM

        Returns:
            `UUID` instance
            `UUID` instance
        """
        return self._serial_number

    @serial_number.setter
    def serial_number(self, serial_number: UUID) -> None:
        self._serial_number = serial_number

    @property
    @serializable.xml_attribute()
    def version(self) -> int:
        return self._version

    @version.setter
    def version(self, version: int) -> None:
        self._version = version

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(10)
    def metadata(self) -> BomMetaData:
        """
        Get our internal metadata object for this Bom.

        Returns:
            Metadata object instance for this Bom.

        .. note::
            See the CycloneDX Schema for Bom metadata: https://cyclonedx.org/docs/1.7/xml/#type_metadata
        """
        return self._metadata

    @metadata.setter
    def metadata(self, metadata: BomMetaData) -> None:
        self._metadata = metadata

    @property
    @serializable.include_none(SchemaVersion1Dot0)
    @serializable.include_none(SchemaVersion1Dot1)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'component')
    @serializable.xml_sequence(20)
    def components(self) -> 'SortedSet[Component]':
        """
        Get all the Components currently in this Bom.

        Returns:
             Set of `Component` in this Bom
        """
        return self._components

    @components.setter
    def components(self, components: Iterable[Component]) -> None:
        self._components = SortedSet(components)

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'service')
    @serializable.xml_sequence(30)
    def services(self) -> 'SortedSet[Service]':
        """
        Get all the Services currently in this Bom.

        Returns:
             Set of `Service` in this BOM
        """
        return self._services

    @services.setter
    def services(self, services: Iterable[Service]) -> None:
        self._services = SortedSet(services)

    @property
    @serializable.view(SchemaVersion1Dot1)
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'reference')
    @serializable.xml_sequence(40)
    def external_references(self) -> 'SortedSet[ExternalReference]':
        """
        Provides the ability to document external references related to the BOM or to the project the BOM describes.

        Returns:
            Set of `ExternalReference`
        """
        return self._external_references

    @external_references.setter
    def external_references(self, external_references: Iterable[ExternalReference]) -> None:
        self._external_references = SortedSet(external_references)

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'dependency')
    @serializable.xml_sequence(50)
    def dependencies(self) -> 'SortedSet[Dependency]':
        return self._dependencies

    @dependencies.setter
    def dependencies(self, dependencies: Iterable[Dependency]) -> None:
        self._dependencies = SortedSet(dependencies)

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot3)
    # @serializable.view(SchemaVersion1Dot4)
    # @serializable.view(SchemaVersion1Dot5)
    # @serializable.xml_sequence(6)
    # def compositions(self) -> ...:
    #     ...  # TODO Since CDX 1.3
    #
    # @compositions.setter
    # def compositions(self, ...) -> None:
    #     ...  # TODO Since CDX 1.3

    @property
    # @serializable.view(SchemaVersion1Dot3) @todo: Update py-serializable to support view by OutputFormat filtering
    # @serializable.view(SchemaVersion1Dot4) @todo: Update py-serializable to support view by OutputFormat filtering
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    @serializable.xml_sequence(70)
    def properties(self) -> 'SortedSet[Property]':
        """
        Provides the ability to document properties in a name/value store. This provides flexibility to include data
        not officially supported in the standard without having to use additional namespaces or create extensions.
        Property names of interest to the general public are encouraged to be registered in the CycloneDX Property
        Taxonomy - https://github.com/CycloneDX/cyclonedx-property-taxonomy. Formal registration is OPTIONAL.

        Return:
            Set of `Property`
        """
        return self._properties

    @properties.setter
    def properties(self, properties: Iterable[Property]) -> None:
        self._properties = SortedSet(properties)

    @property
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'vulnerability')
    @serializable.xml_sequence(80)
    def vulnerabilities(self) -> 'SortedSet[Vulnerability]':
        """
        Get all the Vulnerabilities in this BOM.

        Returns:
             Set of `Vulnerability`
        """
        return self._vulnerabilities

    @vulnerabilities.setter
    def vulnerabilities(self, vulnerabilities: Iterable[Vulnerability]) -> None:
        self._vulnerabilities = SortedSet(vulnerabilities)

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot5)
    # @serializable.xml_sequence(9)
    # def annotations(self) -> ...:
    #     ... # TODO Since CDX 1.5
    #
    # @annotations.setter
    # def annotations(self, ...) -> None:
    #     ...  # TODO Since CDX 1.5

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot5)
    # @formulation.xml_sequence(10)
    # def formulation(self) -> ...:
    #     ... # TODO Since CDX 1.5
    #
    # @formulation.setter
    # def formulation(self, ...) -> None:
    #     ...  # TODO Since CDX 1.5

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(110)
    def definitions(self) -> Optional[Definitions]:
        """
        The repository for definitions

        Returns:
            `Definitions`
        """
        return self._definitions if len(self._definitions.standards) > 0 else None

    @definitions.setter
    def definitions(self, definitions: Definitions) -> None:
        self._definitions = definitions

    def get_component_by_purl(self, purl: Optional['PackageURL']) -> Optional[Component]:
        """
        Get a Component already in the Bom by its PURL

        Args:
             purl:
                An instance of `packageurl.PackageURL` to look and find `Component`.

        Returns:
            `Component` or `None`

        .. deprecated:: next
        """
        if purl:
            found = [x for x in self.components if x.purl == purl]
            if len(found) == 1:
                return found[0]

        return None

    def get_urn_uuid(self) -> str:
        """
        Get the unique reference for this Bom.

        Returns:
            URN formatted UUID that uniquely identified this Bom instance.

        .. deprecated:: next
        """
        return self.serial_number.urn

    def has_component(self, component: Component) -> bool:
        """
        Check whether this Bom contains the provided Component.

        Args:
            component:
                The instance of `cyclonedx.model.component.Component` to check if this Bom contains.

        Returns:
            `bool` - `True` if the supplied Component is part of this Bom, `False` otherwise.

        .. deprecated:: next
        """
        return component in self.components

    def _get_all_components(self) -> Generator[Component, None, None]:
        if self.metadata.component:
            yield from self.metadata.component.get_all_nested_components(include_self=True)
        for c in self.components:
            yield from c.get_all_nested_components(include_self=True)

    def get_vulnerabilities_for_bom_ref(self, bom_ref: BomRef) -> 'SortedSet[Vulnerability]':
        """
        Get all known Vulnerabilities that affect the supplied bom_ref.

        Args:
            bom_ref: `BomRef`

        Returns:
            `SortedSet` of `Vulnerability`

        .. deprecated:: next
            Deprecated without any replacement.
        """
        vulnerabilities: SortedSet[Vulnerability] = SortedSet()
        for v in self.vulnerabilities:
            for target in v.affects:
                if target.ref == bom_ref.value:
                    vulnerabilities.add(v)
        return vulnerabilities

    def has_vulnerabilities(self) -> bool:
        """
        Check whether this Bom has any declared vulnerabilities.

        Returns:
            `bool` - `True` if this Bom has at least one Vulnerability, `False` otherwise.

        .. deprecated:: next
            Deprecated without any replacement.
        """
        return bool(self.vulnerabilities)

    def register_dependency(self, target: Dependable, depends_on: Optional[Iterable[Dependable]] = None) -> None:
        _d = next(filter(lambda _d: _d.ref == target.bom_ref, self.dependencies), None)
        if _d:
            # Dependency Target already registered - but it might have new dependencies to add
            if depends_on:
                _d.dependencies.update(map(lambda _d: Dependency(ref=_d.bom_ref), depends_on))
        else:
            # First time we are seeing this target as a Dependency
            self._dependencies.add(Dependency(
                ref=target.bom_ref,
                dependencies=map(lambda _dep: Dependency(ref=_dep.bom_ref), depends_on) if depends_on else []
            ))

        if depends_on:
            # Ensure dependents are registered with no further dependents in the DependencyGraph
            for _d2 in depends_on:
                self.register_dependency(target=_d2, depends_on=None)

    def urn(self) -> str:
        """
        .. deprecated:: next
            Deprecated without any replacement.
        """
        # idea: have 'serial_number' be a string, and use it instead of this method
        return f'{_BOM_LINK_PREFIX}{self.serial_number}/{self.version}'

    def validate(self) -> bool:
        """
        Perform data-model level validations to make sure we have some known data integrity prior to attempting output
        of this `Bom`

        Returns:
             `bool`

        .. deprecated:: next
            Deprecated without any replacement.
        """
        # !! deprecated function. have this as an part of the normalization process, like the BomRefDiscrimator
        # 0. Make sure all Dependable have a Dependency entry
        if self.metadata.component:
            self.register_dependency(target=self.metadata.component)
        for _c in self.components:
            self.register_dependency(target=_c)
        for _s in self.services:
            self.register_dependency(target=_s)

        # 1. Make sure dependencies are all in this Bom.
        component_bom_refs = set(map(lambda c: c.bom_ref, self._get_all_components())) | set(
            map(lambda s: s.bom_ref, self.services))
        dependency_bom_refs = set(chain(
            (d.ref for d in self.dependencies),
            chain.from_iterable(d.dependencies_as_bom_refs() for d in self.dependencies)
        ))
        dependency_diff = dependency_bom_refs - component_bom_refs
        if len(dependency_diff) > 0:
            raise UnknownComponentDependencyException(
                'One or more Components have Dependency references to Components/Services that are not known in this '
                f'BOM. They are: {dependency_diff}')

        # 2. if root component is set and there are other components: dependencies should exist for the Component
        # this BOM is describing
        if self.metadata.component and len(self.components) > 0 and not any(map(
            lambda d: d.ref == self.metadata.component.bom_ref and len(d.dependencies) > 0,  # type:ignore[union-attr]
            self.dependencies
        )):
            warn(
                f'The Component this BOM is describing {self.metadata.component.purl} has no defined dependencies '
                'which means the Dependency Graph is incomplete - you should add direct dependencies to this '
                '"root" Component to complete the Dependency Graph data.',
                category=UserWarning, stacklevel=1
            )

        # 3. If a LicenseExpression is set, then there must be no other license.
        # see https://github.com/CycloneDX/specification/pull/205
        elem: Union[BomMetaData, Component, Service]
        for elem in chain(  # type:ignore[assignment]
            [self.metadata],
            self.metadata.component.get_all_nested_components(include_self=True) if self.metadata.component else [],
            chain.from_iterable(c.get_all_nested_components(include_self=True) for c in self.components),
            self.services
        ):
            if len(elem.licenses) > 1 and any(isinstance(li, LicenseExpression) for li in elem.licenses):
                raise LicenseExpressionAlongWithOthersException(
                    f'Found LicenseExpression along with others licenses in: {elem!r}')

        return True

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.serial_number, self.version, self.metadata, _ComparableTuple(
                self.components), _ComparableTuple(self.services),
            _ComparableTuple(self.external_references), _ComparableTuple(
                self.dependencies), _ComparableTuple(self.properties),
            _ComparableTuple(self.vulnerabilities),
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Bom):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Bom uuid={self.serial_number}, hash={hash(self)}>'
