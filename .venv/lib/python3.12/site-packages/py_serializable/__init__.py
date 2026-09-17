# This file is part of py-serializable
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
# Copyright (c) Paul Horton. All Rights Reserved.

from copy import copy
from decimal import Decimal
from enum import Enum, EnumMeta, unique
from inspect import getfullargspec, getmembers, isclass
from io import StringIO, TextIOBase
from json import JSONEncoder, dumps as json_dumps
from logging import NullHandler, getLogger
from re import compile as re_compile, search as re_search
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from xml.etree.ElementTree import Element, SubElement

from defusedxml import ElementTree as SafeElementTree  # type:ignore[import-untyped]

from .formatters import BaseNameFormatter, CurrentFormatter
from .helpers import BaseHelper
from .xml import xs_normalizedString, xs_token

# `Intersection` is still not implemented, so it is interim replaced by Union for any support
# see section "Intersection" in https://peps.python.org/pep-0483/
# see https://github.com/python/typing/issues/213
from typing import Union as Intersection  # isort: skip

# MUST import the whole thing to get some eval/hacks working for dynamic type detection.
import typing  # noqa: F401 # isort: skip

# !! version is managed by semantic_release
# do not use typing here, or else `semantic_release` might have issues finding the variable
__version__ = '2.1.0'

_logger = getLogger(__name__)
_logger.addHandler(NullHandler())
# make `logger` publicly available, as stable API
logger = _logger
"""
The logger. The thing that captures all this package has to say.
Feel free to modify its level and attach handlers to it.
"""


class ViewType:
    """Base of all views."""
    pass


_F = TypeVar('_F', bound=Callable[..., Any])
_T = TypeVar('_T')
_E = TypeVar('_E', bound=Enum)


@unique
class SerializationType(str, Enum):
    """
    Enum to define the different formats supported for serialization and deserialization.
    """
    JSON = 'JSON'
    XML = 'XML'


# tuple = immutable collection -> immutable = prevent unexpected modifications
_DEFAULT_SERIALIZATION_TYPES: Iterable[SerializationType] = (
    SerializationType.JSON,
    SerializationType.XML,
)


@unique
class XmlArraySerializationType(Enum):
    """
    Enum to differentiate how array-type properties (think Iterables) are serialized.

    Given a ``Warehouse`` has a property ``boxes`` that returns `List[Box]`:

    ``FLAT`` would allow for XML looking like:

    ``
    <warehouse>
        <box>..box 1..</box>
        <box>..box 2..</box>
    </warehouse>
    ``

    ``NESTED`` would allow for XML looking like:

    ``
    <warehouse>
        <boxes>
            <box>..box 1..</box>
            <box>..box 2..</box>
        </boxes>
    </warehouse>
    ``
    """
    FLAT = 1
    NESTED = 2


@unique
class XmlStringSerializationType(Enum):
    """
    Enum to differentiate how string-type properties are serialized.
    """
    STRING = 1
    """
    as raw string.
    see https://www.w3.org/TR/xmlschema-2/#string
    """
    NORMALIZED_STRING = 2
    """
    as `normalizedString`.
    see http://www.w3.org/TR/xmlschema-2/#normalizedString"""
    TOKEN = 3
    """
    as `token`.
    see http://www.w3.org/TR/xmlschema-2/#token"""

    # unimplemented cases
    # - https://www.w3.org/TR/xmlschema-2/#language
    # - https://www.w3.org/TR/xmlschema-2/#NMTOKEN
    # - https://www.w3.org/TR/xmlschema-2/#Name


# region _xs_string_mod_apply

__XS_STRING_MODS: Dict[XmlStringSerializationType, Callable[[str], str]] = {
    XmlStringSerializationType.NORMALIZED_STRING: xs_normalizedString,
    XmlStringSerializationType.TOKEN: xs_token,
}


def _xs_string_mod_apply(v: str, t: Optional[XmlStringSerializationType]) -> str:
    mod = __XS_STRING_MODS.get(t)  # type: ignore[arg-type]
    return mod(v) if mod else v


# endregion _xs_string_mod_apply


def _allow_property_for_view(prop_info: 'ObjectMetadataLibrary.SerializableProperty', value_: Any,
                             view_: Optional[Type[ViewType]]) -> bool:
    # First check Property is part of the View is given
    allow_for_view = False
    if view_:
        if prop_info.views and view_ in prop_info.views:
            allow_for_view = True
        elif not prop_info.views:
            allow_for_view = True
    else:
        if not prop_info.views:
            allow_for_view = True

    # Second check for inclusion of None values
    if value_ is None or (prop_info.is_array and len(value_) < 1):
        if not prop_info.include_none:
            allow_for_view = False
        elif prop_info.include_none and prop_info.include_none_views:
            allow_for_view = False
            for _v, _a in prop_info.include_none_views:
                if _v == view_:
                    allow_for_view = True

    return allow_for_view


class _SerializableJsonEncoder(JSONEncoder):
    """
    ``py_serializable``'s custom implementation of ``JSONEncode``.

    You don't need to call this directly - it is all handled for you by ``py_serializable``.
    """

    def __init__(self, *, skipkeys: bool = False, ensure_ascii: bool = True, check_circular: bool = True,
                 allow_nan: bool = True, sort_keys: bool = False, indent: Optional[int] = None,
                 separators: Optional[Tuple[str, str]] = None, default: Optional[Callable[[Any], Any]] = None,
                 view_: Optional[Type[ViewType]] = None) -> None:
        super().__init__(
            skipkeys=skipkeys, ensure_ascii=ensure_ascii, check_circular=check_circular, allow_nan=allow_nan,
            sort_keys=sort_keys, indent=indent, separators=separators, default=default
        )
        self._view: Optional[Type[ViewType]] = view_

    @property
    def view(self) -> Optional[Type[ViewType]]:
        return self._view

    def default(self, o: Any) -> Any:
        # Enum
        if isinstance(o, Enum):
            return o.value

        # Iterables
        if isinstance(o, (list, set)):
            return list(o)

        # Classes
        if isinstance(o, object):
            d: Dict[Any, Any] = {}
            klass_qualified_name = f'{o.__module__}.{o.__class__.__qualname__}'
            serializable_property_info = ObjectMetadataLibrary.klass_property_mappings.get(klass_qualified_name, {})

            # Handle remaining Properties that will be sub elements
            for k, prop_info in serializable_property_info.items():
                v = getattr(o, k)

                if not _allow_property_for_view(prop_info=prop_info, view_=self._view, value_=v):
                    # Skip as rendering for a view and this Property is not registered form this View
                    continue

                new_key = BaseNameFormatter.decode_handle_python_builtins_and_keywords(name=k)

                if custom_name := prop_info.custom_names.get(SerializationType.JSON):
                    new_key = str(custom_name)

                if CurrentFormatter.formatter:
                    new_key = CurrentFormatter.formatter.encode(property_name=new_key)

                if prop_info.custom_type:
                    if prop_info.is_helper_type():
                        v = prop_info.custom_type.json_normalize(
                            v, view=self._view, prop_info=prop_info, ctx=o.__class__)
                    else:
                        v = prop_info.custom_type(v)
                elif prop_info.is_array:
                    if len(v) > 0:
                        v = list(v)
                    else:
                        v = None
                elif prop_info.is_enum:
                    v = str(v.value)
                elif not prop_info.is_primitive_type():
                    if isinstance(v, Decimal):
                        if prop_info.string_format:
                            v = float(f'{v:{prop_info.string_format}}')
                        else:
                            v = float(v)
                    else:
                        global_klass_name = f'{prop_info.concrete_type.__module__}.{prop_info.concrete_type.__name__}'
                        if global_klass_name not in ObjectMetadataLibrary.klass_mappings:
                            if prop_info.string_format:
                                v = f'{v:{prop_info.string_format}}'
                            else:
                                v = str(v)

                if new_key == '.':
                    return v

                if _allow_property_for_view(prop_info=prop_info, view_=self._view, value_=v):
                    # We need to recheck as values may have been modified above
                    d.update({new_key: v if v is not None else prop_info.get_none_value_for_view(view_=self._view)})

            return d

        # Fallback to default
        super().default(o=o)


