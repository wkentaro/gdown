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
from decimal import Decimal
from enum import Enum
from json import loads as json_loads
from typing import Any, List, Optional, Union
from warnings import warn
from xml.etree.ElementTree import Element as XmlElement  # nosec B405

# See https://github.com/package-url/packageurl-python/issues/65
import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.bom_ref import bom_ref_from_str as _bom_ref_from_str
from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.model import InvalidConfidenceException, InvalidValueException
from ..schema.schema import SchemaVersion1Dot5, SchemaVersion1Dot6, SchemaVersion1Dot7
from . import Copyright
from .bom_ref import BomRef
from .license import License, LicenseRepository, _LicenseRepositorySerializationHelper


@serializable.serializable_enum
class IdentityField(str, Enum):
    """
    Enum object that defines the permissible field types for Identity.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/json/#components_items_evidence_identity
    """

    GROUP = 'group'
    NAME = 'name'
    VERSION = 'version'
    PURL = 'purl'
    CPE = 'cpe'
    OMNIBOR_ID = 'omniborId'
    SWHID = 'swhid'
    SWID = 'swid'
    HASH = 'hash'


@serializable.serializable_enum
class AnalysisTechnique(str, Enum):
    """
    Enum object that defines the permissible analysis techniques.
    """

    SOURCE_CODE_ANALYSIS = 'source-code-analysis'
    BINARY_ANALYSIS = 'binary-analysis'
    MANIFEST_ANALYSIS = 'manifest-analysis'
    AST_FINGERPRINT = 'ast-fingerprint'
    HASH_COMPARISON = 'hash-comparison'
    INSTRUMENTATION = 'instrumentation'
    DYNAMIC_ANALYSIS = 'dynamic-analysis'
    FILENAME = 'filename'
    ATTESTATION = 'attestation'
    OTHER = 'other'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Method:
    """
    Represents a method used to extract and/or analyze evidence.

    .. note::
        See the CycloneDX Schema definition:
        https://cyclonedx.org/docs/1.7/json/#components_items_evidence_identity_oneOf_i0_items_methods
    """

    def __init__(
        self, *,
        technique: AnalysisTechnique,
        confidence: Decimal,
        value: Optional[str] = None,
    ) -> None:
        self.technique = technique
        self.confidence = confidence
        self.value = value

    @property
    @serializable.xml_sequence(1)
    def technique(self) -> AnalysisTechnique:
        return self._technique

    @technique.setter
    def technique(self, technique: AnalysisTechnique) -> None:
        self._technique = technique

    @property
    @serializable.xml_sequence(2)
    def confidence(self) -> Decimal:
        """
        The confidence of the evidence from 0 - 1, where 1 is 100% confidence.
        Confidence is specific to the technique used. Each technique of analysis can have independent confidence.
        """
        return self._confidence

    @confidence.setter
    def confidence(self, confidence: Decimal) -> None:
        if not (0 <= confidence <= 1):
            raise InvalidConfidenceException(f'confidence {confidence!r} is invalid')
        self._confidence = confidence

    @property
    @serializable.xml_sequence(3)
    def value(self) -> Optional[str]:
        return self._value

    @value.setter
    def value(self, value: Optional[str]) -> None:
        self._value = value

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.technique,
            self.confidence,
            self.value,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Method):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Method):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Method technique={self.technique}, confidence={self.confidence}, value={self.value}>'


