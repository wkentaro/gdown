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
Uniform set of models to represent objects within a CycloneDX software bill-of-materials.

You can either create a `cyclonedx.model.bom.Bom` yourself programmatically, or generate a `cyclonedx.model.bom.Bom`
from a `cyclonedx.parser.BaseParser` implementation.
"""

import re
import sys
from collections.abc import Generator, Iterable
from datetime import datetime
from enum import Enum
from functools import reduce
from json import loads as json_loads
from typing import Any, Optional, Union
from urllib.parse import quote as url_quote
from uuid import UUID
from warnings import warn
from xml.etree.ElementTree import Element as XmlElement  # nosec B405

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.model import InvalidLocaleTypeException, InvalidUriException
from ..exception.serialization import CycloneDxDeserializationException, SerializationOfUnexpectedValueException
from ..schema.schema import (
    SchemaVersion1Dot0,
    SchemaVersion1Dot1,
    SchemaVersion1Dot2,
    SchemaVersion1Dot3,
    SchemaVersion1Dot4,
    SchemaVersion1Dot5,
    SchemaVersion1Dot6,
    SchemaVersion1Dot7,
)
from .bom_ref import BomRef

_BOM_LINK_PREFIX = 'urn:cdx:'


@serializable.serializable_enum
class DataFlow(str, Enum):
    """
    This is our internal representation of the dataFlowType simple type within the CycloneDX standard.

    .. note::
        See the CycloneDX Schema: https://cyclonedx.org/docs/1.7/xml/#type_dataFlowType
    """
    INBOUND = 'inbound'
    OUTBOUND = 'outbound'
    BI_DIRECTIONAL = 'bi-directional'
    UNKNOWN = 'unknown'


@serializable.serializable_class
class DataClassification:
    """
    This is our internal representation of the `dataClassificationType` complex type within the CycloneDX standard.

    DataClassification might be deprecated since CycloneDX 1.5, but it is not deprecated in this library.
    In fact, this library will try to provide a compatibility layer if needed.

    .. note::
        See the CycloneDX Schema for dataClassificationType:
        https://cyclonedx.org/docs/1.7/xml/#type_dataClassificationType
    """

    def __init__(
        self, *,
        flow: DataFlow,
        classification: str,
    ) -> None:
        self.flow = flow
        self.classification = classification

    @property
    @serializable.xml_attribute()
    def flow(self) -> DataFlow:
        """
        Specifies the flow direction of the data.

        Valid values are: inbound, outbound, bi-directional, and unknown.

        Direction is relative to the service.

        - Inbound flow states that data enters the service
        - Outbound flow states that data leaves the service
        - Bi-directional states that data flows both ways
        - Unknown states that the direction is not known

        Returns:
            `DataFlow`
        """
        return self._flow

    @flow.setter
    def flow(self, flow: DataFlow) -> None:
        self._flow = flow

    @property
    @serializable.xml_name('.')
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def classification(self) -> str:
        """
        Data classification tags data according to its type, sensitivity, and value if altered, stolen, or destroyed.

        Returns:
            `str`
        """
        return self._classification

    @classification.setter
    def classification(self, classification: str) -> None:
        self._classification = classification

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.flow, self.classification
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DataClassification):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, DataClassification):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<DataClassification flow={self.flow}>'


@serializable.serializable_enum
class Encoding(str, Enum):
    """
    This is our internal representation of the encoding simple type within the CycloneDX standard.

    .. note::
        See the CycloneDX Schema: https://cyclonedx.org/docs/1.7/xml/#type_encoding
    """
    BASE_64 = 'base64'


@serializable.serializable_class
class AttachedText:
    """
    This is our internal representation of the `attachedTextType` complex type within the CycloneDX standard.

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_attachedTextType
    """

    DEFAULT_CONTENT_TYPE = 'text/plain'

    def __init__(
        self, *,
        content: str,
        content_type: str = DEFAULT_CONTENT_TYPE,
        encoding: Optional[Encoding] = None,
    ) -> None:
        self.content_type = content_type
        self.encoding = encoding
        self.content = content

    @property
    @serializable.xml_attribute()
    @serializable.xml_name('content-type')
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def content_type(self) -> str:
        """
        Specifies the content type of the text. Defaults to text/plain if not specified.

        Returns:
            `str`
        """
        return self._content_type

    @content_type.setter
    def content_type(self, content_type: str) -> None:
        self._content_type = content_type

    @property
    @serializable.xml_attribute()
    def encoding(self) -> Optional[Encoding]:
        """
        Specifies the optional encoding the text is represented in.

        Returns:
            `Encoding` if set else `None`
        """
        return self._encoding

    @encoding.setter
    def encoding(self, encoding: Optional[Encoding]) -> None:
        self._encoding = encoding

    @property
    @serializable.xml_name('.')
    def content(self) -> str:
        """
        The attachment data.

        Proactive controls such as input validation and sanitization should be employed to prevent misuse of attachment
        text.

        Returns:
            `str`
        """
        return self._content

    @content.setter
    def content(self, content: str) -> None:
        self._content = content

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.content_type, self.encoding, self.content,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AttachedText):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, AttachedText):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<AttachedText content-type={self.content_type}, encoding={self.encoding}>'


@serializable.serializable_enum
class HashAlgorithm(str, Enum):
    """
    This is our internal representation of the hashAlg simple type within the CycloneDX standard.

    .. note::
        See the CycloneDX Schema: https://cyclonedx.org/docs/1.7/xml/#type_hashAlg
    """
    # see `_HashTypeRepositorySerializationHelper.__CASES` for view/case map
    BLAKE2B_256 = 'BLAKE2b-256'  # Only supported in >= 1.2
    BLAKE2B_384 = 'BLAKE2b-384'  # Only supported in >= 1.2
    BLAKE2B_512 = 'BLAKE2b-512'  # Only supported in >= 1.2
    BLAKE3 = 'BLAKE3'  # Only supported in >= 1.2
    MD5 = 'MD5'
    SHA_1 = 'SHA-1'
    SHA_256 = 'SHA-256'
    SHA_384 = 'SHA-384'
    SHA_512 = 'SHA-512'
    SHA3_256 = 'SHA3-256'
    SHA3_384 = 'SHA3-384'  # Only supported in >= 1.2
    SHA3_512 = 'SHA3-512'
    STREEBOG_256 = 'Streebog-256'  # Only supported in >= 1.7
    STREEBOG_512 = 'Streebog-512'  # Only supported in >= 1.7


class _HashTypeRepositorySerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    __CASES: dict[type[serializable.ViewType], frozenset[HashAlgorithm]] = dict()
    __CASES[SchemaVersion1Dot0] = frozenset({
        HashAlgorithm.MD5,
        HashAlgorithm.SHA_1,
        HashAlgorithm.SHA_256,
        HashAlgorithm.SHA_384,
        HashAlgorithm.SHA_512,
        HashAlgorithm.SHA3_256,
        HashAlgorithm.SHA3_512,
    })
    __CASES[SchemaVersion1Dot1] = __CASES[SchemaVersion1Dot0]
    __CASES[SchemaVersion1Dot2] = __CASES[SchemaVersion1Dot1] | {
        HashAlgorithm.BLAKE2B_256,
        HashAlgorithm.BLAKE2B_384,
        HashAlgorithm.BLAKE2B_512,
        HashAlgorithm.BLAKE3,
        HashAlgorithm.SHA3_384,
    }
    __CASES[SchemaVersion1Dot3] = __CASES[SchemaVersion1Dot2]
    __CASES[SchemaVersion1Dot4] = __CASES[SchemaVersion1Dot3]
    __CASES[SchemaVersion1Dot5] = __CASES[SchemaVersion1Dot4]
    __CASES[SchemaVersion1Dot6] = __CASES[SchemaVersion1Dot5]
    __CASES[SchemaVersion1Dot7] = __CASES[SchemaVersion1Dot6] | {
        HashAlgorithm.STREEBOG_256,
        HashAlgorithm.STREEBOG_512,
    }

    @classmethod
    def __prep(cls, hts: Iterable['HashType'], view: type[serializable.ViewType]) -> Generator['HashType', None, None]:
        cases = cls.__CASES.get(view, ())
        for ht in hts:
            if ht.alg in cases:
                yield ht
            else:
                warn(f'serialization omitted due to unsupported HashAlgorithm: {ht!r}',
                     category=UserWarning, stacklevel=0)

    @classmethod
    def json_normalize(cls, o: Iterable['HashType'], *,
                       view: Optional[type[serializable.ViewType]],
                       **__: Any) -> list[Any]:
        assert view is not None
        return [
            json_loads(
                ht.as_json(  # type:ignore[attr-defined]
                    view_=view)
            ) for ht in cls.__prep(o, view)
        ]

    @classmethod
    def xml_normalize(cls, o: Iterable['HashType'], *,
                      element_name: str,
                      view: Optional[type[serializable.ViewType]],
                      xmlns: Optional[str],
                      **__: Any) -> XmlElement:
        assert view is not None
        elem = XmlElement(element_name)
        elem.extend(
            ht.as_xml(  # type:ignore[attr-defined]
                view_=view, as_string=False, element_name='hash', xmlns=xmlns
            ) for ht in cls.__prep(o, view)
        )
        return elem

    @classmethod
    def json_denormalize(cls, o: Any,
                         **__: Any) -> list['HashType']:
        return [
            HashType.from_json(  # type:ignore[attr-defined]
                ht) for ht in o
        ]

    @classmethod
    def xml_denormalize(cls, o: 'XmlElement', *,
                        default_ns: Optional[str],
                        **__: Any) -> list['HashType']:
        return [
            HashType.from_xml(  # type:ignore[attr-defined]
                ht, default_ns) for ht in o
        ]


@serializable.serializable_class
class HashType:
    """
    This is our internal representation of the hashType complex type within the CycloneDX standard.

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_hashType
    """

    @staticmethod
    @deprecated('Deprecated - use cyclonedx.contrib.hash.factories.HashTypeFactory().from_hashlib_alg() instead')
    def from_hashlib_alg(hashlib_alg: str, content: str) -> 'HashType':
        """Deprecated — Alias of :func:`cyclonedx.contrib.hash.factories.HashTypeFactory.from_hashlib_alg`.

        Attempts to convert a hashlib-algorithm to our internal model classes.

        .. deprecated:: next
            Use ``cyclonedx.contrib.hash.factories.HashTypeFactory().from_hashlib_alg()`` instead.
        """
        from ..contrib.hash.factories import HashTypeFactory

        return HashTypeFactory().from_hashlib_alg(hashlib_alg, content)

    @staticmethod
    @deprecated('Deprecated - use cyclonedx.contrib.hash.factories.HashTypeFactory().from_composite_str() instead')
    def from_composite_str(composite_hash: str) -> 'HashType':
        """Deprecated — Alias of :func:`cyclonedx.contrib.hash.factories.HashTypeFactory.from_composite_str`.

        Attempts to convert a string which includes both the Hash Algorithm and Hash Value and represent using our
        internal model classes.

        .. deprecated:: next
            Use ``cyclonedx.contrib.hash.factories.HashTypeFactory().from_composite_str()`` instead.
        """
        from ..contrib.hash.factories import HashTypeFactory

        return HashTypeFactory().from_composite_str(composite_hash)

    def __init__(
        self, *,
        alg: HashAlgorithm,
        content: str,
    ) -> None:
        self.alg = alg
        self.content = content

    @property
    @serializable.xml_attribute()
    def alg(self) -> HashAlgorithm:
        """
        Specifies the algorithm used to create the hash.

        Returns:
            `HashAlgorithm`
        """
        return self._alg

    @alg.setter
    def alg(self, alg: HashAlgorithm) -> None:
        self._alg = alg

    @property
    @serializable.xml_name('.')
    @serializable.xml_string(serializable.XmlStringSerializationType.TOKEN)
    def content(self) -> str:
        """
        Hash value content.

        Returns:
            `str`
        """
        return self._content

    @content.setter
    def content(self, content: str) -> None:
        self._content = content

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.alg, self.content
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, HashType):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, HashType):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<HashType {self.alg.name}:{self.content}>'


@serializable.serializable_enum
class ExternalReferenceType(str, Enum):
    """
    Enum object that defines the permissible 'types' for an External Reference according to the CycloneDX schema.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_externalReferenceType
    """
    # see `_ExternalReferenceSerializationHelper.__CASES` for view/case map
    ADVERSARY_MODEL = 'adversary-model'  # Only supported in >= 1.5
    ADVISORIES = 'advisories'
    ATTESTATION = 'attestation'  # Only supported in >= 1.5
    BOM = 'bom'
    BUILD_META = 'build-meta'
    BUILD_SYSTEM = 'build-system'
    CERTIFICATION_REPORT = 'certification-report'  # Only supported in >= 1.5
    CHAT = 'chat'
    CITATION = 'citation'  # Only supported in >= 1.7
    CODIFIED_INFRASTRUCTURE = 'codified-infrastructure'  # Only supported in >= 1.5
    COMPONENT_ANALYSIS_REPORT = 'component-analysis-report'  # Only supported in >= 1.5
    CONFIGURATION = 'configuration'  # Only supported in >= 1.5
    DIGITAL_SIGNATURE = 'digital-signature'  # Only supported in >= 1.6
    DISTRIBUTION = 'distribution'
    DISTRIBUTION_INTAKE = 'distribution-intake'  # Only supported in >= 1.5
    DOCUMENTATION = 'documentation'
    DYNAMIC_ANALYSIS_REPORT = 'dynamic-analysis-report'  # Only supported in >= 1.5
    ELECTRONIC_SIGNATURE = 'electronic-signature'  # Only supported in >= 1.6
    EVIDENCE = 'evidence'  # Only supported in >= 1.5
    EXPLOITABILITY_STATEMENT = 'exploitability-statement'  # Only supported in >= 1.5
    FORMULATION = 'formulation'  # Only supported in >= 1.5
    ISSUE_TRACKER = 'issue-tracker'
    LICENSE = 'license'
    LOG = 'log'  # Only supported in >= 1.5
    MAILING_LIST = 'mailing-list'
    MATURITY_REPORT = 'maturity-report'  # Only supported in >= 1.5
    MODEL_CARD = 'model-card'  # Only supported in >= 1.5
    PATENT = 'patent'  # Only supported in >= 1.7
    PATENT_ASSERTION = 'patent-assertion'  # Only supported in >= 1.7
    PATENT_FAMILY = 'patent-family'  # Only supported in >= 1.7
    PENTEST_REPORT = 'pentest-report'  # Only supported in >= 1.5
    POAM = 'poam'  # Only supported in >= 1.5
    QUALITY_METRICS = 'quality-metrics'  # Only supported in >= 1.5
    RELEASE_NOTES = 'release-notes'  # Only supported in >= 1.4
    RFC_9166 = 'rfc-9116'  # Only supported in >= 1.6
    RISK_ASSESSMENT = 'risk-assessment'  # Only supported in >= 1.5
    RUNTIME_ANALYSIS_REPORT = 'runtime-analysis-report'  # Only supported in >= 1.5
    SECURITY_CONTACT = 'security-contact'  # Only supported in >= 1.5
    STATIC_ANALYSIS_REPORT = 'static-analysis-report'  # Only supported in >= 1.5
    SOCIAL = 'social'
    SOURCE_DISTRIBUTION = 'source-distribution'  # Only supported in >= 1.6
    SCM = 'vcs'
    SUPPORT = 'support'
    THREAT_MODEL = 'threat-model'  # Only supported in >= 1.5
    VCS = 'vcs'
    VULNERABILITY_ASSERTION = 'vulnerability-assertion'  # Only supported in >= 1.5
    WEBSITE = 'website'
    # --
    OTHER = 'other'


class _ExternalReferenceSerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    __CASES: dict[type[serializable.ViewType], frozenset[ExternalReferenceType]] = dict()
    __CASES[SchemaVersion1Dot1] = frozenset({
        ExternalReferenceType.VCS,
        ExternalReferenceType.ISSUE_TRACKER,
        ExternalReferenceType.WEBSITE,
        ExternalReferenceType.ADVISORIES,
        ExternalReferenceType.BOM,
        ExternalReferenceType.MAILING_LIST,
        ExternalReferenceType.SOCIAL,
        ExternalReferenceType.CHAT,
        ExternalReferenceType.DOCUMENTATION,
        ExternalReferenceType.SUPPORT,
        ExternalReferenceType.DISTRIBUTION,
        ExternalReferenceType.LICENSE,
        ExternalReferenceType.BUILD_META,
        ExternalReferenceType.BUILD_SYSTEM,
        ExternalReferenceType.OTHER,
    })
    __CASES[SchemaVersion1Dot2] = __CASES[SchemaVersion1Dot1]
    __CASES[SchemaVersion1Dot3] = __CASES[SchemaVersion1Dot2]
    __CASES[SchemaVersion1Dot4] = __CASES[SchemaVersion1Dot3] | {
        ExternalReferenceType.RELEASE_NOTES
    }
    __CASES[SchemaVersion1Dot5] = __CASES[SchemaVersion1Dot4] | {
        ExternalReferenceType.DISTRIBUTION_INTAKE,
        ExternalReferenceType.SECURITY_CONTACT,
        ExternalReferenceType.MODEL_CARD,
        ExternalReferenceType.LOG,
        ExternalReferenceType.CONFIGURATION,
        ExternalReferenceType.EVIDENCE,
        ExternalReferenceType.FORMULATION,
        ExternalReferenceType.ATTESTATION,
        ExternalReferenceType.THREAT_MODEL,
        ExternalReferenceType.ADVERSARY_MODEL,
        ExternalReferenceType.RISK_ASSESSMENT,
        ExternalReferenceType.VULNERABILITY_ASSERTION,
        ExternalReferenceType.EXPLOITABILITY_STATEMENT,
        ExternalReferenceType.PENTEST_REPORT,
        ExternalReferenceType.STATIC_ANALYSIS_REPORT,
        ExternalReferenceType.DYNAMIC_ANALYSIS_REPORT,
        ExternalReferenceType.RUNTIME_ANALYSIS_REPORT,
        ExternalReferenceType.COMPONENT_ANALYSIS_REPORT,
        ExternalReferenceType.MATURITY_REPORT,
        ExternalReferenceType.CERTIFICATION_REPORT,
        ExternalReferenceType.QUALITY_METRICS,
        ExternalReferenceType.CODIFIED_INFRASTRUCTURE,
        ExternalReferenceType.POAM,
    }
    __CASES[SchemaVersion1Dot6] = __CASES[SchemaVersion1Dot5] | {
        ExternalReferenceType.SOURCE_DISTRIBUTION,
        ExternalReferenceType.ELECTRONIC_SIGNATURE,
        ExternalReferenceType.DIGITAL_SIGNATURE,
        ExternalReferenceType.RFC_9166,
    }
    __CASES[SchemaVersion1Dot7] = __CASES[SchemaVersion1Dot6] | {
        ExternalReferenceType.CITATION,
        ExternalReferenceType.PATENT,
        ExternalReferenceType.PATENT_ASSERTION,
        ExternalReferenceType.PATENT_FAMILY,
    }

    @classmethod
    def __normalize(cls, extref: ExternalReferenceType, view: type[serializable.ViewType]) -> str:
        return (
            extref
            if extref in cls.__CASES.get(view, ())
            else ExternalReferenceType.OTHER
        ).value

    @classmethod
    def json_normalize(cls, o: Any, *,
                       view: Optional[type[serializable.ViewType]],
                       **__: Any) -> str:
        assert view is not None
        return cls.__normalize(o, view)

    @classmethod
    def xml_normalize(cls, o: Any, *,
                      view: Optional[type[serializable.ViewType]],
                      **__: Any) -> str:
        assert view is not None
        return cls.__normalize(o, view)

    @classmethod
    def deserialize(cls, o: Any) -> ExternalReferenceType:
        return ExternalReferenceType(o)


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class XsUri(serializable.helpers.BaseHelper):
    """
    Helper class that allows us to perform validation on data strings that are defined as xs:anyURI
    in CycloneDX schema.

    Developers can just use this via `str(XsUri('https://www.google.com'))`.

    .. note::
        See XSD definition for xsd:anyURI: http://www.datypic.com/sc/xsd/t-xsd_anyURI.html
        See JSON Schema definition for iri-reference: https://tools.ietf.org/html/rfc3987
    """

    _INVALID_URI_REGEX = re.compile(r'%(?![0-9A-F]{2})|#.*#', re.IGNORECASE + re.MULTILINE)

    __SPEC_REPLACEMENTS = (
        (' ', '%20'),
        ('"', '%22'),
        ("'", '%27'),
        ('[', '%5B'),
        (']', '%5D'),
        ('<', '%3C'),
        ('>', '%3E'),
        ('{', '%7B'),
        ('}', '%7D'),
    )

    @staticmethod
    def __spec_replace(v: str, r: tuple[str, str]) -> str:
        return v.replace(*r)

    @classmethod
    def _spec_migrate(cls, o: str) -> str:
        """
         Make a string valid to
         - XML::anyURI spec.
         - JSON::iri-reference spec.

         BEST EFFORT IMPLEMENTATION

         @see http://www.w3.org/TR/xmlschema-2/#anyURI
         @see http://www.datypic.com/sc/xsd/t-xsd_anyURI.html
         @see https://datatracker.ietf.org/doc/html/rfc2396
         @see https://datatracker.ietf.org/doc/html/rfc3987
        """
        return reduce(cls.__spec_replace, cls.__SPEC_REPLACEMENTS, o)

    def __init__(self, uri: str) -> None:
        if re.search(XsUri._INVALID_URI_REGEX, uri):
            raise InvalidUriException(
                f"Supplied value '{uri}' does not appear to be a valid URI."
            )
        self._uri = self._spec_migrate(uri)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, XsUri):
            return self._uri == other._uri
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, XsUri):
            return self._uri < other._uri
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._uri)

    def __repr__(self) -> str:
        return f'<XsUri {self._uri}>'

    def __str__(self) -> str:
        return self._uri

    @property
    @serializable.json_name('.')
    @serializable.xml_name('.')
    def uri(self) -> str:
        return self._uri

    @classmethod
    def serialize(cls, o: Any) -> str:
        if isinstance(o, XsUri):
            return str(o)
        raise SerializationOfUnexpectedValueException(
            f'Attempt to serialize a non-XsUri: {o!r}')

    @classmethod
    def deserialize(cls, o: Any) -> 'XsUri':
        try:
            return XsUri(uri=str(o))
        except ValueError as err:
            raise CycloneDxDeserializationException(
                f'XsUri string supplied does not parse: {o!r}'
            ) from err

    @classmethod
    def make_bom_link(
        cls,
        serial_number: Union[UUID, str],
        version: int = 1,
        bom_ref: Optional[Union[str, BomRef]] = None
    ) -> 'XsUri':
        """
        Generate a BOM-Link URI.

        Args:
            serial_number: The unique serial number of the BOM.
            version: The version of the BOM. The default version is 1.
            bom_ref: The unique identifier of the component, service, or vulnerability within the BOM.

        Returns:
            XsUri: Instance of XsUri with the generated BOM-Link URI.
        """
        bom_ref_part = f'#{url_quote(str(bom_ref))}' if bom_ref else ''
        return cls(f'{_BOM_LINK_PREFIX}{serial_number}/{version}{bom_ref_part}')

    def is_bom_link(self) -> bool:
        """
        Check if the URI is a BOM-Link.

        Returns:
            `bool`
        """
        return self._uri.startswith(_BOM_LINK_PREFIX)


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class ExternalReference:
    """
    This is our internal representation of an ExternalReference complex type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_externalReference
    """

    def __init__(
        self, *,
        type: ExternalReferenceType,
        url: XsUri,
        comment: Optional[str] = None,
        hashes: Optional[Iterable[HashType]] = None,
        properties: Optional[Iterable['Property']] = None,
    ) -> None:
        self.url = url
        self.comment = comment
        self.type = type
        self.hashes = hashes or []
        self.properties = properties or []

    @property
    @serializable.xml_sequence(1)
    def url(self) -> XsUri:
        """
        The URL to the external reference.

        Returns:
            `XsUri`
        """
        return self._url

    @url.setter
    def url(self, url: XsUri) -> None:
        self._url = url

    @property
    def comment(self) -> Optional[str]:
        """
        An optional comment describing the external reference.

        Returns:
            `str` if set else `None`
        """
        return self._comment

    @comment.setter
    def comment(self, comment: Optional[str]) -> None:
        self._comment = comment

    @property
    @serializable.type_mapping(_ExternalReferenceSerializationHelper)
    @serializable.xml_attribute()
    def type(self) -> ExternalReferenceType:
        """
        Specifies the type of external reference.

        There are built-in types to describe common references. If a type does not exist for the reference being
        referred to, use the "other" type.

        Returns:
            `ExternalReferenceType`
        """
        return self._type

    @type.setter
    def type(self, type: ExternalReferenceType) -> None:
        self._type = type

    @property
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.type_mapping(_HashTypeRepositorySerializationHelper)
    def hashes(self) -> 'SortedSet[HashType]':
        """
        The hashes of the external reference (if applicable).

        Returns:
            Set of `HashType`
        """
        return self._hashes

    @hashes.setter
    def hashes(self, hashes: Iterable[HashType]) -> None:
        self._hashes = SortedSet(hashes)

    @property
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    def properties(self) -> 'SortedSet[Property]':
        """
        Provides the ability to document properties in a key/value store. This provides flexibility to include data not
        officially supported in the standard without having to use additional namespaces or create extensions.

        Return:
            Set of `Property`
        """
        return self._properties

    @properties.setter
    def properties(self, properties: Iterable['Property']) -> None:
        self._properties = SortedSet(properties)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self._type, self._url, self._comment,
            _ComparableTuple(self._hashes), _ComparableTuple(self.properties),
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ExternalReference):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ExternalReference):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<ExternalReference {self.type.name}, {self.url}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Property:
    """
    This is our internal representation of `propertyType` complex type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_propertyType

    Specifies an individual property with a name and value.
    """

    def __init__(
        self, *,
        name: str,
        value: Optional[str] = None,
    ) -> None:
        self.name = name
        self.value = value

    @property
    @serializable.xml_attribute()
    def name(self) -> str:
        """
        The name of the property.

        Duplicate names are allowed, each potentially having a different value.

        Returns:
            `str`
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    @serializable.xml_name('.')
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def value(self) -> Optional[str]:
        """
        Value of this Property.

        Returns:
             `str`
        """
        return self._value

    @value.setter
    def value(self, value: Optional[str]) -> None:
        self._value = value

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.name, self.value
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Property):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Property):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Property name={self.name}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class NoteText:
    """
    This is our internal representation of the Note.text complex type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_releaseNotesType
    """

    DEFAULT_CONTENT_TYPE: str = 'text/plain'

    def __init__(
        self, *,
        content: str,
        content_type: Optional[str] = None,
        encoding: Optional[Encoding] = None,
    ) -> None:
        self.content = content
        self.content_type = content_type or NoteText.DEFAULT_CONTENT_TYPE
        self.encoding = encoding

    @property
    @serializable.xml_name('.')
    def content(self) -> str:
        """
        Get the text content of this Note.

        Returns:
            `str` note content
        """
        return self._content

    @content.setter
    def content(self, content: str) -> None:
        self._content = content

    @property
    @serializable.xml_attribute()
    @serializable.xml_name('content-type')
    def content_type(self) -> Optional[str]:
        """
        Get the content-type of this Note.

        Defaults to 'text/plain' if one was not explicitly specified.

        Returns:
            `str` content-type
        """
        return self._content_type

    @content_type.setter
    def content_type(self, content_type: str) -> None:
        self._content_type = content_type

    @property
    @serializable.xml_attribute()
    def encoding(self) -> Optional[Encoding]:
        """
        Get the encoding method used for the note's content.

        Returns:
            `Encoding` if set else `None`
        """
        return self._encoding

    @encoding.setter
    def encoding(self, encoding: Optional[Encoding]) -> None:
        self._encoding = encoding

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.content, self.content_type, self.encoding
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, NoteText):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, NoteText):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<NoteText content_type={self.content_type}, encoding={self.encoding}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Note:
    """
    This is our internal representation of the Note complex type that can be used in multiple places within
    a CycloneDX BOM document.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_releaseNotesType

    @todo: Replace ``NoteText`` with ``AttachedText``?
    """

    _LOCALE_TYPE_REGEX = re.compile(r'^[a-z]{2}(?:\-[A-Z]{2})?$')

    def __init__(
        self, *,
        text: NoteText,
        locale: Optional[str] = None,
    ) -> None:
        self.text = text
        self.locale = locale

    @property
    def text(self) -> NoteText:
        """
        Specifies the full content of the release note.

        Returns:
            `NoteText`
        """
        return self._text

    @text.setter
    def text(self, text: NoteText) -> None:
        self._text = text

    @property
    @serializable.xml_sequence(1)
    def locale(self) -> Optional[str]:
        """
        Get the ISO locale of this Note.

        The ISO-639 (or higher) language code and optional ISO-3166 (or higher) country code.

        Examples include: "en", "en-US", "fr" and "fr-CA".

        Returns:
            `str` locale if set else `None`
        """
        return self._locale

    @locale.setter
    def locale(self, locale: Optional[str]) -> None:
        self._locale = locale
        if isinstance(locale, str):
            if not re.search(Note._LOCALE_TYPE_REGEX, locale):
                self._locale = None
                raise InvalidLocaleTypeException(
                    f'Supplied locale {locale!r} is not a valid locale.'
                    ' Locale string should be formatted as the ISO-639 (or higher) language code and optional'
                    " ISO-3166 (or higher) country code. according to ISO-639 format. Examples include: 'en', 'en-US'."
                )

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.locale, self.text
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Note):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Note):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Note id={id(self)}, locale={self.locale}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class IdentifiableAction:
    """
    This is our internal representation of the `identifiableActionType` complex type.

    .. note::
        See the CycloneDX specification: https://cyclonedx.org/docs/1.7/xml/#type_identifiableActionType
    """

    def __init__(
        self, *,
        timestamp: Optional[datetime] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        self.timestamp = timestamp
        self.name = name
        self.email = email

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    def timestamp(self) -> Optional[datetime]:
        """
        The timestamp in which the action occurred.

        Returns:
            `datetime` if set else `None`
        """
        return self._timestamp

    @timestamp.setter
    def timestamp(self, timestamp: Optional[datetime]) -> None:
        self._timestamp = timestamp

    @property
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> Optional[str]:
        """
        The name of the individual who performed the action.

        Returns:
            `str` if set else `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def email(self) -> Optional[str]:
        """
        The email address of the individual who performed the action.

        Returns:
            `str` if set else `None`
        """
        return self._email

    @email.setter
    def email(self, email: Optional[str]) -> None:
        self._email = email

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.timestamp, self.name, self.email
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IdentifiableAction):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, IdentifiableAction):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<IdentifiableAction name={self.name}, email={self.email}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Copyright:
    """
    This is our internal representation of the `copyrightsType` complex type.

    .. note::
        See the CycloneDX specification: https://cyclonedx.org/docs/1.7/xml/#type_copyrightsType
    """

    def __init__(
        self, *,
        text: str,
    ) -> None:
        self.text = text

    @property
    @serializable.xml_name('.')
    def text(self) -> str:
        """
        Copyright statement.

        Returns:
            `str` if set else `None`
        """
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Copyright):
            return self._text == other._text
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Copyright):
            return self._text < other._text
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._text)

    def __repr__(self) -> str:
        return f'<Copyright text={self.text}>'