class _JsonSerializable(Protocol):

    def as_json(self: Any, view_: Optional[Type[ViewType]] = None) -> str:
        """
        Internal method that is injected into Classes that are annotated for serialization and deserialization by
        ``py_serializable``.
        """
        _logger.debug('Dumping %s to JSON with view: %s...', self, view_)
        return json_dumps(self, cls=_SerializableJsonEncoder, view_=view_)

    @classmethod
    def from_json(cls: Type[_T], data: Dict[str, Any]) -> Optional[_T]:
        """
        Internal method that is injected into Classes that are annotated for serialization and deserialization by
        ``py_serializable``.
        """
        _logger.debug('Rendering JSON to %s...', cls)
        klass_qualified_name = f'{cls.__module__}.{cls.__qualname__}'
        klass = ObjectMetadataLibrary.klass_mappings.get(klass_qualified_name)
        klass_properties = ObjectMetadataLibrary.klass_property_mappings.get(klass_qualified_name, {})

        if klass is None:
            _logger.warning(
                '%s is not a known py_serializable class', klass_qualified_name,
                stacklevel=2)
            return None

        if len(klass_properties) == 1:
            k, only_prop = next(iter(klass_properties.items()))
            if only_prop.custom_names.get(SerializationType.JSON) == '.':
                return cls(**{only_prop.name: data})

        _data = copy(data)
        for k, v in data.items():
            del _data[k]
            decoded_k = CurrentFormatter.formatter.decode(property_name=k)
            if decoded_k in klass.ignore_during_deserialization:
                _logger.debug('Ignoring %s when deserializing %s.%s', k, cls.__module__, cls.__qualname__)
                continue

            new_key = None
            if decoded_k not in klass_properties:
                _allowed_custom_names = {decoded_k, k}
                for p, pi in klass_properties.items():
                    if pi.custom_names.get(SerializationType.JSON) in _allowed_custom_names:
                        new_key = p
            else:
                new_key = decoded_k

            if new_key is None:
                if klass.ignore_unknown_during_deserialization:
                    _logger.debug('Ignoring %s when deserializing %s.%s', k, cls.__module__, cls.__qualname__)
                    continue
                _logger.error('Unexpected key %s/%s in data being serialized to %s.%s',
                              k, decoded_k, cls.__module__, cls.__qualname__)
                raise ValueError(
                    f'Unexpected key {k}/{decoded_k} in data being serialized to {cls.__module__}.{cls.__qualname__}'
                )
            _data[new_key] = v

        for k, v in _data.items():
            prop_info = klass_properties.get(k)
            if not prop_info:
                raise ValueError(f'No Prop Info for {k} in {cls}')

            try:
                if prop_info.custom_type:
                    if prop_info.is_helper_type():
                        _data[k] = prop_info.custom_type.json_denormalize(
                            v, prop_info=prop_info, ctx=klass)
                    else:
                        _data[k] = prop_info.custom_type(v)
                elif prop_info.is_array:
                    items = []
                    for j in v:
                        if not prop_info.is_primitive_type() and not prop_info.is_enum:
                            items.append(prop_info.concrete_type.from_json(data=j))
                        else:
                            items.append(prop_info.concrete_type(j))
                    _data[k] = items  # type: ignore
                elif prop_info.is_enum:
                    _data[k] = prop_info.concrete_type(v)
                elif not prop_info.is_primitive_type():
                    global_klass_name = f'{prop_info.concrete_type.__module__}.{prop_info.concrete_type.__name__}'
                    if global_klass_name in ObjectMetadataLibrary.klass_mappings:
                        _data[k] = prop_info.concrete_type.from_json(data=v)
                    else:
                        if prop_info.concrete_type is Decimal:
                            v = str(v)
                        _data[k] = prop_info.concrete_type(v)
            except AttributeError as e:
                _logger.exception('There was an AttributeError deserializing JSON to %s.\n'
                                  'The Property is: %s\n'
                                  'The Value was: %s\n',
                                  cls, prop_info, v)
                raise AttributeError(
                    f'There was an AttributeError deserializing JSON to {cls} the Property {prop_info}: {e}'
                ) from e

        _logger.debug('Creating %s from %s', cls, _data)

        return cls(**_data)


_XML_BOOL_REPRESENTATIONS_TRUE = ('1', 'true')


