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
License related things
"""

from collections.abc import Iterable
from enum import Enum
from json import loads as json_loads
from typing import TYPE_CHECKING, Any, Optional, Union
from warnings import warn
from xml.etree.ElementTree import Element  # nosec B405

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.bom_ref import bom_ref_from_str as _bom_ref_from_str
from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.model import MutuallyExclusivePropertiesException
from ..exception.serialization import CycloneDxDeserializationException
from ..schema import SchemaVersion
from ..schema.schema import SchemaVersion1Dot5, SchemaVersion1Dot6, SchemaVersion1Dot7
from . import AttachedText, Property, XsUri
from .bom_ref import BomRef


@serializable.serializable_enum
class LicenseAcknowledgement(str, Enum):
    """
    This is our internal representation of the `type_licenseAcknowledgementEnumerationType` ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType:
        https://cyclonedx.org/docs/1.7/xml/#type_licenseAcknowledgementEnumerationType
    """

    CONCLUDED = 'concluded'
    DECLARED = 'declared'


# In an error, the name of the enum was `LicenseExpressionAcknowledgement`.
# Even though this was changed, there might be some downstream usage of this symbol, so we keep it around ...
LicenseExpressionAcknowledgement = LicenseAcknowledgement
"""Deprecated — Alias for :class:`LicenseAcknowledgement`

.. deprecated:: next Import `LicenseAcknowledgement` instead.
    The exported original symbol itself is NOT deprecated - only this import path.