class _IdentityToolRepositorySerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    @classmethod
    def json_serialize(cls, o: Iterable['BomRef']) -> list[str]:
        return [t.value for t in o if t.value]

    @classmethod
    def json_deserialize(cls, o: Iterable[str]) -> list[BomRef]:
        return [BomRef(value=t) for t in o]

    @classmethod
    def xml_normalize(cls, o: Iterable[BomRef], *,
                      xmlns: Optional[str],
                      **kwargs: Any) -> Optional[XmlElement]:
        o = tuple(o)
        if len(o) == 0:
            return None
        elem_s = XmlElement(f'{{{xmlns}}}tools' if xmlns else 'tools')
        tool_name = f'{{{xmlns}}}tool' if xmlns else 'tool'
        ref_name = f'{{{xmlns}}}ref' if xmlns else 'ref'
        elem_s.extend(
            XmlElement(tool_name, {ref_name: t.value})
            for t in o if t.value)
        return elem_s

    @classmethod
    def xml_denormalize(cls, o: 'XmlElement', *,
                        default_ns: Optional[str],
                        **__: Any) -> list[BomRef]:
        return [BomRef(value=t.get('ref')) for t in o]


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Identity:
    """
    Our internal representation of the `identityType` complex type.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/json/#components_items_evidence_identity
    """

    def __init__(
        self, *,
        field: IdentityField,
        confidence: Optional[Decimal] = None,
        concluded_value: Optional[str] = None,
        methods: Optional[Iterable[Method]] = None,
        tools: Optional[Iterable[BomRef]] = None,
    ) -> None:
        self.field = field
        self.confidence = confidence
        self.concluded_value = concluded_value
        self.methods = methods or []
        self.tools = tools or []

    @property
    @serializable.xml_sequence(1)
    def field(self) -> IdentityField:
        return self._field

    @field.setter
    def field(self, field: IdentityField) -> None:
        self._field = field

    @property
    @serializable.xml_sequence(2)
    def confidence(self) -> Optional[Decimal]:
        """
        The overall confidence of the evidence from 0 - 1, where 1 is 100% confidence.
        """
        return self._confidence

    @confidence.setter
    def confidence(self, confidence: Optional[Decimal]) -> None:
        if confidence is not None and not (0 <= confidence <= 1):
            raise InvalidConfidenceException(f'{confidence} in invalid')
        self._confidence = confidence

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(3)
    def concluded_value(self) -> Optional[str]:
        return self._concluded_value

    @concluded_value.setter
    def concluded_value(self, concluded_value: Optional[str]) -> None:
        self._concluded_value = concluded_value

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'method')
    @serializable.xml_sequence(4)
    def methods(self) -> 'SortedSet[Method]':
        return self._methods

    @methods.setter
    def methods(self, methods: Iterable[Method]) -> None:
        self._methods = SortedSet(methods)

    @property
    @serializable.type_mapping(_IdentityToolRepositorySerializationHelper)
    @serializable.xml_sequence(5)
    def tools(self) -> 'SortedSet[BomRef]':
        """
        References to the tools used to perform analysis and collect evidence.
        """
        return self._tools

    @tools.setter
    def tools(self, tools: Iterable[BomRef]) -> None:
        self._tools = SortedSet(tools)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.field,
            self.confidence,
            self.concluded_value,
            _ComparableTuple(self.methods),
            _ComparableTuple(self.tools),
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Identity):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Identity):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Identity field={self.field}, confidence={self.confidence},' \
            f' concludedValue={self.concluded_value},' \
            f' methods={self.methods}, tools={self.tools}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Occurrence:
    """
    Our internal representation of the `occurrenceType` complex type.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/json/#components_items_evidence_occurrences
    """

    def __init__(
        self, *,
        bom_ref: Optional[Union[str, BomRef]] = None,
        location: str,
        line: Optional[int] = None,
        offset: Optional[int] = None,
        symbol: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> None:
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.location = location
        self.line = line
        self.offset = offset
        self.symbol = symbol
        self.additional_context = additional_context

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
    def location(self) -> str:
        """
        Location can be a file path, URL, or a unique identifier from a component discovery tool
        """
        return self._location

    @location.setter
    def location(self, location: str) -> None:
        self._location = location

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(2)
    def line(self) -> Optional[int]:
        """
        The line number in the file where the dependency or reference was detected.
        """
        return self._line

    @line.setter
    def line(self, line: Optional[int]) -> None:
        if line is not None and line < 0:
            raise InvalidValueException(f'line {line!r} must not be lower than zero')
        self._line = line

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(3)
    def offset(self) -> Optional[int]:
        """
        The offset location within the file where the dependency or reference was detected.
        """
        return self._offset

    @offset.setter
    def offset(self, offset: Optional[int]) -> None:
        if offset is not None and offset < 0:
            raise InvalidValueException(f'offset {offset!r} must not be lower than zero')
        self._offset = offset

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(4)
    def symbol(self) -> Optional[str]:
        """
        Programming language symbol or import name.
        """
        return self._symbol

    @symbol.setter
    def symbol(self, symbol: Optional[str]) -> None:
        self._symbol = symbol

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(5)
    def additional_context(self) -> Optional[str]:
        """
        Additional context about the occurrence of the component.
        """
        return self._additional_context

    @additional_context.setter
    def additional_context(self, additional_context: Optional[str]) -> None:
        self._additional_context = additional_context

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.bom_ref,
            self.location,
            self.line,
            self.offset,
            self.symbol,
            self.additional_context,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Occurrence):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Occurrence):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Occurrence location={self.location}, line={self.line}, symbol={self.symbol}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class CallStackFrame:
    """
    Represents an individual frame in a call stack.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/json/#components_items_evidence_callstack
    """

    def __init__(
        self, *,
        module: str,
        package: Optional[str] = None,
        function: Optional[str] = None,
        parameters: Optional[Iterable[str]] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        full_filename: Optional[str] = None,
    ) -> None:
        self.package = package
        self.module = module
        self.function = function
        self.parameters = parameters or []
        self.line = line
        self.column = column
        self.full_filename = full_filename

    @property
    @serializable.xml_sequence(1)
    def package(self) -> Optional[str]:
        """
        The package name.
        """
        return self._package

    @package.setter
    def package(self, package: Optional[str]) -> None:
        """
        Sets the package name.
        """
        self._package = package

    @property
    @serializable.xml_sequence(2)
    def module(self) -> str:
        """
        The module name
        """
        return self._module

    @module.setter
    def module(self, module: str) -> None:
        self._module = module

    @property
    @serializable.xml_sequence(3)
    def function(self) -> Optional[str]:
        """
        The function name.
        """
        return self._function

    @function.setter
    def function(self, function: Optional[str]) -> None:
        """
        Sets the function name.
        """
        self._function = function

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'parameter')
    @serializable.xml_sequence(4)
    def parameters(self) -> 'SortedSet[str]':
        """
        Function parameters
        """
        return self._parameters

    @parameters.setter
    def parameters(self, parameters: Iterable[str]) -> None:
        self._parameters = SortedSet(parameters)

    @property
    @serializable.xml_sequence(5)
    def line(self) -> Optional[int]:
        """
        The line number
        """
        return self._line

    @line.setter
    def line(self, line: Optional[int]) -> None:
        self._line = line

    @property
    @serializable.xml_sequence(6)
    def column(self) -> Optional[int]:
        """
        The column number
        """
        return self._column

    @column.setter
    def column(self, column: Optional[int]) -> None:
        self._column = column

    @property
    @serializable.xml_sequence(7)
    def full_filename(self) -> Optional[str]:
        """
        The full file path
        """
        return self._full_filename

    @full_filename.setter
    def full_filename(self, full_filename: Optional[str]) -> None:
        self._full_filename = full_filename

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.package,
            self.module,
            self.function,
            _ComparableTuple(self.parameters),
            self.line,
            self.column,
            self.full_filename,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CallStackFrame):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, CallStackFrame):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return '<CallStackFrame' \
               f' package={self.package}, module={self.module}, ' \
               f' function={self.function}, parameters={self.parameters!r},' \
               f' line={self.line}, column={self.column}, full_filename={self.full_filename}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class CallStack:
    """
    Our internal representation of the `callStackType` complex type.
    Contains an array of stack frames describing a call stack from when a component was identified.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/json/#components_items_evidence_callstack
    """

    def __init__(
        self, *,
        frames: Optional[Iterable[CallStackFrame]] = None,
    ) -> None:
        self.frames = frames or []

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'frame')
    @serializable.xml_sequence(1)
    def frames(self) -> 'List[CallStackFrame]':
        """
        Array of stack frames
        """
        return self._frames

    @frames.setter
    def frames(self, frames: Iterable[CallStackFrame]) -> None:
        self._frames = list(frames)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            _ComparableTuple(self.frames),
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CallStack):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, CallStack):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        h = self.__comparable_tuple()
        try:
            return hash(h)
        except TypeError as e:
            raise e

    def __repr__(self) -> str:
        return f'<CallStack frames={len(self.frames)}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class ComponentEvidence:
    """
    Our internal representation of the `componentEvidenceType` complex type.

    Provides the ability to document evidence collected through various forms of extraction or analysis.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_componentEvidenceType
    """

    def __init__(
        self, *,
        identity: Optional[Union[Iterable[Identity], Identity]] = None,
        occurrences: Optional[Iterable[Occurrence]] = None,
        callstack: Optional[CallStack] = None,
        licenses: Optional[Iterable[License]] = None,
        copyright: Optional[Iterable[Copyright]] = None,
    ) -> None:
        self.identity = identity or []
        self.occurrences = occurrences or []
        self.callstack = callstack
        self.licenses = licenses or []
        self.copyright = copyright or []

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(1)
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, 'identity')
    def identity(self) -> 'SortedSet[Identity]':
        """
        Provides a way to identify components via various methods.
        Returns SortedSet of identities.
        """
        return self._identity

    @identity.setter
    def identity(self, identity: Union[Iterable[Identity], Identity]) -> None:
        self._identity = SortedSet(
            (identity,)
            if isinstance(identity, Identity)
            else identity
        )

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'occurrence')
    @serializable.xml_sequence(2)
    def occurrences(self) -> 'SortedSet[Occurrence]':
        """A list of locations where evidence was obtained from."""
        return self._occurrences

    @occurrences.setter
    def occurrences(self, occurrences: Iterable[Occurrence]) -> None:
        self._occurrences = SortedSet(occurrences)

    @property
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(3)
    def callstack(self) -> Optional[CallStack]:
        """
        A representation of a call stack from when the component was identified.
        """
        return self._callstack

    @callstack.setter
    def callstack(self, callstack: Optional[CallStack]) -> None:
        self._callstack = callstack

    @property
    @serializable.type_mapping(_LicenseRepositorySerializationHelper)
    @serializable.xml_sequence(4)
    def licenses(self) -> LicenseRepository:
        """
        Optional list of licenses obtained during analysis.

        Returns:
            Set of `LicenseChoice`
        """
        return self._licenses

    @licenses.setter
    def licenses(self, licenses: Iterable[License]) -> None:
        self._licenses = LicenseRepository(licenses)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'text')
    @serializable.xml_sequence(5)
    def copyright(self) -> 'SortedSet[Copyright]':
        """
        Optional list of copyright statements.

        Returns:
             Set of `Copyright`
        """
        return self._copyright

    @copyright.setter
    def copyright(self, copyright: Iterable[Copyright]) -> None:
        self._copyright = SortedSet(copyright)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            _ComparableTuple(self.licenses),
            _ComparableTuple(self.copyright),
            self.callstack,
            _ComparableTuple(self.identity),
            _ComparableTuple(self.occurrences),
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ComponentEvidence):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ComponentEvidence):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<ComponentEvidence id={id(self)}>'