class _XmlSerializable(Protocol):

    def as_xml(self: Any, view_: Optional[Type[ViewType]] = None,
               as_string: bool = True, element_name: Optional[str] = None,
               xmlns: Optional[str] = None) -> Union[Element, str]:
        """
        Internal method that is injected into Classes that are annotated for serialization and deserialization by
        ``py_serializable``.
        """
        _logger.debug('Dumping %s to XML with view %s...', self, view_)

        this_e_attributes = {}
        klass_qualified_name = f'{self.__class__.__module__}.{self.__class__.__qualname__}'
        serializable_property_info = {k: v for k, v in sorted(
            ObjectMetadataLibrary.klass_property_mappings.get(klass_qualified_name, {}).items(),
            key=lambda i: i[1].xml_sequence)}

        for k, v in self.__dict__.items():
            # Remove leading _ in key names
            new_key = k[1:]
            if new_key.startswith('_') or '__' in new_key:
                continue
            new_key = BaseNameFormatter.decode_handle_python_builtins_and_keywords(name=new_key)

            if new_key in serializable_property_info:
                prop_info = cast('ObjectMetadataLibrary.SerializableProperty', serializable_property_info.get(new_key))

                if not _allow_property_for_view(prop_info=prop_info, view_=view_, value_=v):
                    # Skip as rendering for a view and this Property is not registered form this View
                    continue

                if prop_info and prop_info.is_xml_attribute:
                    new_key = prop_info.custom_names.get(SerializationType.XML, new_key)
                    if CurrentFormatter.formatter:
                        new_key = CurrentFormatter.formatter.encode(property_name=new_key)

                    if prop_info.custom_type and prop_info.is_helper_type():
                        v = prop_info.custom_type.xml_normalize(
                            v, view=view_, element_name=new_key, xmlns=xmlns, prop_info=prop_info, ctx=self.__class__)
                    elif prop_info.is_enum:
                        v = v.value

                    if v is None:
                        v = prop_info.get_none_value_for_view(view_=view_)
                    if v is None:
                        continue

                    this_e_attributes[_namespace_element_name(new_key, xmlns)] = \
                        _xs_string_mod_apply(str(v), prop_info.xml_string_config)

        element_name = _namespace_element_name(
            element_name if element_name else CurrentFormatter.formatter.encode(self.__class__.__name__),
            xmlns)
        this_e = Element(element_name, this_e_attributes)

        # Handle remaining Properties that will be sub elements
        for k, prop_info in serializable_property_info.items():
            # Skip if rendering for a View and this Property is not designated for this View
            v = getattr(self, k)

            if not _allow_property_for_view(prop_info=prop_info, view_=view_, value_=v):
                # Skip as rendering for a view and this Property is not registered form this View
                continue

            new_key = BaseNameFormatter.decode_handle_python_builtins_and_keywords(name=k)

            if not prop_info:
                raise ValueError(f'{new_key} is not a known Property for {klass_qualified_name}')

            if not prop_info.is_xml_attribute:
                new_key = prop_info.custom_names.get(SerializationType.XML, new_key)

                if v is None:
                    v = prop_info.get_none_value_for_view(view_=view_)
                if v is None:
                    SubElement(this_e, _namespace_element_name(tag_name=new_key, xmlns=xmlns))
                    continue

                if new_key == '.':
                    this_e.text = _xs_string_mod_apply(str(v),
                                                       prop_info.xml_string_config)
                    continue

                if CurrentFormatter.formatter:
                    new_key = CurrentFormatter.formatter.encode(property_name=new_key)
                new_key = _namespace_element_name(new_key, xmlns)

                if prop_info.is_array and prop_info.xml_array_config:
                    _array_type, nested_key = prop_info.xml_array_config
                    nested_key = _namespace_element_name(nested_key, xmlns)
                    if _array_type and _array_type == XmlArraySerializationType.NESTED:
                        nested_e = SubElement(this_e, new_key)
                    else:
                        nested_e = this_e
                    for j in v:
                        if not prop_info.is_primitive_type() and not prop_info.is_enum:
                            nested_e.append(
                                j.as_xml(view_=view_, as_string=False, element_name=nested_key, xmlns=xmlns))
                        elif prop_info.is_enum:
                            SubElement(nested_e, nested_key).text = _xs_string_mod_apply(str(j.value),
                                                                                         prop_info.xml_string_config)
                        elif prop_info.concrete_type in (float, int):
                            SubElement(nested_e, nested_key).text = str(j)
                        elif prop_info.concrete_type is bool:
                            SubElement(nested_e, nested_key).text = str(j).lower()
                        else:
                            # Assume type is str
                            SubElement(nested_e, nested_key).text = _xs_string_mod_apply(str(j),
                                                                                         prop_info.xml_string_config)
                elif prop_info.custom_type:
                    if prop_info.is_helper_type():
                        v_ser = prop_info.custom_type.xml_normalize(
                            v, view=view_, element_name=new_key, xmlns=xmlns, prop_info=prop_info, ctx=self.__class__)
                        if v_ser is None:
                            pass  # skip the element
                        elif isinstance(v_ser, Element):
                            this_e.append(v_ser)
                        else:
                            SubElement(this_e, new_key).text = _xs_string_mod_apply(str(v_ser),
                                                                                    prop_info.xml_string_config)
                    else:
                        SubElement(this_e, new_key).text = _xs_string_mod_apply(str(prop_info.custom_type(v)),
                                                                                prop_info.xml_string_config)
                elif prop_info.is_enum:
                    SubElement(this_e, new_key).text = _xs_string_mod_apply(str(v.value),
                                                                            prop_info.xml_string_config)
                elif not prop_info.is_primitive_type():
                    global_klass_name = f'{prop_info.concrete_type.__module__}.{prop_info.concrete_type.__name__}'
                    if global_klass_name in ObjectMetadataLibrary.klass_mappings:
                        # Handle other Serializable Classes
                        this_e.append(v.as_xml(view_=view_, as_string=False, element_name=new_key, xmlns=xmlns))
                    else:
                        # Handle properties that have a type that is not a Python Primitive (e.g. int, float, str)
                        if prop_info.string_format:
                            SubElement(this_e, new_key).text = _xs_string_mod_apply(f'{v:{prop_info.string_format}}',
                                                                                    prop_info.xml_string_config)
                        else:
                            SubElement(this_e, new_key).text = _xs_string_mod_apply(str(v),
                                                                                    prop_info.xml_string_config)
                elif prop_info.concrete_type in (float, int):
                    SubElement(this_e, new_key).text = str(v)
                elif prop_info.concrete_type is bool:
                    SubElement(this_e, new_key).text = str(v).lower()
                else:
                    # Assume type is str
                    SubElement(this_e, new_key).text = _xs_string_mod_apply(str(v),
                                                                            prop_info.xml_string_config)

        if as_string:
            return cast(Element, SafeElementTree.tostring(this_e, 'unicode'))
        else:
            return this_e

    @classmethod
    def from_xml(cls: Type[_T], data: Union[TextIOBase, Element],
                 default_namespace: Optional[str] = None) -> Optional[_T]:
        """
        Internal method that is injected into Classes that are annotated for serialization and deserialization by
        ``py_serializable``.
        """
        _logger.debug('Rendering XML from %s to %s...', type(data), cls)
        klass = ObjectMetadataLibrary.klass_mappings.get(f'{cls.__module__}.{cls.__qualname__}')
        if klass is None:
            _logger.warning('%s.%s is not a known py_serializable class', cls.__module__, cls.__qualname__,
                            stacklevel=2)
            return None

        klass_properties = ObjectMetadataLibrary.klass_property_mappings.get(f'{cls.__module__}.{cls.__qualname__}', {})

        if isinstance(data, TextIOBase):
            data = cast(Element, SafeElementTree.fromstring(data.read()))

        if default_namespace is None:
            _namespaces = dict(node for _, node in
                               SafeElementTree.iterparse(StringIO(SafeElementTree.tostring(data, 'unicode')),
                                                         events=['start-ns']))
            default_namespace = (re_compile(r'^\{(.*?)\}.').search(data.tag) or (None, _namespaces.get('')))[1]

        if default_namespace is None:
            def strip_default_namespace(s: str) -> str:
                return s
        else:
            def strip_default_namespace(s: str) -> str:
                return s.replace(f'{{{default_namespace}}}', '')

        _data: Dict[str, Any] = {}

        # Handle attributes on the root element if there are any
        for k, v in data.attrib.items():
            decoded_k = CurrentFormatter.formatter.decode(strip_default_namespace(k))
            if decoded_k in klass.ignore_during_deserialization:
                _logger.debug('Ignoring %s when deserializing %s.%s', decoded_k, cls.__module__, cls.__qualname__)
                continue

            if decoded_k not in klass_properties:
                for p, pi in klass_properties.items():
                    if pi.custom_names.get(SerializationType.XML) == decoded_k:
                        decoded_k = p

            prop_info = klass_properties.get(decoded_k)
            if not prop_info:
                if klass.ignore_unknown_during_deserialization:
                    _logger.debug('Ignoring %s when deserializing %s.%s', decoded_k, cls.__module__, cls.__qualname__)
                    continue
                raise ValueError(f'Non-primitive types not supported from XML Attributes - see {decoded_k} for '
                                 f'{cls.__module__}.{cls.__qualname__} which has Prop Metadata: {prop_info}')

            if prop_info.xml_string_config:
                v = _xs_string_mod_apply(v, prop_info.xml_string_config)

            if prop_info.custom_type and prop_info.is_helper_type():
                _data[decoded_k] = prop_info.custom_type.xml_deserialize(v)
            elif prop_info.is_enum:
                _data[decoded_k] = prop_info.concrete_type(v)
            elif prop_info.is_primitive_type():
                _data[decoded_k] = prop_info.concrete_type(v)
            else:
                raise ValueError(f'Non-primitive types not supported from XML Attributes - see {decoded_k}')

        # Handle Node text content
        if data.text:
            for p, pi in klass_properties.items():
                if pi.custom_names.get(SerializationType.XML) == '.':
                    _data[p] = _xs_string_mod_apply(data.text.strip(), pi.xml_string_config)

        # Handle Sub-Elements
        for child_e in data:
            decoded_k = CurrentFormatter.formatter.decode(strip_default_namespace(child_e.tag))

            if decoded_k not in klass_properties:
                for p, pi in klass_properties.items():
                    if pi.xml_array_config:
                        array_type, nested_name = pi.xml_array_config
                        if nested_name == strip_default_namespace(child_e.tag):
                            decoded_k = p

            if decoded_k in klass.ignore_during_deserialization:
                _logger.debug('Ignoring %s when deserializing %s.%s', decoded_k, cls.__module__, cls.__qualname__)
                continue

            if decoded_k not in klass_properties:
                for p, pi in klass_properties.items():
                    if pi.xml_array_config:
                        array_type, nested_name = pi.xml_array_config
                        if nested_name == decoded_k:
                            if array_type == XmlArraySerializationType.FLAT:
                                decoded_k = p
                            else:
                                decoded_k = '____SKIP_ME____'
                    elif pi.custom_names.get(SerializationType.XML) == decoded_k:
                        decoded_k = p

            if decoded_k == '____SKIP_ME____':
                continue

            prop_info = klass_properties.get(decoded_k)
            if not prop_info:
                if klass.ignore_unknown_during_deserialization:
                    _logger.debug('Ignoring %s when deserializing %s.%s', decoded_k, cls.__module__, cls.__qualname__)
                    continue
                _logger.error('Unexpected key %s/%s in data being serialized to %s.%s',
                              k, decoded_k, cls.__module__, cls.__qualname__)
                raise ValueError(f'{decoded_k} is not a known Property for {cls.__module__}.{cls.__qualname__}')

            try:
                _logger.debug('Handling %s', prop_info)

                if child_e.text:
                    child_e.text = _xs_string_mod_apply(child_e.text, prop_info.xml_string_config)

                if prop_info.is_array and prop_info.xml_array_config:
                    array_type, nested_name = prop_info.xml_array_config

                    if decoded_k not in _data:
                        _data[decoded_k] = []

                    if array_type == XmlArraySerializationType.NESTED:
                        for sub_child_e in child_e:
                            if sub_child_e.text:
                                sub_child_e.text = _xs_string_mod_apply(sub_child_e.text,
                                                                        prop_info.xml_string_config)
                            if not prop_info.is_primitive_type() and not prop_info.is_enum:
                                _data[decoded_k].append(prop_info.concrete_type.from_xml(
                                    data=sub_child_e, default_namespace=default_namespace)
                                )
                            else:
                                _data[decoded_k].append(prop_info.concrete_type(sub_child_e.text))
                    else:
                        if not prop_info.is_primitive_type() and not prop_info.is_enum:
                            _data[decoded_k].append(prop_info.concrete_type.from_xml(
                                data=child_e, default_namespace=default_namespace)
                            )
                        elif prop_info.custom_type:
                            if prop_info.is_helper_type():
                                _data[decoded_k] = prop_info.custom_type.xml_denormalize(
                                    child_e, default_ns=default_namespace, prop_info=prop_info, ctx=klass)
                            else:
                                _data[decoded_k] = prop_info.custom_type(child_e.text)
                        else:
                            _data[decoded_k].append(prop_info.concrete_type(child_e.text))
                elif prop_info.custom_type:
                    if prop_info.is_helper_type():
                        _data[decoded_k] = prop_info.custom_type.xml_denormalize(
                            child_e, default_ns=default_namespace, prop_info=prop_info, ctx=klass)
                    else:
                        _data[decoded_k] = prop_info.custom_type(child_e.text)
                elif prop_info.is_enum:
                    _data[decoded_k] = prop_info.concrete_type(child_e.text)
                elif not prop_info.is_primitive_type():
                    global_klass_name = f'{prop_info.concrete_type.__module__}.{prop_info.concrete_type.__name__}'
                    if global_klass_name in ObjectMetadataLibrary.klass_mappings:
                        _data[decoded_k] = prop_info.concrete_type.from_xml(
                            data=child_e, default_namespace=default_namespace
                        )
                    else:
                        _data[decoded_k] = prop_info.concrete_type(child_e.text)
                else:
                    if prop_info.concrete_type == bool:
                        _data[decoded_k] = str(child_e.text) in _XML_BOOL_REPRESENTATIONS_TRUE
                    else:
                        _data[decoded_k] = prop_info.concrete_type(child_e.text)
            except AttributeError as e:
                _logger.exception('There was an AttributeError deserializing JSON to %s.\n'
                                  'The Property is: %s\n'
                                  'The Value was: %s\n',
                                  cls, prop_info, v)
                raise AttributeError('There was an AttributeError deserializing XML '
                                     f'to {cls} the Property {prop_info}: {e}') from e

        _logger.debug('Creating %s from %s', cls, _data)

        if len(_data) == 0:
            return None

        return cls(**_data)


