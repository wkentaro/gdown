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
from enum import Enum
from typing import Any, Optional

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from . import XsUri


@serializable.serializable_enum
class IssueClassification(str, Enum):
    """
    This is our internal representation of the enum `issueClassification`.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_issueClassification
    """
    DEFECT = 'defect'
    ENHANCEMENT = 'enhancement'
    SECURITY = 'security'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class IssueTypeSource:
    """
    This is our internal representation ofa source within the IssueType complex type that can be used in multiple
    places within a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition:
        https://cyclonedx.org/docs/1.7/json/#components_items_pedigree_patches_items_resolves_items_source
    """

    def __init__(
        self, *,
        name: Optional[str] = None,
        url: Optional[XsUri] = None,
    ) -> None:
        self.name = name
        self.url = url

    @property
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        The name of the source. For example "National Vulnerability Database", "NVD", and "Apache".

        Returns:
            `str` if set else `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    def url(self) -> Optional[XsUri]:
        """
        Optional url of the issue documentation as provided by the source.

        Returns:
            `XsUri` if set else `None`
        """
        return self._url

    @url.setter
    def url(self, url: Optional[XsUri]) -> None:
        self._url = url

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.name, self.url
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IssueTypeSource):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, IssueTypeSource):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<IssueTypeSource name={self._name}, url={self.url}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class IssueType:
    """
    This is our internal representation of an IssueType complex type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_issueType
    """

    def __init__(
        self, *,
        type: IssueClassification,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        source: Optional[IssueTypeSource] = None,
        references: Optional[Iterable[XsUri]] = None,
    ) -> None:
        self.type = type
        self.id = id
        self.name = name
        self.description = description
        self.source = source
        self.references = references or []

    @property
    @serializable.xml_attribute()
    def type(self) -> IssueClassification:
        """
        Specifies the type of issue.

        Returns:
            `IssueClassification`
        """
        return self._type

    @type.setter
    def type(self, type: IssueClassification) -> None:
        self._type = type

    @property
    @serializable.xml_sequence(1)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def id(self) -> Optional[str]:
        """
        The identifier of the issue assigned by the source of the issue.

        Returns:
            `str` if set else `None`
        """
        return self._id

    @id.setter
    def id(self, id: Optional[str]) -> None:
        self._id = id

    @property
    @serializable.xml_sequence(2)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        The name of the issue.

        Returns:
            `str` if set else `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    @serializable.xml_sequence(3)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def description(self) -> Optional[str]:
        """
        A description of the issue.

        Returns:
            `str` if set else `None`
        """
        return self._description

    @description.setter
    def description(self, description: Optional[str]) -> None:
        self._description = description

    @property
    @serializable.xml_sequence(4)
    def source(self) -> Optional[IssueTypeSource]:
        """
        The source of this issue.

        Returns:
            `IssueTypeSource` if set else `None`
        """
        return self._source

    @source.setter
    def source(self, source: Optional[IssueTypeSource]) -> None:
        self._source = source

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'url')
    @serializable.xml_sequence(5)
    def references(self) -> 'SortedSet[XsUri]':
        """
        Any reference URLs related to this issue.

        Returns:
            Set of `XsUri`
        """
        return self._references

    @references.setter
    def references(self, references: Iterable[XsUri]) -> None:
        self._references = SortedSet(references)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.type, self.id, self.name, self.description, self.source,
            _ComparableTuple(self.references)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IssueType):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, IssueType):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<IssueType type={self.type}, id={self.id}, name={self.name}>'
