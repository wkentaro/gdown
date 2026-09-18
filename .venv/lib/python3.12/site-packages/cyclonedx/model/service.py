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


"""
This set of classes represents the data that is possible about known Services.

.. note::
    See the CycloneDX Schema extension definition https://cyclonedx.org/docs/1.7/xml/#type_servicesType
"""


from collections.abc import Iterable
from typing import Any, Optional, Union

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.bom_ref import bom_ref_from_str as _bom_ref_from_str
from .._internal.compare import ComparableTuple as _ComparableTuple
from ..schema.schema import (
    SchemaVersion1Dot3,
    SchemaVersion1Dot4,
    SchemaVersion1Dot5,
    SchemaVersion1Dot6,
    SchemaVersion1Dot7,
)
from . import DataClassification, ExternalReference, Property, XsUri
from .bom_ref import BomRef
from .contact import OrganizationalEntity
from .dependency import Dependable
from .license import License, LicenseRepository, _LicenseRepositorySerializationHelper
from .release_note import ReleaseNotes


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Service(Dependable):
    """
    Class that models the `service` complex type in the CycloneDX schema.

    .. note::
        See the CycloneDX schema: https://cyclonedx.org/docs/1.7/xml/#type_service
    """

    def __init__(
        self, *,
        name: str,
        bom_ref: Optional[Union[str, BomRef]] = None,
        provider: Optional[OrganizationalEntity] = None,
        group: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        endpoints: Optional[Iterable[XsUri]] = None,
        authenticated: Optional[bool] = None,
        x_trust_boundary: Optional[bool] = None,
        data: Optional[Iterable[DataClassification]] = None,
        licenses: Optional[Iterable[License]] = None,
        external_references: Optional[Iterable[ExternalReference]] = None,
        properties: Optional[Iterable[Property]] = None,
        services: Optional[Iterable['Service']] = None,
        release_notes: Optional[ReleaseNotes] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.provider = provider
        self.group = group
        self.name = name
        self.version = version
        self.description = description
        self.endpoints = endpoints or []
        self.authenticated = authenticated
        self.x_trust_boundary = x_trust_boundary
        self.data = data or []
        self.licenses = licenses or []
        self.external_references = external_references or []
        self.services = services or []
        self.release_notes = release_notes
        self.properties = properties or []

    @property
    @serializable.json_name('bom-ref')
    @serializable.type_mapping(BomRef)
    @serializable.xml_attribute()
    @serializable.xml_name('bom-ref')
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the service elsewhere in the BOM. Uniqueness is enforced
        within all elements and children of the root-level bom element.

        Returns:
           `BomRef` unique identifier for this Service
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(1)
    def provider(self) -> Optional[OrganizationalEntity]:
        """
        Get the organization that provides the service.

        Returns:
            `OrganizationalEntity` if set else `None`
        """
        return self._provider

    @provider.setter
    def provider(self, provider: Optional[OrganizationalEntity]) -> None:
        self._provider = provider

    @property
    @serializable.xml_sequence(2)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def group(self) -> Optional[str]:
        """
        The grouping name, namespace, or identifier. This will often be a shortened, single name of the company or
        project that produced the service or domain name. Whitespace and special characters should be avoided.

        Returns:
            `str` if provided else `None`
        """
        return self._group

    @group.setter
    def group(self, group: Optional[str]) -> None:
        self._group = group

    @property
    @serializable.xml_sequence(3)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> str:
        """
        The name of the service. This will often be a shortened, single name of the service.

        Returns:
            `str`
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    @serializable.xml_sequence(4)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def version(self) -> Optional[str]:
        """
        The service version.

        Returns:
            `str` if set else `None`
        """
        return self._version

    @version.setter
    def version(self, version: Optional[str]) -> None:
        self._version = version

    @property
    @serializable.xml_sequence(5)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def description(self) -> Optional[str]:
        """
        Specifies a description for the service.

        Returns:
            `str` if set else `None`
        """
        return self._description

    @description.setter
    def description(self, description: Optional[str]) -> None:
        self._description = description

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'endpoint')
    @serializable.xml_sequence(6)
    def endpoints(self) -> 'SortedSet[XsUri]':
        """
        A list of endpoints URI's this service provides.

        Returns:
            Set of `XsUri`
        """
        return self._endpoints

    @endpoints.setter
    def endpoints(self, endpoints: Iterable[XsUri]) -> None:
        self._endpoints = SortedSet(endpoints)

    @property
    @serializable.xml_sequence(7)
    def authenticated(self) -> Optional[bool]:
        """
        A boolean value indicating if the service requires authentication. A value of true indicates the service
        requires authentication prior to use.

        A value of false indicates the service does not require authentication.

        Returns:
            `bool` if set else `None`
        """
        return self._authenticated

    @authenticated.setter
    def authenticated(self, authenticated: Optional[bool]) -> None:
        self._authenticated = authenticated

    @property
    @serializable.json_name('x-trust-boundary')
    @serializable.xml_name('x-trust-boundary')
    @serializable.xml_sequence(8)
    def x_trust_boundary(self) -> Optional[bool]:
        """
        A boolean value indicating if use of the service crosses a trust zone or boundary. A value of true indicates
        that by using the service, a trust boundary is crossed.

        A value of false indicates that by using the service, a trust boundary is not crossed.

        Returns:
            `bool` if set else `None`
        """
        return self._x_trust_boundary

    @x_trust_boundary.setter
    def x_trust_boundary(self, x_trust_boundary: Optional[bool]) -> None:
        self._x_trust_boundary = x_trust_boundary

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot5)
    # @serializable.xml_sequence(9)
    # def trust_zone(self) -> ...:
    #     ... # since CDX1.5
    #
    # @trust_zone.setter
    # def trust_zone(self, ...) -> None:
    #     ... # since CDX1.5

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'classification')
    @serializable.xml_sequence(10)
    def data(self) -> 'SortedSet[DataClassification]':
        """
        Specifies the data classification.

        Returns:
            Set of `DataClassification`
        """
        # TODO since CDX1.5 also supports `dataflow`, not only `DataClassification`
        return self._data

    @data.setter
    def data(self, data: Iterable[DataClassification]) -> None:
        self._data = SortedSet(data)

    @property
    @serializable.type_mapping(_LicenseRepositorySerializationHelper)
    @serializable.xml_sequence(11)
    def licenses(self) -> LicenseRepository:
        """
        A optional list of statements about how this Service is licensed.

        Returns:
            Set of `LicenseChoice`
        """
        # TODO since CDX1.5 also supports `dataflow`, not only `DataClassification`
        return self._licenses

    @licenses.setter
    def licenses(self, licenses: Iterable[License]) -> None:
        self._licenses = LicenseRepository(licenses)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'reference')
    @serializable.xml_sequence(12)
    def external_references(self) -> 'SortedSet[ExternalReference]':
        """
        Provides the ability to document external references related to the Service.

        Returns:
            Set of `ExternalReference`
        """
        return self._external_references

    @external_references.setter
    def external_references(self, external_references: Iterable[ExternalReference]) -> None:
        self._external_references = SortedSet(external_references)

    @property
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    @serializable.xml_sequence(13)
    def properties(self) -> 'SortedSet[Property]':
        """
        Provides the ability to document properties in a key/value store. This provides flexibility to include data not
        officially supported in the standard without having to use additional namespaces or create extensions.

        Return:
            Set of `Property`
        """
        return self._properties

    @properties.setter
    def properties(self, properties: Iterable[Property]) -> None:
        self._properties = SortedSet(properties)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'service')
    @serializable.xml_sequence(14)
    def services(self) -> "SortedSet['Service']":
        """
        A list of services included or deployed behind the parent service.

        This is not a dependency tree.

        It provides a way to specify a hierarchical representation of service assemblies.

        Returns:
            Set of `Service`
        """
        return self._services

    @services.setter
    def services(self, services: Iterable['Service']) -> None:
        self._services = SortedSet(services)

    @property
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(15)
    def release_notes(self) -> Optional[ReleaseNotes]:
        """
        Specifies optional release notes.

        Returns:
            `ReleaseNotes` or `None`
        """
        return self._release_notes

    @release_notes.setter
    def release_notes(self, release_notes: Optional[ReleaseNotes]) -> None:
        self._release_notes = release_notes

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.group, self.name, self.version,
            self.bom_ref.value,
            self.provider, self.description,
            self.authenticated, _ComparableTuple(self.data), _ComparableTuple(self.endpoints),
            _ComparableTuple(self.external_references), _ComparableTuple(self.licenses),
            _ComparableTuple(self.properties), self.release_notes, _ComparableTuple(self.services),
            self.x_trust_boundary
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Service):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Service):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Service bom-ref={self.bom_ref}, group={self.group}, name={self.name}, version={self.version}>'
