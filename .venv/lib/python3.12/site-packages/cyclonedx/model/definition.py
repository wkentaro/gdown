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

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Optional, Union

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.bom_ref import bom_ref_from_str as _bom_ref_from_str
from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.model import InvalidCreIdException
from ..exception.serialization import SerializationOfUnexpectedValueException
from . import ExternalReference, Property
from .bom_ref import BomRef

if TYPE_CHECKING:  # pragma: no cover
    from typing import TypeVar

    _T_CreId = TypeVar('_T_CreId', bound='CreId')


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class CreId(serializable.helpers.BaseHelper):
    """
    Helper class that allows us to perform validation on data strings that must conform to
    Common Requirements Enumeration (CRE) identifier(s).

    """

    _VALID_CRE_REGEX = re.compile(r'^CRE:[0-9]+-[0-9]+$')

    def __init__(self, id: str) -> None:
        if CreId._VALID_CRE_REGEX.match(id) is None:
            raise InvalidCreIdException(
                f'Supplied value "{id} does not meet format specification.'
            )
        self._id = id

    @property
    @serializable.json_name('.')
    @serializable.xml_name('.')
    def id(self) -> str:
        return self._id

    @classmethod
    def serialize(cls, o: Any) -> str:
        if isinstance(o, cls):
            return str(o)
        raise SerializationOfUnexpectedValueException(
            f'Attempt to serialize a non-CreId: {o!r}')

    @classmethod
    def deserialize(cls: 'type[_T_CreId]', o: Any) -> '_T_CreId':
        return cls(id=str(o))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CreId):
            return self._id == other._id
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, CreId):
            return self._id < other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f'<CreId {self._id}>'

    def __str__(self) -> str:
        return self._id


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Requirement:
    """
    A requirement comprising a standard.

    .. note::
        See the CycloneDX Schema for hashType:
        https://cyclonedx.org/docs/1.7/json/#definitions_standards_items_requirements
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        identifier: Optional[str] = None,
        title: Optional[str] = None,
        text: Optional[str] = None,
        descriptions: Optional[Iterable[str]] = None,
        open_cre: Optional[Iterable[CreId]] = None,
        parent: Optional[Union[str, BomRef]] = None,
        properties: Optional[Iterable[Property]] = None,
        external_references: Optional[Iterable[ExternalReference]] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.identifier = identifier
        self.title = title
        self.text = text
        self.descriptions = descriptions or ()
        self.open_cre = open_cre or ()
        self.parent = parent
        self.properties = properties or ()
        self.external_references = external_references or ()

    @property
    @serializable.type_mapping(BomRef)
    @serializable.json_name('bom-ref')
    @serializable.xml_name('bom-ref')
    @serializable.xml_attribute()
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the requirement elsewhere in the BOM.
        Every bom-ref MUST be unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(1)
    def identifier(self) -> Optional[str]:
        """
        Returns:
            The identifier of the requirement.
        """
        return self._identifier

    @identifier.setter
    def identifier(self, identifier: Optional[str]) -> None:
        self._identifier = identifier

    @property
    @serializable.xml_sequence(2)
    def title(self) -> Optional[str]:
        """
        Returns:
            The title of the requirement.
        """
        return self._title

    @title.setter
    def title(self, title: Optional[str]) -> None:
        self._title = title

    @property
    @serializable.xml_sequence(3)
    def text(self) -> Optional[str]:
        """
        Returns:
            The text of the requirement.
        """
        return self._text

    @text.setter
    def text(self, text: Optional[str]) -> None:
        self._text = text

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'description')
    @serializable.xml_sequence(4)
    def descriptions(self) -> 'SortedSet[str]':
        """
        Returns:
            A SortedSet of descriptions of the requirement.
        """
        return self._descriptions

    @descriptions.setter
    def descriptions(self, descriptions: Iterable[str]) -> None:
        self._descriptions = SortedSet(descriptions)

    @property
    @serializable.json_name('openCre')
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, 'openCre')
    @serializable.xml_sequence(5)
    def open_cre(self) -> 'SortedSet[CreId]':
        """
        CRE is a structured and standardized framework for uniting security standards and guidelines. CRE links each
        section of a resource to a shared topic identifier (a Common Requirement). Through this shared topic link, all
        resources map to each other. Use of CRE promotes clear and unambiguous communication among stakeholders.

        Returns:
            The Common Requirements Enumeration (CRE) identifier(s).
            CREs must match regular expression: ^CRE:[0-9]+-[0-9]+$
        """
        return self._open_cre

    @open_cre.setter
    def open_cre(self, open_cre: Iterable[CreId]) -> None:
        self._open_cre = SortedSet(open_cre)

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_sequence(6)
    def parent(self) -> Optional[BomRef]:
        """
        Returns:
            The optional bom-ref to a parent requirement. This establishes a hierarchy of requirements. Top-level
            requirements must not define a parent. Only child requirements should define parents.
        """
        return self._parent

    @parent.setter
    def parent(self, parent: Optional[Union[str, BomRef]]) -> None:
        self._parent = _bom_ref_from_str(parent, optional=True)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    @serializable.xml_sequence(7)
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
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'reference')
    @serializable.xml_sequence(8)
    def external_references(self) -> 'SortedSet[ExternalReference]':
        """
        Provides the ability to document external references related to the component or to the project the component
        describes.

        Returns:
            Set of `ExternalReference`
        """
        return self._external_references

    @external_references.setter
    def external_references(self, external_references: Iterable[ExternalReference]) -> None:
        self._external_references = SortedSet(external_references)

    def __comparable_tuple(self) -> _ComparableTuple:
        # all properties are optional - so need to compare all, in hope that one is unique
        return _ComparableTuple((
            self.identifier, self.bom_ref.value,
            self.title, self.text,
            _ComparableTuple(self.descriptions),
            _ComparableTuple(self.open_cre), self.parent, _ComparableTuple(self.properties),
            _ComparableTuple(self.external_references)
        ))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Requirement):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Requirement):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Requirement bom-ref={self._bom_ref}, identifier={self.identifier}, ' \
            f'title={self.title}, text={self.text}, parent={self.parent}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Level:
    """
    Level of compliance for a standard.

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/json/#definitions_standards_items_levels
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        identifier: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        requirements: Optional[Iterable[Union[str, BomRef]]] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.identifier = identifier
        self.title = title
        self.description = description
        self.requirements = requirements or ()

    @property
    @serializable.type_mapping(BomRef)
    @serializable.json_name('bom-ref')
    @serializable.xml_name('bom-ref')
    @serializable.xml_attribute()
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the level elsewhere in the BOM.
        Every bom-ref MUST be unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(1)
    def identifier(self) -> Optional[str]:
        """
        Returns:
            The identifier of the level.
        """
        return self._identifier

    @identifier.setter
    def identifier(self, identifier: Optional[str]) -> None:
        self._identifier = identifier

    @property
    @serializable.xml_sequence(2)
    def title(self) -> Optional[str]:
        """
        Returns:
            The title of the level.
        """
        return self._title

    @title.setter
    def title(self, title: Optional[str]) -> None:
        self._title = title

    @property
    @serializable.xml_sequence(3)
    def description(self) -> Optional[str]:
        """
        Returns:
            The description of the level.
        """
        return self._description

    @description.setter
    def description(self, description: Optional[str]) -> None:
        self._description = description

    @property
    @serializable.xml_sequence(4)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'requirement')
    def requirements(self) -> 'SortedSet[BomRef]':
        """
        Returns:
            A SortedSet of requirements associated with the level.
        """
        return self._requirements

    @requirements.setter
    def requirements(self, requirements: Iterable[Union[str, BomRef]]) -> None:
        self._requirements = SortedSet(map(_bom_ref_from_str,  # type:ignore[arg-type]
                                           requirements))

    def __comparable_tuple(self) -> _ComparableTuple:
        # all properties are optional - so need to compare all, in hope that one is unique
        return _ComparableTuple((
            self.identifier, self.bom_ref.value,
            self.title, self.description,
            _ComparableTuple(self.requirements)
        ))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Level):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Level):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Level bom-ref={self.bom_ref}, identifier={self.identifier}, ' \
            f'title={self.title}, description={self.description}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Standard:
    """
    A standard of regulations, industry or organizational-specific standards, maturity models, best practices,
    or any other requirements.

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_standard
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        name: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        requirements: Optional[Iterable[Requirement]] = None,
        levels: Optional[Iterable[Level]] = None,
        external_references: Optional[Iterable['ExternalReference']] = None
        # TODO: signature
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.name = name
        self.version = version
        self.description = description
        self.owner = owner
        self.requirements = requirements or ()
        self.levels = levels or ()
        self.external_references = external_references or ()
        # TODO: signature

    @property
    @serializable.type_mapping(BomRef)
    @serializable.json_name('bom-ref')
    @serializable.xml_name('bom-ref')
    @serializable.xml_attribute()
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the standard elsewhere in the BOM. Every bom-ref MUST be
        unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.xml_sequence(1)
    def name(self) -> Optional[str]:
        """
        Returns:
            The name of the standard
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    @serializable.xml_sequence(2)
    def version(self) -> Optional[str]:
        """
        Returns:
            The version of the standard
        """
        return self._version

    @version.setter
    def version(self, version: Optional[str]) -> None:
        self._version = version

    @property
    @serializable.xml_sequence(3)
    def description(self) -> Optional[str]:
        """
        Returns:
            The description of the standard
        """
        return self._description

    @description.setter
    def description(self, description: Optional[str]) -> None:
        self._description = description

    @property
    @serializable.xml_sequence(4)
    def owner(self) -> Optional[str]:
        """
        Returns:
            The owner of the standard, often the entity responsible for its release.
        """
        return self._owner

    @owner.setter
    def owner(self, owner: Optional[str]) -> None:
        self._owner = owner

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'requirement')
    @serializable.xml_sequence(5)
    def requirements(self) -> 'SortedSet[Requirement]':
        """
        Returns:
            A SortedSet of requirements comprising the standard.
        """
        return self._requirements

    @requirements.setter
    def requirements(self, requirements: Iterable[Requirement]) -> None:
        self._requirements = SortedSet(requirements)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'level')
    @serializable.xml_sequence(6)
    def levels(self) -> 'SortedSet[Level]':
        """
        Returns:
            A SortedSet of levels associated with the standard. Some standards have different levels of compliance.
        """
        return self._levels

    @levels.setter
    def levels(self, levels: Iterable[Level]) -> None:
        self._levels = SortedSet(levels)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'reference')
    @serializable.xml_sequence(7)
    def external_references(self) -> 'SortedSet[ExternalReference]':
        """
        Returns:
            A SortedSet of external references associated with the standard.
        """
        return self._external_references

    @external_references.setter
    def external_references(self, external_references: Iterable[ExternalReference]) -> None:
        self._external_references = SortedSet(external_references)

    # @property
    # @serializable.xml_sequence(8)
    # # MUST NOT RENDER FOR XML -- this is JSON only
    # def signature(self) -> ...:
    #     ...
    #
    # @signature.setter
    # def levels(self, signature: ...) -> None:
    #     ...

    def __comparable_tuple(self) -> _ComparableTuple:
        # all properties are optional - so need to apply all, in hope that one is unique
        return _ComparableTuple((
            self.name, self.version,
            self.bom_ref.value,
            self.description, self.owner,
            _ComparableTuple(self.requirements), _ComparableTuple(self.levels),
            _ComparableTuple(self.external_references)
        ))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Standard):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Standard):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Standard bom-ref={self.bom_ref}, ' \
            f'name={self.name}, version={self.version}, ' \
            f'description={self.description}, owner={self.owner}>'


@serializable.serializable_class(
    name='definitions',
    ignore_unknown_during_deserialization=True
)
class Definitions:
    """
    The repository for definitions

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_definitionsType
    """

    def __init__(
        self, *,
        standards: Optional[Iterable[Standard]] = None
    ) -> None:
        self.standards = standards or ()

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'standard')
    @serializable.xml_sequence(1)
    def standards(self) -> 'SortedSet[Standard]':
        """
        Returns:
            A SortedSet of Standards
        """
        return self._standards

    @standards.setter
    def standards(self, standards: Iterable[Standard]) -> None:
        self._standards = SortedSet(standards)

    def __bool__(self) -> bool:
        return len(self._standards) > 0

    def __comparable_tuple(self) -> _ComparableTuple:
        # all properties are optional - so need to apply all, in hope that one is unique
        return _ComparableTuple(self._standards)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Definitions):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Definitions):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Definitions standards={self.standards!r} >'