"""


@serializable.serializable_class(
    name='license',
    ignore_unknown_during_deserialization=True
)
class DisjunctiveLicense:
    """
    This is our internal representation of `licenseType` complex type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_licenseType
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        id: Optional[str] = None, name: Optional[str] = None,
        text: Optional[AttachedText] = None, url: Optional[XsUri] = None,
        acknowledgement: Optional[LicenseAcknowledgement] = None,
        properties: Optional[Iterable[Property]] = None,
    ) -> None:
        if not id and not name:
            raise MutuallyExclusivePropertiesException('Either `id` or `name` MUST be supplied')
        if id and name:
            warn(
                'Both `id` and `name` have been supplied - `name` will be ignored!',
                category=RuntimeWarning, stacklevel=1
            )
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self._id = id
        self._name = name if not id else None
        self._text = text
        self._url = url
        self._acknowledgement = acknowledgement
        self._properties = SortedSet(properties or [])

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
    def id(self) -> Optional[str]:
        """
        A SPDX license ID.

        .. note::
          See the list of expected values:
          https://cyclonedx.org/docs/1.7/json/#components_items_licenses_items_license_id

        Returns:
            `str` or `None`
        """
        return self._id

    @id.setter
    def id(self, id: Optional[str]) -> None:
        self._id = id
        if id is not None:
            self._name = None

    @property
    @serializable.xml_sequence(1)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        If SPDX does not define the license used, this field may be used to provide the license name.

        Returns:
            `str` or `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name
        if name is not None:
            self._id = None

    @property
    @serializable.xml_sequence(2)
    def text(self) -> Optional[AttachedText]:
        """
        Specifies the optional full text of the attachment

        Returns:
            `AttachedText` else `None`
        """
        return self._text

    @text.setter
    def text(self, text: Optional[AttachedText]) -> None:
        self._text = text

    @property
    @serializable.xml_sequence(3)
    def url(self) -> Optional[XsUri]:
        """
        The URL to the attachment file. If the attachment is a license or BOM, an externalReference should also be
        specified for completeness.

        Returns:
            `XsUri` or `None`
        """
        return self._url

    @url.setter
    def url(self, url: Optional[XsUri]) -> None:
        self._url = url

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot5)
    # @serializable.view(SchemaVersion1Dot6)
    # @serializable.xml_sequence(5)
    # def licensing(self) -> ...:
    #     ...  # TODO since CDX1.5
    #
    # @licensing.setter
    # def licensing(self, ...) -> None:
    #     ...  # TODO since CDX1.5

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    @serializable.xml_sequence(6)
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
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_attribute()
    def acknowledgement(self) -> Optional[LicenseAcknowledgement]:
        """
        Declared licenses and concluded licenses represent two different stages in the licensing process within
        software development.

        Declared licenses refer to the initial intention of the software authors regarding the
        licensing terms under which their code is released. On the other hand, concluded licenses are the result of a
        comprehensive analysis of the project's codebase to identify and confirm the actual licenses of the components
        used, which may differ from the initially declared licenses. While declared licenses provide an upfront
        indication of the licensing intentions, concluded licenses offer a more thorough understanding of the actual
        licensing within a project, facilitating proper compliance and risk management. Observed licenses are defined
        in evidence.licenses. Observed licenses form the evidence necessary to substantiate a concluded license.

        Returns:
            `LicenseAcknowledgement` or `None`
        """
        return self._acknowledgement

    @acknowledgement.setter
    def acknowledgement(self, acknowledgement: Optional[LicenseAcknowledgement]) -> None:
        self._acknowledgement = acknowledgement

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self._acknowledgement,
            self._id, self._name,
            self._url,
            self._text,
            self._bom_ref.value,
            _ComparableTuple(self._properties),
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DisjunctiveLicense):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, DisjunctiveLicense):
            return self.__comparable_tuple() < other.__comparable_tuple()
        if isinstance(other, LicenseExpression):
            return False  # self after any LicenseExpression
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<License id={self._id!r}, name={self._name!r}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class LicenseExpressionDetails:
    """
    This is our internal representation of the ``licenseExpressionDetailedType`` complex type that specifies the details
    and attributes related to a software license identifier within a CycloneDX BOM document.

    .. note::
        Introduced in CycloneDX v1.7


    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_licenseExpressionDetailedType
    """

    def __init__(
        self, license_identifier: str, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        text: Optional[AttachedText] = None,
        url: Optional[XsUri] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.license_identifier = license_identifier
        self.text = text
        self.url = url

    @property
    @serializable.xml_name('license-identifier')
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    @serializable.xml_attribute()
    def license_identifier(self) -> str:
        """
        A valid SPDX license identifier. Refer to https://spdx.org/specifications for syntax requirements.
        This field serves as the primary key, which uniquely identifies each record.

        Example values:
         - "Apache-2.0",
         - "GPL-3.0-only WITH Classpath-exception-2.0"
         - "LicenseRef-my-custom-license"

        Returns:
            `str`
        """
        return self._license_identifier

    @license_identifier.setter
    def license_identifier(self, license_identifier: str) -> None:
        self._license_identifier = license_identifier

    @property
    @serializable.json_name('bom-ref')
    @serializable.type_mapping(BomRef)
    @serializable.xml_attribute()
    @serializable.xml_name('bom-ref')
    def bom_ref(self) -> BomRef:
        """
        An identifier which can be used to reference the license elsewhere in the BOM. Every bom-ref MUST be
        unique within the BOM.
        Value SHOULD not start with the BOM-Link intro 'urn:cdx:' to avoid conflicts with BOM-Links.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(1)
    def text(self) -> Optional[AttachedText]:
        """
        A way to include the textual content of the license.

        Returns:
            `AttachedText` else `None`
        """
        return self._text

    @text.setter
    def text(self, text: Optional[AttachedText]) -> None:
        self._text = text

    @property
    @serializable.xml_sequence(2)
    def url(self) -> Optional[XsUri]:
        """
        The URL to the license file. If specified, a 'license' externalReference should also be specified for
        completeness.

        Returns:
            `XsUri` or `None`
        """
        return self._url

    @url.setter
    def url(self, url: Optional[XsUri]) -> None:
        self._url = url

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.bom_ref.value, self.license_identifier, self.url, self.text,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LicenseExpressionDetails):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, LicenseExpressionDetails):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<LicenseExpressionDetails bom-ref={self.bom_ref!r}, license_identifier={self.license_identifier}>'


@serializable.serializable_class(
    name='expression',
    ignore_unknown_during_deserialization=True
)
class LicenseExpression:
    """
    This is our internal representation of `licenseType`'s  expression type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition:
        https://cyclonedx.org/docs/1.7/json/#components_items_licenses_items_expression
    """

    def __init__(
        self, value: str, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        acknowledgement: Optional[LicenseAcknowledgement] = None,
        details: Optional[Iterable[LicenseExpressionDetails]] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self._value = value
        self._acknowledgement = acknowledgement
        self.details = details or []

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
    @serializable.xml_name('.')
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    @serializable.json_name('expression')
    def value(self) -> str:
        """
        Value of this LicenseExpression.

        Returns:
             `str`
        """
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self._value = value

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_attribute()
    def acknowledgement(self) -> Optional[LicenseAcknowledgement]:
        """
        Declared licenses and concluded licenses represent two different stages in the licensing process within
        software development.

        Declared licenses refer to the initial intention of the software authors regarding the
        licensing terms under which their code is released. On the other hand, concluded licenses are the result of a
        comprehensive analysis of the project's codebase to identify and confirm the actual licenses of the components
        used, which may differ from the initially declared licenses. While declared licenses provide an upfront
        indication of the licensing intentions, concluded licenses offer a more thorough understanding of the actual
        licensing within a project, facilitating proper compliance and risk management. Observed licenses are defined
        in evidence.licenses. Observed licenses form the evidence necessary to substantiate a concluded license.

        Returns:
            `LicenseAcknowledgement` or `None`
        """
        return self._acknowledgement

    @acknowledgement.setter
    def acknowledgement(self, acknowledgement: Optional[LicenseAcknowledgement]) -> None:
        self._acknowledgement = acknowledgement

    @property
    @serializable.json_name('expressionDetails')
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, child_name='details')
    @serializable.xml_sequence(1)
    def details(self) -> 'SortedSet[LicenseExpressionDetails]':
        """
        Details for parts of the expression.

        Returns:
            Set of `LicenseExpressionDetails`
        """
        return self._details

    @details.setter
    def details(self, details: Iterable[LicenseExpressionDetails]) -> None:
        self._details = SortedSet(details)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self._acknowledgement,
            self._value,
            self._bom_ref.value,
            _ComparableTuple(self.details),
        ))

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LicenseExpression):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, LicenseExpression):
            return self.__comparable_tuple() < other.__comparable_tuple()
        if isinstance(other, DisjunctiveLicense):
            return True  # self before any DisjunctiveLicense
        return NotImplemented

    def __repr__(self) -> str:
        return f'<LicenseExpression value={self._value!r}>'


License = Union[LicenseExpression, DisjunctiveLicense]
"""TypeAlias for a union of supported license models.

- :class:`LicenseExpression`
- :class:`DisjunctiveLicense`
"""

if TYPE_CHECKING:  # pragma: no cover
    # workaround for https://github.com/python/mypy/issues/5264
    # this code path is taken when static code analysis or documentation tools runs through.
    class LicenseRepository(SortedSet[License]):
        """Collection of :class:`License`.

        This is a `set`, not a `list`.  Order MUST NOT matter here.
        If you wanted a certain order, then you should also express whether the items are concat by `AND` or `OR`.
        If you wanted to do so, you should use :class:`LicenseExpression`.

        As a model, this MUST accept multiple :class:`LicenseExpression` along with
        multiple :class:`DisjunctiveLicense`, as this was an accepted in CycloneDX JSON before v1.5.
        So for modeling purposes, this is supported.
        Denormalizers/deserializers will be thankful.
        The normalization/serialization process SHOULD take care of these facts and do what is needed.
        """

else:
    class LicenseRepository(SortedSet):
        """Collection of :class:`License`.

        This is a `set`, not a `list`.  Order MUST NOT matter here.
        If you wanted a certain order, then you should also express whether the items are concat by `AND` or `OR`.
        If you wanted to do so, you should use :class:`LicenseExpression`.

        As a model, this MUST accept multiple :class:`LicenseExpression` along with
        multiple :class:`DisjunctiveLicense`, as this was an accepted in CycloneDX JSON before v1.5.
        So for modeling purposes, this is supported.
        Denormalizers/deserializers will be thankful.
        The normalization/serialization process SHOULD take care of these facts and do what is needed.
        """


class _LicenseRepositorySerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    @staticmethod
    def __supports_expression_details(view: Any) -> bool:
        try:
            return view is not None and view().schema_version_enum >= SchemaVersion.V1_7
        except Exception:  # pragma: no cover
            return False

    @staticmethod
    def __xml_normalize_license_expression_detailed(
        license_expression: LicenseExpression,
        view: Optional[type[serializable.ViewType]],
        xmlns: Optional[str]
    ) -> Element:
        elem: Element = license_expression.as_xml(  # type:ignore[attr-defined]
            view_=view, as_string=False, element_name='expression-detailed', xmlns=xmlns)
        elem.set(f'{{{xmlns}}}expression' if xmlns else 'expression', license_expression.value)
        elem.text = None
        return elem

    @staticmethod
    def __xml_denormalize_license_expression_detailed(
        li: Element,
        default_ns: Optional[str]
    ) -> LicenseExpression:
        expression_value = li.get('expression')
        if not expression_value:
            raise CycloneDxDeserializationException(f'unexpected content: {li!r}')
        license_expression: LicenseExpression = LicenseExpression.from_xml(  # type:ignore[attr-defined]
            li, default_ns)
        license_expression.value = expression_value
        return license_expression

    @classmethod
    def json_normalize(cls, o: LicenseRepository, *,
                       view: Optional[type[serializable.ViewType]],
                       **__: Any) -> Any:
        if len(o) == 0:
            return None
        expression = next((li for li in o if isinstance(li, LicenseExpression)), None)
        if expression:
            # mixed license expression and license? this is an invalid constellation according to schema!
            # see https://github.com/CycloneDX/specification/pull/205
            # but models need to allow it for backwards compatibility with JSON CDX < 1.5
            return [json_loads(expression.as_json(view_=view))]  # type:ignore[attr-defined]
        return [
            {'license': json_loads(
                li.as_json(  # type:ignore[attr-defined]
                    view_=view)
            )}
            for li in o
            if isinstance(li, DisjunctiveLicense)
        ]

    @classmethod
    def json_denormalize(cls, o: list[dict[str, Any]],
                         **__: Any) -> LicenseRepository:
        repo = LicenseRepository()
        for li in o:
            if 'license' in li:
                repo.add(DisjunctiveLicense.from_json(  # type:ignore[attr-defined]
                    li['license']))
            elif 'expression' in li:
                repo.add(LicenseExpression.from_json(  # type:ignore[attr-defined]
                    li
                ))
            else:
                raise CycloneDxDeserializationException(f'unexpected: {li!r}')
        return repo

    @classmethod
    def xml_normalize(cls, o: LicenseRepository, *,
                      element_name: str,
                      view: Optional[type[serializable.ViewType]],
                      xmlns: Optional[str],
                      **__: Any) -> Optional[Element]:
        if len(o) == 0:
            return None
        elem = Element(element_name)
        expression = next((li for li in o if isinstance(li, LicenseExpression)), None)
        if expression:
            # mixed license expression and license? this is an invalid constellation according to schema!
            # see https://github.com/CycloneDX/specification/pull/205
            # but models need to allow it for backwards compatibility with JSON CDX < 1.5
            if expression.details and cls.__supports_expression_details(view):
                elem.append(cls.__xml_normalize_license_expression_detailed(expression, view, xmlns))
            else:
                if expression.details:
                    warn('LicenseExpression details are not supported in schema versions < 1.7; skipping serialization')
                elem.append(expression.as_xml(  # type:ignore[attr-defined]
                    view_=view, as_string=False, element_name='expression', xmlns=xmlns))
        else:
            elem.extend(
                li.as_xml(  # type:ignore[attr-defined]
                    view_=view, as_string=False, element_name='license', xmlns=xmlns)
                for li in o
                if isinstance(li, DisjunctiveLicense)
            )
        return elem

    @classmethod
    def xml_denormalize(cls, o: Element,
                        default_ns: Optional[str],
                        **__: Any) -> LicenseRepository:
        repo = LicenseRepository()
        for li in o:
            tag = li.tag if default_ns is None else li.tag.replace(f'{{{default_ns}}}', '')
            if tag == 'license':
                repo.add(DisjunctiveLicense.from_xml(  # type:ignore[attr-defined]
                    li, default_ns))
            elif tag == 'expression':
                repo.add(LicenseExpression.from_xml(  # type:ignore[attr-defined]
                    li, default_ns))
            elif tag == 'expression-detailed':
                repo.add(cls.__xml_denormalize_license_expression_detailed(li, default_ns))
            else:
                raise CycloneDxDeserializationException(f'unexpected: {li!r}')
        return repo
