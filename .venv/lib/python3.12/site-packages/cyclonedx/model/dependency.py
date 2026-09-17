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


from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Optional

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.serialization import SerializationOfUnexpectedValueException
from .bom_ref import BomRef


class _DependencyRepositorySerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    @classmethod
    def serialize(cls, o: Any) -> list[str]:
        if isinstance(o, (SortedSet, set)):
            return [str(i.ref) for i in o]
        raise SerializationOfUnexpectedValueException(
            f'Attempt to serialize a non-DependencyRepository: {o!r}')

    @classmethod
    def deserialize(cls, o: Any) -> set['Dependency']:
        dependencies = set()
        if isinstance(o, list):
            for v in o:
                dependencies.add(Dependency(ref=BomRef(value=v)))
        return dependencies


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Dependency:
    """
    Models a Dependency within a BOM.

    .. note::
        See https://cyclonedx.org/docs/1.7/xml/#type_dependencyType
    """

    def __init__(self, ref: BomRef, dependencies: Optional[Iterable['Dependency']] = None) -> None:
        self.ref = ref
        self.dependencies = dependencies or []

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_attribute()
    def ref(self) -> BomRef:
        return self._ref

    @ref.setter
    def ref(self, ref: BomRef) -> None:
        self._ref = ref

    @property
    @serializable.json_name('dependsOn')
    @serializable.type_mapping(_DependencyRepositorySerializationHelper)
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, 'dependency')
    def dependencies(self) -> 'SortedSet[Dependency]':
        return self._dependencies

    @dependencies.setter
    def dependencies(self, dependencies: Iterable['Dependency']) -> None:
        self._dependencies = SortedSet(dependencies)

    def dependencies_as_bom_refs(self) -> set[BomRef]:
        return set(map(lambda d: d.ref, self.dependencies))

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.ref, _ComparableTuple(self.dependencies)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Dependency):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Dependency):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Dependency ref={self.ref!r}, targets={len(self.dependencies)}>'


class Dependable(ABC):
    """
    Dependable objects can be part of the Dependency Graph
    """

    @property
    @abstractmethod
    def bom_ref(self) -> BomRef:
        ...  # pragma: no cover
