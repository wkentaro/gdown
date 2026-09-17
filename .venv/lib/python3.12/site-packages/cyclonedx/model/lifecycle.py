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
    This set of classes represents the lifecycles types in the CycloneDX standard.

.. note::
    Introduced in CycloneDX v1.5

.. note::
    See the CycloneDX Schema for lifecycles: https://cyclonedx.org/docs/1.7/xml/#metadata_lifecycles
"""

from enum import Enum
from json import loads as json_loads
from typing import TYPE_CHECKING, Any, Optional, Union
from xml.etree.ElementTree import Element  # nosec B405

import py_serializable as serializable
from py_serializable.helpers import BaseHelper
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.serialization import CycloneDxDeserializationException

if TYPE_CHECKING:  # pragma: no cover
    from py_serializable import ViewType


@serializable.serializable_enum
class LifecyclePhase(str, Enum):
    """
    Enum object that defines the permissible 'phase' for a Lifecycle according to the CycloneDX schema.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_classification
    """
    DESIGN = 'design'
    PRE_BUILD = 'pre-build'
    BUILD = 'build'
    POST_BUILD = 'post-build'
    OPERATIONS = 'operations'
    DISCOVERY = 'discovery'
    DECOMMISSION = 'decommission'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class PredefinedLifecycle:
    """
    Object that defines pre-defined phases in the product lifecycle.

    .. note::
        See the CycloneDX Schema definition:
        https://cyclonedx.org/docs/1.7/json/#tab-pane_metadata_lifecycles_items_oneOf_i0
    """

    def __init__(self, phase: LifecyclePhase) -> None:
        self._phase = phase

    @property
    def phase(self) -> LifecyclePhase:
        return self._phase

    @phase.setter
    def phase(self, phase: LifecyclePhase) -> None:
        self._phase = phase

    def __hash__(self) -> int:
        return hash(self._phase)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PredefinedLifecycle):
            return self._phase == other._phase
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, PredefinedLifecycle):
            return self._phase < other._phase
        if isinstance(other, NamedLifecycle):
            return True  # put PredefinedLifecycle before any NamedLifecycle
        return NotImplemented

    def __repr__(self) -> str:
        return f'<PredefinedLifecycle phase={self._phase}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class NamedLifecycle:
    """
    Object that defines custom state in the product lifecycle.

    .. note::
        See the CycloneDX Schema definition:
        https://cyclonedx.org/docs/1.7/json/#tab-pane_metadata_lifecycles_items_oneOf_i1
    """

    def __init__(self, name: str, *, description: Optional[str] = None) -> None:
        self._name = name
        self._description = description

    @property
    @serializable.xml_sequence(1)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> str:
        """
        Name of the lifecycle phase.

        Returns:
             `str`
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    @serializable.xml_sequence(2)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def description(self) -> Optional[str]:
        """
        Description of the lifecycle phase.

        Returns:
             `str`
        """
        return self._description

    @description.setter
    def description(self, description: Optional[str]) -> None:
        self._description = description

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self._name, self._description
        ))

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, NamedLifecycle):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, NamedLifecycle):
            return self.__comparable_tuple() < other.__comparable_tuple()
        if isinstance(other, PredefinedLifecycle):
            return False  # put NamedLifecycle after any PredefinedLifecycle
        return NotImplemented

    def __repr__(self) -> str:
        return f'<NamedLifecycle name={self._name}>'


Lifecycle = Union[PredefinedLifecycle, NamedLifecycle]
"""TypeAlias for a union of supported lifecycle models.

- :class:`PredefinedLifecycle`
- :class:`NamedLifecycle`
"""

if TYPE_CHECKING:  # pragma: no cover
    # workaround for https://github.com/python/mypy/issues/5264
    # this code path is taken when static code analysis or documentation tools runs through.
    class LifecycleRepository(SortedSet[Lifecycle]):
        """Collection of :class:`Lifecycle`.

        This is a `set`, not a `list`.  Order MUST NOT matter here.
        """
else:
    class LifecycleRepository(SortedSet):
        """Collection of :class:`Lifecycle`.

        This is a `set`, not a `list`.  Order MUST NOT matter here.
        """


class _LifecycleRepositoryHelper(BaseHelper):
    @classmethod
    def json_normalize(cls, o: LifecycleRepository, *,
                       view: Optional[type['ViewType']],
                       **__: Any) -> Any:
        if len(o) == 0:
            return None
        return [json_loads(li.as_json(  # type:ignore[union-attr]
            view_=view)) for li in o]

    @classmethod
    def json_denormalize(cls, o: list[dict[str, Any]],
                         **__: Any) -> LifecycleRepository:
        repo = LifecycleRepository()
        for li in o:
            if 'phase' in li:
                repo.add(PredefinedLifecycle.from_json(  # type:ignore[attr-defined]
                    li))
            elif 'name' in li:
                repo.add(NamedLifecycle.from_json(  # type:ignore[attr-defined]
                    li))
            else:
                raise CycloneDxDeserializationException(f'unexpected: {li!r}')
        return repo

    @classmethod
    def xml_normalize(cls, o: LifecycleRepository, *,
                      element_name: str,
                      view: Optional[type['ViewType']],
                      xmlns: Optional[str],
                      **__: Any) -> Optional[Element]:
        if len(o) == 0:
            return None
        elem = Element(element_name)
        for li in o:
            elem.append(li.as_xml(  # type:ignore[union-attr]
                view_=view, as_string=False, element_name='lifecycle', xmlns=xmlns))
        return elem

    @classmethod
    def xml_denormalize(cls, o: Element,
                        default_ns: Optional[str],
                        **__: Any) -> LifecycleRepository:
        repo = LifecycleRepository()
        ns_map = {'bom': default_ns or ''}
        # Do not iterate over `o` and do not check for expected `.tag` of items.
        # This check could have been done by schema validators before even deserializing.
        for li in o.iterfind('bom:lifecycle', ns_map):
            if li.find('bom:phase', ns_map) is not None:
                repo.add(PredefinedLifecycle.from_xml(  # type:ignore[attr-defined]
                    li, default_ns))
            elif li.find('bom:name', ns_map) is not None:
                repo.add(NamedLifecycle.from_xml(  # type:ignore[attr-defined]
                    li, default_ns))
            else:
                raise CycloneDxDeserializationException(f'unexpected content: {li!r}')
        return repo