def _namespace_element_name(tag_name: str, xmlns: Optional[str]) -> str:
    if tag_name.startswith('{'):
        return tag_name
    if xmlns:
        return f'{{{xmlns}}}{tag_name}'
    return tag_name


class ObjectMetadataLibrary:
    """namespace-like

    The core Class in ``py_serializable`` that is used to record all metadata about classes that you annotate for
    serialization and deserialization.
    """
    _deferred_property_type_parsing: Dict[str, Set['ObjectMetadataLibrary.SerializableProperty']] = {}
    _klass_views: Dict[str, Type[ViewType]] = {}
    _klass_property_array_config: Dict[str, Tuple[XmlArraySerializationType, str]] = {}
    _klass_property_string_config: Dict[str, Optional[XmlStringSerializationType]] = {}
    _klass_property_attributes: Set[str] = set()
    _klass_property_include_none: Dict[str, Set[Tuple[Type[ViewType], Any]]] = {}
    _klass_property_names: Dict[str, Dict[SerializationType, str]] = {}
    _klass_property_string_formats: Dict[str, str] = {}
    _klass_property_types: Dict[str, type] = {}
    _klass_property_views: Dict[str, Set[Type[ViewType]]] = {}
    _klass_property_xml_sequence: Dict[str, int] = {}
    custom_enum_klasses: Set[Type[Enum]] = set()
    klass_mappings: Dict[str, 'ObjectMetadataLibrary.SerializableClass'] = {}
    klass_property_mappings: Dict[str, Dict[str, 'ObjectMetadataLibrary.SerializableProperty']] = {}

    class SerializableClass:
        """
        Internal model class used to represent metadata we hold about Classes that are being included in
        (de-)serialization.
        """

        def __init__(self, *, klass: type, custom_name: Optional[str] = None,
                     serialization_types: Optional[Iterable[SerializationType]] = None,
                     ignore_during_deserialization: Optional[Iterable[str]] = None,
                     ignore_unknown_during_deserialization: bool = False) -> None:
            # param ignore_unknown_during_deserialization defaults to False, since we deserialize from JSON/XML
            # and both have mechanisms for arbitrary content that might be intended to pass to the constructors:
            # - JSON has `additionalProperties:true`
            # - XML has `##any` and `##other`
            self._name = str(klass.__name__)
            self._klass = klass
            self._custom_name = custom_name
            if serialization_types is None:
                serialization_types = _DEFAULT_SERIALIZATION_TYPES
            self._serialization_types = serialization_types
            self._ignore_during_deserialization = set(ignore_during_deserialization or ())
            self._ignore_unknown_during_deserialization = ignore_unknown_during_deserialization

        @property
        def name(self) -> str:
            return self._name

        @property
        def klass(self) -> type:
            return self._klass

        @property
        def custom_name(self) -> Optional[str]:
            return self._custom_name

        @property
        def serialization_types(self) -> Iterable[SerializationType]:
            return self._serialization_types

        @property
        def ignore_during_deserialization(self) -> Set[str]:
            return self._ignore_during_deserialization

        @property
        def ignore_unknown_during_deserialization(self) -> bool:
            return self._ignore_unknown_during_deserialization

        def __repr__(self) -> str:
            return f'<s.oml.SerializableClass name={self.name}>'

    class SerializableProperty:
        """
        Internal model class used to represent metadata we hold about Properties that are being included in
        (de-)serialization.
        """

        _ARRAY_TYPES = {'List': List, 'Set': Set, 'SortedSet': Set}
        _SORTED_CONTAINERS_TYPES = {'SortedList': List, 'SortedSet': Set}
        _PRIMITIVE_TYPES = (bool, int, float, str)

        _DEFAULT_XML_SEQUENCE = 100

        def __init__(self, *,
                     prop_name: str, prop_type: Any, custom_names: Dict[SerializationType, str],
                     custom_type: Optional[Any] = None,
                     include_none_config: Optional[Set[Tuple[Type[ViewType], Any]]] = None,
                     is_xml_attribute: bool = False, string_format_: Optional[str] = None,
                     views: Optional[Iterable[Type[ViewType]]] = None,
                     xml_array_config: Optional[Tuple[XmlArraySerializationType, str]] = None,
                     xml_string_config: Optional[XmlStringSerializationType] = None,
                     xml_sequence_: Optional[int] = None) -> None:

            self._name = prop_name
            self._custom_names = custom_names
            self._type_ = None
            self._concrete_type = None
            self._is_array = False
            self._is_enum = False
            self._is_optional = False
            self._custom_type = custom_type
            if include_none_config is not None:
                self._include_none = True
                self._include_none_views = include_none_config
            else:
                self._include_none = False
                self._include_none_views = set()
            self._is_xml_attribute = is_xml_attribute
            self._string_format = string_format_
            self._views = set(views or ())
            self._xml_array_config = xml_array_config
            self._xml_string_config = xml_string_config
            self._xml_sequence = xml_sequence_ or self._DEFAULT_XML_SEQUENCE

            self._deferred_type_parsing = False
            self._parse_type(type_=prop_type)

        @property
        def name(self) -> str:
            return self._name

        @property
        def custom_names(self) -> Dict[SerializationType, str]:
            return self._custom_names

        def custom_name(self, serialization_type: SerializationType) -> Optional[str]:
            return self.custom_names.get(serialization_type)

        @property
        def type_(self) -> Any:
            return self._type_

        @property
        def concrete_type(self) -> Any:
            return self._concrete_type

        @property
        def custom_type(self) -> Optional[Any]:
            return self._custom_type

        @property
        def include_none(self) -> bool:
            return self._include_none

        @property
        def include_none_views(self) -> Set[Tuple[Type[ViewType], Any]]:
            return self._include_none_views

        def include_none_for_view(self, view_: Type[ViewType]) -> bool:
            for _v, _a in self._include_none_views:
                if _v == view_:
                    return True

            return False

        def get_none_value_for_view(self, view_: Optional[Type[ViewType]]) -> Any:
            if view_:
                for _v, _a in self._include_none_views:
                    if _v == view_:
                        return _a
            return None

        @property
        def is_xml_attribute(self) -> bool:
            return self._is_xml_attribute

        @property
        def string_format(self) -> Optional[str]:
            return self._string_format

        @property
        def views(self) -> Set[Type[ViewType]]:
            return self._views

        @property
        def xml_array_config(self) -> Optional[Tuple[XmlArraySerializationType, str]]:
            return self._xml_array_config

        @property
        def is_array(self) -> bool:
            return self._is_array

        @property
        def xml_string_config(self) -> Optional[XmlStringSerializationType]:
            return self._xml_string_config

        @property
        def is_enum(self) -> bool:
            return self._is_enum

        @property
        def is_optional(self) -> bool:
            return self._is_optional

        @property
        def xml_sequence(self) -> int:
            return self._xml_sequence

        def get_none_value(self, view_: Optional[Type[ViewType]] = None) -> Any:
            if not self.include_none:
                raise ValueError('No None Value for property that is not include_none')

        def is_helper_type(self) -> bool:
            ct = self.custom_type
            return isclass(ct) and issubclass(ct, BaseHelper)

        def is_primitive_type(self) -> bool:
            return self.concrete_type in self._PRIMITIVE_TYPES

        def parse_type_deferred(self) -> None:
            self._parse_type(type_=self._type_)

        def _parse_type(self, type_: Any) -> None:
            self._type_ = type_ = self._handle_forward_ref(t_=type_)

            if type(type_) is str:
                type_to_parse = str(type_)
                # Handle types that are quoted strings e.g. 'SortedSet[MyObject]' or 'Optional[SortedSet[MyObject]]'
                if type_to_parse.startswith('typing.Optional['):
                    self._is_optional = True
                    type_to_parse = type_to_parse[16:-1]
                elif type_to_parse.startswith('Optional['):
                    self._is_optional = True
                    type_to_parse = type_to_parse[9:-1]

                match = re_search(r"^(?P<array_type>[\w.]+)\[['\"]?(?P<array_of>\w+)['\"]?]$", type_to_parse)
                if match:
                    results = match.groupdict()
                    if results.get('array_type') in self._SORTED_CONTAINERS_TYPES:
                        mapped_array_type = self._SORTED_CONTAINERS_TYPES.get(str(results.get('array_type')))
                        self._is_array = True
                        try:
                            # Will load any class already loaded assuming fully qualified name
                            self._type_ = eval(f'{mapped_array_type}[{results.get("array_of")}]')
                            self._concrete_type = eval(str(results.get('array_of')))
                        except NameError:
                            # Likely a class that is missing its fully qualified name
                            _k: Optional[Any] = None
                            for _k_name, _oml_sc in ObjectMetadataLibrary.klass_mappings.items():
                                if _oml_sc.name == results.get('array_of'):
                                    _k = _oml_sc.klass

                            if _k is None:
                                # Perhaps a custom ENUM?
                                for _enum_klass in ObjectMetadataLibrary.custom_enum_klasses:
                                    if _enum_klass.__name__ == results.get('array_of'):
                                        _k = _enum_klass

                            if _k is None:
                                self._type_ = type_  # type: ignore
                                self._deferred_type_parsing = True
                                ObjectMetadataLibrary.defer_property_type_parsing(
                                    prop=self, klasses=[str(results.get('array_of'))]
                                )
                                return

                            self._type_ = mapped_array_type[_k]  # type: ignore
                            self._concrete_type = _k  # type: ignore

                    elif results.get('array_type', '').replace('typing.', '') in self._ARRAY_TYPES:
                        mapped_array_type = self._ARRAY_TYPES.get(
                            str(results.get('array_type', '').replace('typing.', ''))
                        )
                        self._is_array = True
                        try:
                            # Will load any class already loaded assuming fully qualified name
                            self._type_ = eval(f'{mapped_array_type}[{results.get("array_of")}]')
                            self._concrete_type = eval(str(results.get('array_of')))
                        except NameError:
                            # Likely a class that is missing its fully qualified name
                            _l: Optional[Any] = None
                            for _k_name, _oml_sc in ObjectMetadataLibrary.klass_mappings.items():
                                if _oml_sc.name == results.get('array_of'):
                                    _l = _oml_sc.klass

                            if _l is None:
                                # Perhaps a custom ENUM?
                                for _enum_klass in ObjectMetadataLibrary.custom_enum_klasses:
                                    if _enum_klass.__name__ == results.get('array_of'):
                                        _l = _enum_klass

                            if _l is None:
                                self._type_ = type_  # type: ignore
                                self._deferred_type_parsing = True
                                ObjectMetadataLibrary.defer_property_type_parsing(
                                    prop=self, klasses=[str(results.get('array_of'))]
                                )
                                return

                            self._type_ = mapped_array_type[_l]  # type: ignore
                            self._concrete_type = _l  # type: ignore
                else:
                    raise ValueError(f'Unable to handle Property with declared type: {type_}')
            else:
                # Handle real types
                if len(getattr(self.type_, '__args__', ())) > 1:
                    # Is this an Optional Property
                    self._is_optional = type(None) in self.type_.__args__

                if self.is_optional:
                    t, n = self.type_.__args__
                    if getattr(t, '_name', None) in self._ARRAY_TYPES:
                        self._is_array = True
                        t, = t.__args__
                    self._concrete_type = t
                else:
                    if getattr(self.type_, '_name', None) in self._ARRAY_TYPES:
                        self._is_array = True
                        self._concrete_type, = self.type_.__args__
                    else:
                        self._concrete_type = self.type_

            # Handle Enums
            if issubclass(type(self.concrete_type), EnumMeta):
                self._is_enum = True

            # Ensure marked as not deferred
            if self._deferred_type_parsing:
                self._deferred_type_parsing = False

        def _handle_forward_ref(self, t_: Any) -> Any:
            if 'ForwardRef' in str(t_):
                return str(t_).replace("ForwardRef('", '"').replace("')", '"')
            else:
                return t_

        def __eq__(self, other: Any) -> bool:
            if isinstance(other, ObjectMetadataLibrary.SerializableProperty):
                return hash(other) == hash(self)
            return False

        def __lt__(self, other: Any) -> bool:
            if isinstance(other, ObjectMetadataLibrary.SerializableProperty):
                return self.xml_sequence < other.xml_sequence
            return NotImplemented

        def __hash__(self) -> int:
            return hash((
                self.concrete_type, tuple(self.custom_names), self.custom_type, self.is_array, self.is_enum,
                self.is_optional, self.is_xml_attribute, self.name, self.type_,
                tuple(self.xml_array_config) if self.xml_array_config else None, self.xml_sequence
            ))

        def __repr__(self) -> str:
            return f'<s.oml.SerializableProperty name={self.name}, custom_names={self.custom_names}, ' \
                f'array={self.is_array}, enum={self.is_enum}, optional={self.is_optional}, ' \
                f'c_type={self.concrete_type}, type={self.type_}, custom_type={self.custom_type}, ' \
                f'xml_attr={self.is_xml_attribute}, xml_sequence={self.xml_sequence}>'

    @classmethod
    def defer_property_type_parsing(cls, prop: 'ObjectMetadataLibrary.SerializableProperty',
                                    klasses: Iterable[str]) -> None:
        for _k in klasses:
            if _k not in ObjectMetadataLibrary._deferred_property_type_parsing:
                ObjectMetadataLibrary._deferred_property_type_parsing[_k] = set()
            ObjectMetadataLibrary._deferred_property_type_parsing[_k].add(prop)

    @classmethod
    def is_klass_serializable(cls, klass: Any) -> bool:
        if type(klass) is Type:
            return f'{klass.__module__}.{klass.__name__}' in cls.klass_mappings  # type: ignore
        return klass in cls.klass_mappings

    @classmethod
    def is_property(cls, o: Any) -> bool:
        return isinstance(o, property)

    @classmethod
    def register_enum(cls, klass: Type[_E]) -> Type[_E]:
        cls.custom_enum_klasses.add(klass)
        return klass

    @classmethod
    def register_klass(cls, klass: Type[_T], custom_name: Optional[str],
                       serialization_types: Iterable[SerializationType],
                       ignore_during_deserialization: Optional[Iterable[str]] = None,
                       ignore_unknown_during_deserialization: bool = False
                       ) -> Intersection[Type[_T], Type[_JsonSerializable], Type[_XmlSerializable]]:
        # param ignore_unknown_during_deserialization defaults to False, since we deserialize from JSON/XML
        # and both have mechanisms for arbitrary content that might be intended to pass to the constructors:
        # - JSON has `additionalProperties:true`
        # - XML has `##any` and `##other`
        if cls.is_klass_serializable(klass=klass):
            return klass

        cls.klass_mappings[f'{klass.__module__}.{klass.__qualname__}'] = ObjectMetadataLibrary.SerializableClass(
            klass=klass, serialization_types=serialization_types,
            ignore_during_deserialization=ignore_during_deserialization,
            ignore_unknown_during_deserialization=ignore_unknown_during_deserialization
        )

        qualified_class_name = f'{klass.__module__}.{klass.__qualname__}'
        cls.klass_property_mappings[qualified_class_name] = {}
        _logger.debug('Registering Class %s with custom name %s', qualified_class_name, custom_name)
        for name, o in getmembers(klass, ObjectMetadataLibrary.is_property):
            qualified_property_name = f'{qualified_class_name}.{name}'
            prop_arg_specs = getfullargspec(o.fget)

            cls.klass_property_mappings[qualified_class_name][name] = ObjectMetadataLibrary.SerializableProperty(
                prop_name=name,
                custom_names=ObjectMetadataLibrary._klass_property_names.get(qualified_property_name, {}),
                prop_type=prop_arg_specs.annotations.get('return'),
                custom_type=ObjectMetadataLibrary._klass_property_types.get(qualified_property_name),
                include_none_config=ObjectMetadataLibrary._klass_property_include_none.get(qualified_property_name),
                is_xml_attribute=(qualified_property_name in ObjectMetadataLibrary._klass_property_attributes),
                string_format_=ObjectMetadataLibrary._klass_property_string_formats.get(qualified_property_name),
                views=ObjectMetadataLibrary._klass_property_views.get(qualified_property_name),
                xml_array_config=ObjectMetadataLibrary._klass_property_array_config.get(qualified_property_name),
                xml_string_config=ObjectMetadataLibrary._klass_property_string_config.get(qualified_property_name),
                xml_sequence_=ObjectMetadataLibrary._klass_property_xml_sequence.get(
                    qualified_property_name,
                    ObjectMetadataLibrary.SerializableProperty._DEFAULT_XML_SEQUENCE)
            )

        if SerializationType.JSON in serialization_types:
            klass.as_json = _JsonSerializable.as_json  # type:ignore[attr-defined]
            klass.from_json = classmethod(_JsonSerializable.from_json.__func__)  # type:ignore[attr-defined]

        if SerializationType.XML in serialization_types:
            klass.as_xml = _XmlSerializable.as_xml  # type:ignore[attr-defined]
            klass.from_xml = classmethod(_XmlSerializable.from_xml.__func__)  # type:ignore[attr-defined]

        # Handle any deferred Properties depending on this class
        for _p in ObjectMetadataLibrary._deferred_property_type_parsing.get(klass.__qualname__, ()):
            _p.parse_type_deferred()

        return klass

    @classmethod
    def register_custom_json_property_name(cls, qual_name: str, json_property_name: str) -> None:
        prop = cls._klass_property_names.get(qual_name)
        if prop is None:
            cls._klass_property_names[qual_name] = {SerializationType.JSON: json_property_name}
        else:
            prop[SerializationType.JSON] = json_property_name

    @classmethod
    def register_custom_string_format(cls, qual_name: str, string_format: str) -> None:
        cls._klass_property_string_formats[qual_name] = string_format

    @classmethod
    def register_custom_xml_property_name(cls, qual_name: str, xml_property_name: str) -> None:
        prop = cls._klass_property_names.get(qual_name)
        if prop:
            prop[SerializationType.XML] = xml_property_name
        else:
            cls._klass_property_names[qual_name] = {SerializationType.XML: xml_property_name}

    @classmethod
    def register_klass_view(cls, klass: Type[_T], view_: Type[ViewType]) -> Type[_T]:
        ObjectMetadataLibrary._klass_views[f'{klass.__module__}.{klass.__qualname__}'] = view_
        return klass

    @classmethod
    def register_property_include_none(cls, qual_name: str, view_: Optional[Type[ViewType]] = None,
                                       none_value: Optional[Any] = None) -> None:
        prop = cls._klass_property_include_none.get(qual_name)
        val = (view_ or ViewType, none_value)
        if prop is None:
            cls._klass_property_include_none[qual_name] = {val}
        else:
            prop.add(val)

    @classmethod
    def register_property_view(cls, qual_name: str, view_: Type[ViewType]) -> None:
        prop = ObjectMetadataLibrary._klass_property_views.get(qual_name)
        if prop is None:
            ObjectMetadataLibrary._klass_property_views[qual_name] = {view_}
        else:
            prop.add(view_)

    @classmethod
    def register_xml_property_array_config(cls, qual_name: str,
                                           array_type: XmlArraySerializationType, child_name: str) -> None:
        cls._klass_property_array_config[qual_name] = (array_type, child_name)

    @classmethod
    def register_xml_property_string_config(cls, qual_name: str,
                                            string_type: Optional[XmlStringSerializationType]) -> None:
        cls._klass_property_string_config[qual_name] = string_type

    @classmethod
    def register_xml_property_attribute(cls, qual_name: str) -> None:
        cls._klass_property_attributes.add(qual_name)

    @classmethod
    def register_xml_property_sequence(cls, qual_name: str, sequence: int) -> None:
        cls._klass_property_xml_sequence[qual_name] = sequence

    @classmethod
    def register_property_type_mapping(cls, qual_name: str, mapped_type: type) -> None:
        cls._klass_property_types[qual_name] = mapped_type


