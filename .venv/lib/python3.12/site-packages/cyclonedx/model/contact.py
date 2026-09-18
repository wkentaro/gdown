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


from collections.abc import Iterable
from typing import Any, Optional, Union

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.bom_ref import bom_ref_from_str as _bom_ref_from_str
from .._internal.compare import ComparableTuple as _ComparableTuple
from ..schema.schema import SchemaVersion1Dot5, SchemaVersion1Dot6, SchemaVersion1Dot7
from . import XsUri
from .bom_ref import BomRef


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class PostalAddress:
    """
    This is our internal representation of the `postalAddressType` complex type that can be used in multiple places
    within a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_postalAddressType
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        locality: Optional[str] = None,
        post_office_box_number: Optional[str] = None,
        postal_code: Optional[str] = None,
        street_address: Optional[str] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.country = country
        self.region = region
        self.locality = locality
        self.post_office_box_number = post_office_box_number
        self.postal_code = postal_code
        self.street_address = street_address

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_attribute()
    @serializable.xml_name('bom-ref')
    @serializable.json_name('bom-ref')
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the component elsewhere in the BOM. Every bom-ref MUST be
        unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(10)
    def country(self) -> Optional[str]:
        """
        The country name or the two-letter ISO 3166-1 country code.

        Returns:
             `str` or `None`
        """
        return self._country

    @country.setter
    def country(self, country: Optional[str]) -> None:
        self._country = country

    @property
    @serializable.xml_sequence(20)
    def region(self) -> Optional[str]:
        """
        The region or state in the country. For example, Texas.

        Returns:
             `str` or `None`
        """
        return self._region

    @region.setter
    def region(self, region: Optional[str]) -> None:
        self._region = region

    @property
    @serializable.xml_sequence(30)
    def locality(self) -> Optional[str]:
        """
        The locality or city within the country. For example, Austin.

        Returns:
             `str` or `None`
        """
        return self._locality

    @locality.setter
    def locality(self, locality: Optional[str]) -> None:
        self._locality = locality

    @property
    @serializable.xml_sequence(40)
    def post_office_box_number(self) -> Optional[str]:
        """
        The post office box number. For example, 901.

        Returns:
             `str` or `None`
        """
        return self._post_office_box_number

    @post_office_box_number.setter
    def post_office_box_number(self, post_office_box_number: Optional[str]) -> None:
        self._post_office_box_number = post_office_box_number

    @property
    @serializable.xml_sequence(60)
    def postal_code(self) -> Optional[str]:
        """
        The postal code. For example, 78758.

        Returns:
             `str` or `None`
        """
        return self._postal_code

    @postal_code.setter
    def postal_code(self, postal_code: Optional[str]) -> None:
        self._postal_code = postal_code

    @property
    @serializable.xml_sequence(70)
    def street_address(self) -> Optional[str]:
        """
        The street address. For example, 100 Main Street.

        Returns:
             `str` or `None`
        """
        return self._street_address

    @street_address.setter
    def street_address(self, street_address: Optional[str]) -> None:
        self._street_address = street_address

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.country, self.region, self.locality, self.postal_code,
            self.post_office_box_number,
            self.street_address,
            self._bom_ref.value,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PostalAddress):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, PostalAddress):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<PostalAddress bom-ref={self.bom_ref}, street_address={self.street_address}, country={self.country}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class OrganizationalContact:
    """
    This is our internal representation of the `organizationalContact` complex type that can be used in multiple places
    within a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_organizationalContact
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.name = name
        self.email = email
        self.phone = phone

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.type_mapping(BomRef)
    @serializable.xml_attribute()
    @serializable.xml_name('bom-ref')
    @serializable.json_name('bom-ref')
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the component elsewhere in the BOM. Every bom-ref MUST be
        unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(1)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        Get the name of the contact.

        Returns:
            `str` if set else `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    @serializable.xml_sequence(2)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def email(self) -> Optional[str]:
        """
        Get the email of the contact.

        Returns:
            `str` if set else `None`
        """
        return self._email

    @email.setter
    def email(self, email: Optional[str]) -> None:
        self._email = email

    @property
    @serializable.xml_sequence(3)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def phone(self) -> Optional[str]:
        """
        Get the phone of the contact.

        Returns:
            `str` if set else `None`
        """
        return self._phone

    @phone.setter
    def phone(self, phone: Optional[str]) -> None:
        self._phone = phone

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.name, self.email, self.phone,
            self._bom_ref.value,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OrganizationalContact):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, OrganizationalContact):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<OrganizationalContact name={self.name}, email={self.email}, phone={self.phone}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class OrganizationalEntity:
    """
    This is our internal representation of the `organizationalEntity` complex type that can be used in multiple places
    within a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_organizationalEntity
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        name: Optional[str] = None,
        urls: Optional[Iterable[XsUri]] = None,
        contacts: Optional[Iterable[OrganizationalContact]] = None,
        address: Optional[PostalAddress] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.name = name
        self.address = address
        self.urls = urls or []
        self.contacts = contacts or []

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.type_mapping(BomRef)
    @serializable.xml_attribute()
    @serializable.xml_name('bom-ref')
    @serializable.json_name('bom-ref')
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the component elsewhere in the BOM. Every bom-ref MUST be
        unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(10)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        Get the name of the organization.

        Returns:
            `str` if set else `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(20)
    def address(self) -> Optional[PostalAddress]:
        """
        The physical address (location) of the organization.

        Returns:
            `PostalAddress` or `None`
        """
        return self._address

    @address.setter
    def address(self, address: Optional[PostalAddress]) -> None:
        self._address = address

    @property
    @serializable.json_name('url')
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, 'url')
    @serializable.xml_sequence(30)
    def urls(self) -> 'SortedSet[XsUri]':
        """
        Get a list of URLs of the organization. Multiple URLs are allowed.

        Returns:
            Set of `XsUri`
        """
        return self._urls

    @urls.setter
    def urls(self, urls: Iterable[XsUri]) -> None:
        self._urls = SortedSet(urls)

    @property
    @serializable.json_name('contact')
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, 'contact')
    @serializable.xml_sequence(40)
    def contacts(self) -> 'SortedSet[OrganizationalContact]':
        """
        Get a list of contact person at the organization. Multiple contacts are allowed.

        Returns:
            Set of `OrganizationalContact`
        """
        return self._contacts

    @contacts.setter
    def contacts(self, contacts: Iterable[OrganizationalContact]) -> None:
        self._contacts = SortedSet(contacts)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.name, _ComparableTuple(self.urls), _ComparableTuple(self.contacts),
            self._bom_ref.value,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OrganizationalEntity):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, OrganizationalEntity):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<OrganizationalEntity name={self.name}>'
