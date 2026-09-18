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
from itertools import chain
from typing import TYPE_CHECKING, Any, Optional, Union
from xml.etree.ElementTree import Element  # nosec B405

import py_serializable as serializable
from py_serializable.helpers import BaseHelper
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from ..schema import SchemaVersion
from ..schema.deprecation import SchemaDeprecationWarning1Dot5
from ..schema.schema import SchemaVersion1Dot4, SchemaVersion1Dot5, SchemaVersion1Dot6, SchemaVersion1Dot7
from . import ExternalReference, HashType, _HashTypeRepositorySerializationHelper
from .component import Component
from .service import Service

if TYPE_CHECKING:  # pragma: no cover
    from py_serializable import ObjectMetadataLibrary, ViewType


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Tool:
    """
    This is our internal representation of the `toolType` complex type within the CycloneDX standard.

    Tool(s) are the things used in the creation of the CycloneDX document.

    Tool might be deprecated since CycloneDX 1.5, but it is not deprecated in this library.
    In fact, this library will try to provide a compatibility layer if needed.

    .. note::
        See the CycloneDX Schema for toolType: https://cyclonedx.org/docs/1.7/xml/#type_toolType
    """

    def __init__(
        self, *,
        vendor: Optional[str] = None,
        name: Optional[str] = None,
        version: Optional[str] = None,
        hashes: Optional[Iterable[HashType]] = None,
        external_references: Optional[Iterable[ExternalReference]] = None,
    ) -> None:
        self.vendor = vendor
        self.name = name
        self.version = version
        self.hashes = hashes or ()
        self.external_references = external_references or ()

    @property
    @serializable.xml_sequence(1)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def vendor(self) -> Optional[str]:
        """
        The name of the vendor who created the tool.

        Returns:
            `str` if set else `None`
        """
        return self._vendor

    @vendor.setter
    def vendor(self, vendor: Optional[str]) -> None:
        self._vendor = vendor

    @property
    @serializable.xml_sequence(2)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        The name of the tool.

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
    def version(self) -> Optional[str]:
        """
        The version of the tool.

        Returns:
             `str` if set else `None`
        """
        return self._version

    @version.setter
    def version(self, version: Optional[str]) -> None:
        self._version = version

    @property
    @serializable.type_mapping(_HashTypeRepositorySerializationHelper)
    @serializable.xml_sequence(4)
    def hashes(self) -> 'SortedSet[HashType]':
        """
        The hashes of the tool (if applicable).

        Returns:
            Set of `HashType`
        """
        return self._hashes

    @hashes.setter
    def hashes(self, hashes: Iterable[HashType]) -> None:
        self._hashes = SortedSet(hashes)

    @property
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'reference')
    @serializable.xml_sequence(5)
    def external_references(self) -> 'SortedSet[ExternalReference]':
        """
        External References provides a way to document systems, sites, and information that may be relevant but which
        are not included with the BOM.

        Returns:
            Set of `ExternalReference`
        """
        return self._external_references

    @external_references.setter
    def external_references(self, external_references: Iterable[ExternalReference]) -> None:
        self._external_references = SortedSet(external_references)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.vendor, self.name, self.version,
            _ComparableTuple(self.hashes), _ComparableTuple(self.external_references)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Tool):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Tool):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Tool name={self.name}, version={self.version}, vendor={self.vendor}>'

    @classmethod
    def from_component(cls: type['Tool'], component: 'Component') -> 'Tool':
        return cls(
            vendor=component.group,
            name=component.name,
            version=component.version,
            hashes=component.hashes,
            external_references=component.external_references,
        )

    @classmethod
    def from_service(cls: type['Tool'], service: 'Service') -> 'Tool':
        return cls(
            vendor=service.group,
            name=service.name,
            version=service.version,
            external_references=service.external_references,
        )


class ToolRepository:
    """
    The repository of tool formats
    """

    def __init__(
        self, *,
        components: Optional[Iterable[Component]] = None,
        services: Optional[Iterable[Service]] = None,
        # Deprecated since v1.5
        tools: Optional[Iterable[Tool]] = None
    ) -> None:
        self.components = components or ()
        self.services = services or ()
        # spec-deprecated properties below
        self.tools = tools or ()

    @property
    def components(self) -> 'SortedSet[Component]':
        """
        Returns:
            A SortedSet of Components
        """
        return self._components

    @components.setter
    def components(self, components: Iterable[Component]) -> None:
        self._components = SortedSet(components)

    @property
    def services(self) -> 'SortedSet[Service]':
        """
        Returns:
            A SortedSet of Services
        """
        return self._services

    @services.setter
    def services(self, services: Iterable[Service]) -> None:
        self._services = SortedSet(services)

    @property
    def tools(self) -> 'SortedSet[Tool]':
        return self._tools

    @tools.setter
    def tools(self, tools: Iterable[Tool]) -> None:
        if tools:
            SchemaDeprecationWarning1Dot5._warn('@.tools', '@.components` and `@.services')
        self._tools = SortedSet(tools)

    def __len__(self) -> int:
        return len(self._tools) \
            + len(self._components) \
            + len(self._services)

    def __bool__(self) -> bool:
        return len(self._tools) > 0 \
            or len(self._components) > 0 \
            or len(self._services) > 0

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            _ComparableTuple(self._tools),
            _ComparableTuple(self._components),
            _ComparableTuple(self._services)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ToolRepository):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ToolRepository):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())