@overload
def serializable_enum(cls: Literal[None] = None) -> Callable[[Type[_E]], Type[_E]]:
    ...


@overload
def serializable_enum(cls: Type[_E]) -> Type[_E]:  # type:ignore[misc] # mypy on py37
    ...


def serializable_enum(cls: Optional[Type[_E]] = None) -> Union[
    Callable[[Type[_E]], Type[_E]],
    Type[_E]
]:
    """Decorator"""

    def decorate(kls: Type[_E]) -> Type[_E]:
        ObjectMetadataLibrary.register_enum(klass=kls)
        return kls

    # See if we're being called as @enum or @enum().
    if cls is None:
        # We're called with parens.
        return decorate

    # We're called as @register_klass without parens.
    return decorate(cls)


@overload
def serializable_class(
    cls: Literal[None] = None, *,
    name: Optional[str] = ...,
    serialization_types: Optional[Iterable[SerializationType]] = ...,
    ignore_during_deserialization: Optional[Iterable[str]] = ...,
    ignore_unknown_during_deserialization: bool = ...
) -> Callable[[Type[_T]], Intersection[Type[_T], Type[_JsonSerializable], Type[_XmlSerializable]]]:
    ...


@overload
def serializable_class(  # type:ignore[misc] # mypy on py37
    cls: Type[_T], *,
    name: Optional[str] = ...,
    serialization_types: Optional[Iterable[SerializationType]] = ...,
    ignore_during_deserialization: Optional[Iterable[str]] = ...,
    ignore_unknown_during_deserialization: bool = ...
) -> Intersection[Type[_T], Type[_JsonSerializable], Type[_XmlSerializable]]:
    ...