class _ComponentEvidenceSerializationHelper(serializable.helpers.BaseHelper):
    """THIS CLASS IS NON-PUBLIC API

    This helper takes care of :attr:`ComponentEvidence.identity`.
    """

    @classmethod
    def json_normalize(cls, o: ComponentEvidence, *,
                       view: Optional[type[serializable.ViewType]],
                       **__: Any) -> dict[str, Any]:
        data: dict[str, Any] = json_loads(o.as_json(view))  # type:ignore[attr-defined]
        if view is SchemaVersion1Dot5:
            identities = data.get('identity', [])
            if identities:
                if (il := len(identities)) > 1:
                    warn(f'CycloneDX 1.5 does not support multiple identity items; dropping {il - 1} items.')
                data['identity'] = identities[0]
        return data

    @classmethod
    def json_denormalize(cls, o: dict[str, Any], **__: Any) -> Any:
        if isinstance(identity := o.get('identity'), dict):
            o = {**o, 'identity': [identity]}
        return ComponentEvidence.from_json(o)  # type:ignore[attr-defined]

    @classmethod
    def xml_normalize(cls, o: ComponentEvidence, *,
                      element_name: str,
                      view: Optional[type['serializable.ViewType']],
                      xmlns: Optional[str],
                      **__: Any) -> Optional['XmlElement']:
        normalized: 'XmlElement' = o.as_xml(view, False, element_name, xmlns)  # type:ignore[attr-defined]
        if view is SchemaVersion1Dot5:
            identities = normalized.findall(f'./{{{xmlns}}}identity' if xmlns else './identity')
            if (il := len(identities)) > 1:
                warn(f'CycloneDX 1.5 does not support multiple identity items; dropping {il - 1} items.')
                for i in identities[1:]:
                    normalized.remove(i)
        return normalized

    @classmethod
    def xml_denormalize(cls, o: 'XmlElement', *,
                        default_ns: Optional[str],
                        **__: Any) -> Any:
        return ComponentEvidence.from_xml(o, default_ns)  # type:ignore[attr-defined]