class _ToolRepositoryHelper(BaseHelper):

    @staticmethod
    def __all_as_tools(o: ToolRepository) -> 'SortedSet[Tool]':
        # use a set here, so the collection gets deduplicated.
        # use SortedSet set here, so the order stays reproducible.
        return SortedSet(chain(
            o.tools,
            map(Tool.from_component, o.components),
            map(Tool.from_service, o.services),
        ))

    @staticmethod
    def __supports_components_and_services(view: Any) -> bool:
        try:
            return view is not None and view().schema_version_enum >= SchemaVersion.V1_5
        except Exception:  # pragma: no cover
            return False

    @classmethod
    def json_normalize(cls, o: ToolRepository, *,
                       view: Optional[type['ViewType']],
                       **__: Any) -> Any:
        if len(o.tools) > 0 or not cls.__supports_components_and_services(view):
            ts = cls.__all_as_tools(o)
            return tuple(ts) if ts else None
        elem: dict[str, Any] = {}
        if o.components:
            elem['components'] = tuple(o.components)
        if o.services:
            elem['services'] = tuple(o.services)
        return elem or None

    @classmethod
    def json_denormalize(cls, o: Union[list[dict[str, Any]], dict[str, Any]],
                         **__: Any) -> ToolRepository:
        tools = None
        components = None
        services = None
        if isinstance(o, dict):
            components = map(lambda c: Component.from_json(  # type:ignore[attr-defined]
                c), o.get('components', ()))
            services = map(lambda s: Service.from_json(  # type:ignore[attr-defined]
                s), o.get('services', ()))
        elif isinstance(o, Iterable):
            tools = map(lambda t: Tool.from_json(  # type:ignore[attr-defined]
                t), o)
        return ToolRepository(components=components, services=services, tools=tools)

    @classmethod
    def xml_normalize(cls, o: ToolRepository, *,
                      element_name: str,
                      view: Optional[type['ViewType']],
                      xmlns: Optional[str],
                      **__: Any) -> Optional[Element]:
        elem = Element(element_name)
        if len(o.tools) > 0 or not cls.__supports_components_and_services(view):
            elem.extend(
                ti.as_xml(  # type:ignore[attr-defined]
                    view_=view, as_string=False, element_name='tool', xmlns=xmlns)
                for ti in cls.__all_as_tools(o)
            )
        else:
            if o.components:
                elem_c = Element(f'{{{xmlns}}}components' if xmlns else 'components')
                elem_c.extend(
                    ci.as_xml(  # type:ignore[attr-defined]
                        view_=view, as_string=False, element_name='component', xmlns=xmlns)
                    for ci in o.components)
                elem.append(elem_c)
            if o.services:
                elem_s = Element(f'{{{xmlns}}}services' if xmlns else 'services')
                elem_s.extend(
                    si.as_xml(  # type:ignore[attr-defined]
                        view_=view, as_string=False, element_name='service', xmlns=xmlns)
                    for si in o.services)
                elem.append(elem_s)
        return elem \
            if len(elem) > 0 \
            else None

    @classmethod
    def xml_denormalize(cls, o: Element, *,
                        default_ns: Optional[str],
                        prop_info: 'ObjectMetadataLibrary.SerializableProperty',
                        ctx: type[Any],
                        **kwargs: Any) -> ToolRepository:
        ns_map = {'bom': default_ns or ''}
        # Do not iterate over `o` and do not check for expected `.tag` of items.
        # This check could have been done by schema validators before even deserializing.
        tools = None
        components = None
        services = None
        ts = o.findall('bom:tool', ns_map)
        if len(ts) > 0:
            tools = map(lambda t: Tool.from_xml(  # type:ignore[attr-defined]
                t, default_ns), ts)
        else:
            components = map(lambda c: Component.from_xml(  # type:ignore[attr-defined]
                c, default_ns), o.iterfind('./bom:components/bom:component', ns_map))
            services = map(lambda s: Service.from_xml(  # type:ignore[attr-defined]
                s, default_ns), o.iterfind('./bom:services/bom:service', ns_map))
        return ToolRepository(components=components, services=services, tools=tools)