def serializable_class(
    cls: Optional[Type[_T]] = None, *,
    name: Optional[str] = None,
    serialization_types: Optional[Iterable[SerializationType]] = None,
    ignore_during_deserialization: Optional[Iterable[str]] = None,
    ignore_unknown_during_deserialization: bool = False
) -> Union[
    Callable[[Type[_T]], Intersection[Type[_T], Type[_JsonSerializable], Type[_XmlSerializable]]],
    Intersection[Type[_T], Type[_JsonSerializable], Type[_XmlSerializable]]
]:
    """
    Decorator used to tell ``py_serializable`` that a class is to be included in (de-)serialization.

    :param cls: Class
    :param name: Alternative name to use for this Class
    :param serialization_types: Serialization Types that are to be supported for this class.
    :param ignore_during_deserialization: List of properties/elements to ignore during deserialization
    :param ignore_unknown_during_deserialization: Whether to ignore all properties/elements/attributes that are unknown
           to the class during deserialization
    :return:
    """
    # param ignore_unknown_during_deserialization defaults to False, since we deserialize from JSON/XML
    # and both have mechanisms for arbitrary content that might be intended to pass to the constructors:
    # - JSON has `additionalProperties:true`
    # - XML has `##any` and `##other`
    if serialization_types is None:
        serialization_types = _DEFAULT_SERIALIZATION_TYPES

    def decorate(kls: Type[_T]) -> Intersection[Type[_T], Type[_JsonSerializable], Type[_XmlSerializable]]:
        ObjectMetadataLibrary.register_klass(
            klass=kls, custom_name=name, serialization_types=serialization_types or [],
            ignore_during_deserialization=ignore_during_deserialization,
            ignore_unknown_during_deserialization=ignore_unknown_during_deserialization
        )
        return kls

    # See if we're being called as @register_klass or @register_klass().
    if cls is None:
        # We're called with parens.
        return decorate

    # We're called as @register_klass without parens.
    return decorate(cls)


def type_mapping(type_: type) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s with custom type: %s', f.__module__, f.__qualname__, type_)
        ObjectMetadataLibrary.register_property_type_mapping(
            qual_name=f'{f.__module__}.{f.__qualname__}', mapped_type=type_
        )
        return f

    return decorate


def include_none(view_: Optional[Type[ViewType]] = None, none_value: Optional[Any] = None) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s to include None for view: %s', f.__module__, f.__qualname__, view_)
        ObjectMetadataLibrary.register_property_include_none(
            qual_name=f'{f.__module__}.{f.__qualname__}', view_=view_, none_value=none_value
        )
        return f

    return decorate


def json_name(name: str) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s with JSON name: %s', f.__module__, f.__qualname__, name)
        ObjectMetadataLibrary.register_custom_json_property_name(
            qual_name=f'{f.__module__}.{f.__qualname__}', json_property_name=name
        )
        return f

    return decorate


def string_format(format_: str) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s with String Format: %s', f.__module__, f.__qualname__, format_)
        ObjectMetadataLibrary.register_custom_string_format(
            qual_name=f'{f.__module__}.{f.__qualname__}', string_format=format_
        )
        return f

    return decorate


def view(view_: Type[ViewType]) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s with View: %s', f.__module__, f.__qualname__, view_)
        ObjectMetadataLibrary.register_property_view(
            qual_name=f'{f.__module__}.{f.__qualname__}', view_=view_
        )
        return f

    return decorate


def xml_attribute() -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s as XML attribute', f.__module__, f.__qualname__)
        ObjectMetadataLibrary.register_xml_property_attribute(qual_name=f'{f.__module__}.{f.__qualname__}')
        return f

    return decorate


def xml_array(array_type: XmlArraySerializationType, child_name: str) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s as XML Array: %s:%s', f.__module__, f.__qualname__, array_type, child_name)
        ObjectMetadataLibrary.register_xml_property_array_config(
            qual_name=f'{f.__module__}.{f.__qualname__}', array_type=array_type, child_name=child_name
        )
        return f

    return decorate


def xml_string(string_type: XmlStringSerializationType) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s as XML StringType: %s', f.__module__, f.__qualname__, string_type)
        ObjectMetadataLibrary.register_xml_property_string_config(
            qual_name=f'{f.__module__}.{f.__qualname__}', string_type=string_type
        )
        return f

    return decorate


def xml_name(name: str) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s with XML name: %s', f.__module__, f.__qualname__, name)
        ObjectMetadataLibrary.register_custom_xml_property_name(
            qual_name=f'{f.__module__}.{f.__qualname__}', xml_property_name=name
        )
        return f

    return decorate


def xml_sequence(sequence: int) -> Callable[[_F], _F]:
    """Decorator"""

    def decorate(f: _F) -> _F:
        _logger.debug('Registering %s.%s with XML sequence: %s', f.__module__, f.__qualname__, sequence)
        ObjectMetadataLibrary.register_xml_property_sequence(
            qual_name=f'{f.__module__}.{f.__qualname__}', sequence=sequence
        )
        return f

    return decorate
