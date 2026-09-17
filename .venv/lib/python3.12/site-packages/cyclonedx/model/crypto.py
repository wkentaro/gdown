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
This set of classes represents cryptoPropertiesType Complex Type in the CycloneDX standard.

.. note::
    Introduced in CycloneDX v1.6

.. note::
    See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
"""

from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import py_serializable as serializable
from sortedcontainers import SortedSet

from .._internal.compare import ComparableTuple as _ComparableTuple
from ..exception.model import InvalidNistQuantumSecurityLevelException, InvalidRelatedCryptoMaterialSizeException
from ..schema.schema import SchemaVersion1Dot6, SchemaVersion1Dot7
from .bom_ref import BomRef


@serializable.serializable_enum
class CryptoAssetType(str, Enum):
    """
    This is our internal representation of the cryptoPropertiesType.assetType ENUM type within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    ALGORITHM = 'algorithm'
    CERTIFICATE = 'certificate'
    PROTOCOL = 'protocol'
    RELATED_CRYPTO_MATERIAL = 'related-crypto-material'


@serializable.serializable_enum
class CryptoPrimitive(str, Enum):
    # TODO: rename to `CryptoAlgorithmPrimitive`

    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.primitive ENUM type within the
    CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    AE = 'ae'
    BLOCK_CIPHER = 'block-cipher'
    COMBINER = 'combiner'
    DRBG = 'drbg'
    HASH = 'hash'
    KDF = 'kdf'
    KEM = 'kem'
    KEY_AGREE = 'key-agree'
    KEY_WRAP = 'key-wrap'  # since CDX1.7
    MAC = 'mac'
    PKE = 'pke'
    SIGNATURE = 'signature'
    STREAM_CIPHER = 'stream-cipher'
    XOF = 'xof'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


class _CryptoPrimitiveSerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    __CASES: dict[type[serializable.ViewType], frozenset[CryptoPrimitive]] = dict()
    __CASES[SchemaVersion1Dot6] = frozenset({
        CryptoPrimitive.AE,
        CryptoPrimitive.BLOCK_CIPHER,
        CryptoPrimitive.COMBINER,
        CryptoPrimitive.DRBG,
        CryptoPrimitive.HASH,
        CryptoPrimitive.KDF,
        CryptoPrimitive.KEM,
        CryptoPrimitive.KEY_AGREE,
        CryptoPrimitive.MAC,
        CryptoPrimitive.PKE,
        CryptoPrimitive.SIGNATURE,
        CryptoPrimitive.STREAM_CIPHER,
        CryptoPrimitive.XOF,
        CryptoPrimitive.OTHER,
        CryptoPrimitive.UNKNOWN,
    })
    __CASES[SchemaVersion1Dot7] = __CASES[SchemaVersion1Dot6] | {
        CryptoPrimitive.KEY_WRAP,
    }

    @classmethod
    def __normalize(cls, cp: CryptoPrimitive, view: type[serializable.ViewType]) -> str:
        return (
            cp
            if cp in cls.__CASES.get(view, ())
            else CryptoPrimitive.OTHER
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
    def deserialize(cls, o: Any) -> CryptoPrimitive:
        return CryptoPrimitive(o)


@serializable.serializable_enum
class CryptoExecutionEnvironment(str, Enum):
    # TODO: rename to `CryptoAlgorithmExecutionEnvironment`

    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.executionEnvironment ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    HARDWARE = 'hardware'
    SOFTWARE_ENCRYPTED_RAM = 'software-encrypted-ram'
    SOFTWARE_PLAIN_RAM = 'software-plain-ram'
    SOFTWARE_TEE = 'software-tee'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class CryptoImplementationPlatform(str, Enum):
    # TODO: rename to `CryptoAlgorithmImplementationPlatform`

    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.implementationPlatform ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    ARMV7_A = 'armv7-a'
    ARMV7_M = 'armv7-m'
    ARMV8_A = 'armv8-a'
    ARMV8_M = 'armv8-m'
    ARMV9_A = 'armv9-a'
    ARMV9_M = 'armv9-m'
    PPC64 = 'ppc64'
    PPC64LE = 'ppc64le'
    S390X = 's390x'
    X86_32 = 'x86_32'
    X86_64 = 'x86_64'
    # --
    GENERIC = 'generic'
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class CryptoCertificationLevel(str, Enum):
    # TODO: rename to `CryptoAlgorithmCertificationLevel`

    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.certificationLevel ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    NONE = 'none'
    # --
    FIPS140_1_L1 = 'fips140-1-l1'
    FIPS140_1_L2 = 'fips140-1-l2'
    FIPS140_1_L3 = 'fips140-1-l3'
    FIPS140_1_L4 = 'fips140-1-l4'
    FIPS140_2_L1 = 'fips140-2-l1'
    FIPS140_2_L2 = 'fips140-2-l2'
    FIPS140_2_L3 = 'fips140-2-l3'
    FIPS140_2_L4 = 'fips140-2-l4'
    FIPS140_3_L1 = 'fips140-3-l1'
    FIPS140_3_L2 = 'fips140-3-l2'
    FIPS140_3_L3 = 'fips140-3-l3'
    FIPS140_3_L4 = 'fips140-3-l4'
    CC_EAL1 = 'cc-eal1'
    CC_EAL1_PLUS = 'cc-eal1+'
    CC_EAL2 = 'cc-eal2'
    CC_EAL2_PLUS = 'cc-eal2+'
    CC_EAL3 = 'cc-eal3'
    CC_EAL3_PLUS = 'cc-eal3+'
    CC_EAL4 = 'cc-eal4'
    CC_EAL4_PLUS = 'cc-eal4+'
    CC_EAL5 = 'cc-eal5'
    CC_EAL5_PLUS = 'cc-eal5+'
    CC_EAL6 = 'cc-eal6'
    CC_EAL6_PLUS = 'cc-eal6+'
    CC_EAL7 = 'cc-eal7'
    CC_EAL7_PLUS = 'cc-eal7+'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class CryptoMode(str, Enum):
    # TODO: rename to `CryptoAlgorithmMode`

    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.mode ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    CBC = 'cbc'
    CCM = 'ccm'
    CFB = 'cfb'
    CTR = 'ctr'
    ECB = 'ecb'
    GCM = 'gcm'
    OFB = 'ofb'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class CryptoPadding(str, Enum):
    # TODO: rename to `CryptoAlgorithmPadding`

    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.padding ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    PKCS5 = 'pkcs5'
    PKCS7 = 'pkcs7'
    PKCS1V15 = 'pkcs1v15'
    OAEP = 'oaep'
    RAW = 'raw'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class CryptoFunction(str, Enum):
    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties.cryptoFunctions.cryptoFunction
    ENUM type within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    DECAPSULATE = 'decapsulate'
    DECRYPT = 'decrypt'
    DIGEST = 'digest'
    ENCAPSULATE = 'encapsulate'
    ENCRYPT = 'encrypt'
    GENERATE = 'generate'
    KEYDERIVE = 'keyderive'
    KEYGEN = 'keygen'
    SIGN = 'sign'
    TAG = 'tag'
    VERIFY = 'verify'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class AlgorithmProperties:
    """
    This is our internal representation of the cryptoPropertiesType.algorithmProperties ENUM type within the CycloneDX
    standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        primitive: Optional[CryptoPrimitive] = None,
        parameter_set_identifier: Optional[str] = None,
        curve: Optional[str] = None,
        execution_environment: Optional[CryptoExecutionEnvironment] = None,
        implementation_platform: Optional[CryptoImplementationPlatform] = None,
        certification_levels: Optional[Iterable[CryptoCertificationLevel]] = None,
        mode: Optional[CryptoMode] = None,
        padding: Optional[CryptoPadding] = None,
        crypto_functions: Optional[Iterable[CryptoFunction]] = None,
        classical_security_level: Optional[int] = None,
        nist_quantum_security_level: Optional[int] = None,
    ) -> None:
        self.primitive = primitive
        self.parameter_set_identifier = parameter_set_identifier
        self.curve = curve
        self.execution_environment = execution_environment
        self.implementation_platform = implementation_platform
        self.certification_levels = certification_levels or []
        self.mode = mode
        self.padding = padding
        self.crypto_functions = crypto_functions or []
        self.classical_security_level = classical_security_level
        self.nist_quantum_security_level = nist_quantum_security_level

    @property
    @serializable.type_mapping(_CryptoPrimitiveSerializationHelper)
    @serializable.xml_sequence(1)
    def primitive(self) -> Optional[CryptoPrimitive]:
        """
        Cryptographic building blocks used in higher-level cryptographic systems and protocols.

        Primitives represent different cryptographic routines: deterministic random bit generators (drbg, e.g. CTR_DRBG
        from NIST SP800-90A-r1), message authentication codes (mac, e.g. HMAC-SHA-256), blockciphers (e.g. AES),
        streamciphers (e.g. Salsa20), signatures (e.g. ECDSA), hash functions (e.g. SHA-256),
        public-key encryption schemes (pke, e.g. RSA), extended output functions (xof, e.g. SHAKE256),
        key derivation functions (e.g. pbkdf2), key agreement algorithms (e.g. ECDH),
        key encapsulation mechanisms (e.g. ML-KEM), authenticated encryption (ae, e.g. AES-GCM) and the combination of
        multiple algorithms (combiner, e.g. SP800-56Cr2).

        Returns:
            `CryptoPrimitive` or `None`
        """
        return self._primitive

    @primitive.setter
    def primitive(self, primitive: Optional[CryptoPrimitive]) -> None:
        self._primitive = primitive

    @property
    @serializable.xml_sequence(2)
    def parameter_set_identifier(self) -> Optional[str]:
        """
        An identifier for the parameter set of the cryptographic algorithm. Examples: in AES128, '128' identifies the
        key length in bits, in SHA256, '256' identifies the digest length, '128' in SHAKE128 identifies its maximum
        security level in bits, and 'SHA2-128s' identifies a parameter set used in SLH-DSA (FIPS205).

        Returns:
            `str` or `None`
        """
        return self._parameter_set_identifier

    @parameter_set_identifier.setter
    def parameter_set_identifier(self, parameter_set_identifier: Optional[str]) -> None:
        self._parameter_set_identifier = parameter_set_identifier

    @property
    @serializable.xml_sequence(3)
    def curve(self) -> Optional[str]:
        """
        The specific underlying Elliptic Curve (EC) definition employed which is an indicator of the level of security
        strength, performance and complexity. Absent an authoritative source of curve names, CycloneDX recommends use
        of curve names as defined at https://neuromancer.sk/std/, the source from which can be found at
        https://github.com/J08nY/std-curves.

        Returns:
            `str` or `None`
        """
        return self._curve

    @curve.setter
    def curve(self, curve: Optional[str]) -> None:
        self._curve = curve

    @property
    @serializable.xml_sequence(4)
    def execution_environment(self) -> Optional[CryptoExecutionEnvironment]:
        """
        The target and execution environment in which the algorithm is implemented in.

        Returns:
             `CryptoExecutionEnvironment` or `None`
        """
        return self._execution_environment

    @execution_environment.setter
    def execution_environment(self, execution_environment: Optional[CryptoExecutionEnvironment]) -> None:
        self._execution_environment = execution_environment

    @property
    @serializable.xml_sequence(4)
    def implementation_platform(self) -> Optional[CryptoImplementationPlatform]:
        """
        The target platform for which the algorithm is implemented. The implementation can be 'generic', running on
        any platform or for a specific platform.

        Returns:
             `CryptoImplementationPlatform` or `None`
        """
        return self._implementation_platform

    @implementation_platform.setter
    def implementation_platform(self, implementation_platform: Optional[CryptoImplementationPlatform]) -> None:
        self._implementation_platform = implementation_platform

    @property
    @serializable.json_name('certificationLevel')
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, child_name='certificationLevel')
    @serializable.xml_sequence(5)
    def certification_levels(self) -> 'SortedSet[CryptoCertificationLevel]':
        """
        The certification that the implementation of the cryptographic algorithm has received, if any. Certifications
        include revisions and levels of FIPS 140 or Common Criteria of different Extended Assurance Levels (CC-EAL).

        Returns:
            `Iterable[CryptoCertificationLevel]`
        """
        return self._certification_levels

    @certification_levels.setter
    def certification_levels(self, certification_levels: Iterable[CryptoCertificationLevel]) -> None:
        self._certification_levels = SortedSet(certification_levels)

    @property
    @serializable.xml_sequence(6)
    def mode(self) -> Optional[CryptoMode]:
        """
        The mode of operation in which the cryptographic algorithm (block cipher) is used.

        Returns:
             `CryptoMode` or `None`
        """
        return self._mode

    @mode.setter
    def mode(self, mode: Optional[CryptoMode]) -> None:
        self._mode = mode

    @property
    @serializable.xml_sequence(8)
    def padding(self) -> Optional[CryptoPadding]:
        """
        The padding scheme that is used for the cryptographic algorithm.

        Returns:
             `CryptoPadding` or `None`
        """
        return self._padding

    @padding.setter
    def padding(self, padding: Optional[CryptoPadding]) -> None:
        self._padding = padding

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, child_name='cryptoFunction')
    @serializable.xml_sequence(9)
    def crypto_functions(self) -> 'SortedSet[CryptoFunction]':
        """
        The cryptographic functions implemented by the cryptographic algorithm.

        Returns:
            `Iterable[CryptoFunction]`
        """
        return self._crypto_functions

    @crypto_functions.setter
    def crypto_functions(self, crypto_functions: Iterable[CryptoFunction]) -> None:
        self._crypto_functions = SortedSet(crypto_functions)

    @property
    @serializable.xml_sequence(10)
    def classical_security_level(self) -> Optional[int]:
        """
        The classical security level that a cryptographic algorithm provides (in bits).

        Returns:
            `int` or `None`
        """
        return self._classical_security_level

    @classical_security_level.setter
    def classical_security_level(self, classical_security_level: Optional[int]) -> None:
        self._classical_security_level = classical_security_level

    @property
    @serializable.xml_sequence(11)
    def nist_quantum_security_level(self) -> Optional[int]:
        """
        The NIST security strength category as defined in
        https://csrc.nist.gov/projects/post-quantum-cryptography/post-quantum-cryptography-standardization/
        evaluation-criteria/security-(evaluation-criteria). A value of 0 indicates that none of the categories are met.

        Returns:
            `int` or `None`
        """
        return self._nist_quantum_security_level

    @nist_quantum_security_level.setter
    def nist_quantum_security_level(self, nist_quantum_security_level: Optional[int]) -> None:
        if nist_quantum_security_level is not None and (
            nist_quantum_security_level < 0
            or nist_quantum_security_level > 6
        ):
            raise InvalidNistQuantumSecurityLevelException(
                'NIST Quantum Security Level must be (0 <= value <= 6)'
            )
        self._nist_quantum_security_level = nist_quantum_security_level

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.primitive, self._parameter_set_identifier, self.curve, self.execution_environment,
            self.implementation_platform, _ComparableTuple(self.certification_levels), self.mode, self.padding,
            _ComparableTuple(self.crypto_functions), self.classical_security_level, self.nist_quantum_security_level,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AlgorithmProperties):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, AlgorithmProperties):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<AlgorithmProperties primitive={self.primitive}, execution_environment={self.execution_environment}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class CertificateProperties:
    """
    This is our internal representation of the `cryptoPropertiesType.certificateProperties` complex type within
    CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        subject_name: Optional[str] = None,
        issuer_name: Optional[str] = None,
        not_valid_before: Optional[datetime] = None,
        not_valid_after: Optional[datetime] = None,
        signature_algorithm_ref: Optional[BomRef] = None,
        subject_public_key_ref: Optional[BomRef] = None,
        certificate_format: Optional[str] = None,
        certificate_extension: Optional[str] = None,
    ) -> None:
        self.subject_name = subject_name
        self.issuer_name = issuer_name
        self.not_valid_before = not_valid_before
        self.not_valid_after = not_valid_after
        self.signature_algorithm_ref = signature_algorithm_ref
        self.subject_public_key_ref = subject_public_key_ref
        self.certificate_format = certificate_format
        self.certificate_extension = certificate_extension

    @property
    @serializable.xml_sequence(10)
    def subject_name(self) -> Optional[str]:
        """
        The subject name for the certificate.

        Returns:
            `str` or `None`
        """
        return self._subject_name

    @subject_name.setter
    def subject_name(self, subject_name: Optional[str]) -> None:
        self._subject_name = subject_name

    @property
    @serializable.xml_sequence(20)
    def issuer_name(self) -> Optional[str]:
        """
        The issuer name for the certificate.

        Returns:
            `str` or `None`
        """
        return self._issuer_name

    @issuer_name.setter
    def issuer_name(self, issuer_name: Optional[str]) -> None:
        self._issuer_name = issuer_name

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(30)
    def not_valid_before(self) -> Optional[datetime]:
        """
        The date and time according to ISO-8601 standard from which the certificate is valid.

        Returns:
            `datetime` or `None`
        """
        return self._not_valid_before

    @not_valid_before.setter
    def not_valid_before(self, not_valid_before: Optional[datetime]) -> None:
        self._not_valid_before = not_valid_before

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(40)
    def not_valid_after(self) -> Optional[datetime]:
        """
        The date and time according to ISO-8601 standard from which the certificate is not valid anymore.

        Returns:
            `datetime` or `None`
        """
        return self._not_valid_after

    @not_valid_after.setter
    def not_valid_after(self, not_valid_after: Optional[datetime]) -> None:
        self._not_valid_after = not_valid_after

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_sequence(50)
    def signature_algorithm_ref(self) -> Optional[BomRef]:
        """
        The bom-ref to signature algorithm used by the certificate.

        Returns:
            `BomRef` or `None`
        """
        return self._signature_algorithm_ref

    @signature_algorithm_ref.setter
    def signature_algorithm_ref(self, signature_algorithm_ref: Optional[BomRef]) -> None:
        self._signature_algorithm_ref = signature_algorithm_ref

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_sequence(60)
    def subject_public_key_ref(self) -> Optional[BomRef]:
        """
        The bom-ref to the public key of the subject.

        Returns:
            `BomRef` or `None`
        """
        return self._subject_public_key_ref

    @subject_public_key_ref.setter
    def subject_public_key_ref(self, subject_public_key_ref: Optional[BomRef]) -> None:
        self._subject_public_key_ref = subject_public_key_ref

    @property
    @serializable.xml_sequence(70)
    def certificate_format(self) -> Optional[str]:
        """
        The format of the certificate. Examples include X.509, PEM, DER, and CVC.

        Returns:
            `str` or `None`
        """
        return self._certificate_format

    @certificate_format.setter
    def certificate_format(self, certificate_format: Optional[str]) -> None:
        self._certificate_format = certificate_format

    @property
    @serializable.xml_sequence(80)
    def certificate_extension(self) -> Optional[str]:
        """
        The file extension of the certificate. Examples include crt, pem, cer, der, and p12.

        Returns:
            `str` or `None`
        """
        return self._certificate_extension

    @certificate_extension.setter
    def certificate_extension(self, certificate_extension: Optional[str]) -> None:
        self._certificate_extension = certificate_extension

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.subject_name, self.issuer_name, self.not_valid_before, self.not_valid_after,
            self.certificate_format, self.certificate_extension
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CertificateProperties):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, CertificateProperties):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<CertificateProperties subject_name={self.subject_name}, certificate_format={self.certificate_format}>'


@serializable.serializable_enum
class RelatedCryptoMaterialType(str, Enum):
    """
    This is our internal representation of the cryptoPropertiesType.relatedCryptoMaterialProperties.type ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    ADDITIONAL_DATA = 'additional-data'
    CIPHERTEXT = 'ciphertext'
    CREDENTIAL = 'credential'
    DIGEST = 'digest'
    INITIALIZATION_VECTOR = 'initialization-vector'
    KEY = 'key'
    NONCE = 'nonce'
    PASSWORD = 'password'  # nosec
    PRIVATE_KEY = 'private-key'
    PUBLIC_KEY = 'public-key'
    SALT = 'salt'
    SECRET_KEY = 'secret-key'  # nosec
    SEED = 'seed'
    SHARED_SECRET = 'shared-secret'  # nosec
    SIGNATURE = 'signature'
    TAG = 'tag'
    TOKEN = 'token'  # nosec
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class RelatedCryptoMaterialState(str, Enum):
    """
    This is our internal representation of the cryptoPropertiesType.relatedCryptoMaterialProperties.state ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    ACTIVE = 'active'
    COMPROMISED = 'compromised'
    DEACTIVATED = 'deactivated'
    DESTROYED = 'destroyed'
    PRE_ACTIVATION = 'pre-activation'
    SUSPENDED = 'suspended'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class RelatedCryptoMaterialSecuredBy:
    """
    This is our internal representation of the `cryptoPropertiesType.relatedCryptoMaterialProperties.securedBy` complex
    type within CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        mechanism: Optional[str] = None,
        algorithm_ref: Optional[BomRef] = None,
    ) -> None:
        self.mechanism = mechanism
        self.algorithm_ref = algorithm_ref

    @property
    @serializable.xml_sequence(10)
    def mechanism(self) -> Optional[str]:
        """
        Specifies the mechanism by which the cryptographic asset is secured by.
        Examples include HSM, TPM, XGX, Software, and None.

        Returns:
            `str` or `None`
        """
        return self._mechanism

    @mechanism.setter
    def mechanism(self, mechanism: Optional[str]) -> None:
        self._mechanism = mechanism

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_sequence(20)
    def algorithm_ref(self) -> Optional[BomRef]:
        """
        The bom-ref to the algorithm.

        Returns:
            `BomRef` or `None`
        """
        return self._algorithm_ref

    @algorithm_ref.setter
    def algorithm_ref(self, algorithm_ref: Optional[BomRef]) -> None:
        self._algorithm_ref = algorithm_ref

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.mechanism, self.algorithm_ref
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RelatedCryptoMaterialSecuredBy):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, RelatedCryptoMaterialSecuredBy):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<RelatedCryptoMaterialSecuredBy mechanism={self.mechanism}, algorithm_ref={self.algorithm_ref}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class RelatedCryptoMaterialProperties:
    """
    This is our internal representation of the `cryptoPropertiesType.relatedCryptoMaterialProperties` complex type
    within CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        type: Optional[RelatedCryptoMaterialType] = None,
        id: Optional[str] = None,
        state: Optional[RelatedCryptoMaterialState] = None,
        algorithm_ref: Optional[BomRef] = None,
        creation_date: Optional[datetime] = None,
        activation_date: Optional[datetime] = None,
        update_date: Optional[datetime] = None,
        expiration_date: Optional[datetime] = None,
        value: Optional[str] = None,
        size: Optional[int] = None,
        format: Optional[str] = None,
        secured_by: Optional[RelatedCryptoMaterialSecuredBy] = None,
    ) -> None:
        self.type = type
        self.id = id
        self.state = state
        self.algorithm_ref = algorithm_ref
        self.creation_date = creation_date
        self.activation_date = activation_date
        self.update_date = update_date
        self.expiration_date = expiration_date
        self.value = value
        self.size = size
        self.format = format
        self.secured_by = secured_by

    @property
    @serializable.xml_sequence(10)
    def type(self) -> Optional[RelatedCryptoMaterialType]:
        """
        The type for the related cryptographic material.

        Returns
        """
        return self._type

    @type.setter
    def type(self, type: Optional[RelatedCryptoMaterialType]) -> None:
        self._type = type

    @property
    @serializable.xml_sequence(20)
    def id(self) -> Optional[str]:
        """
        The optional unique identifier for the related cryptographic material.

        :return:
        """
        return self._id

    @id.setter
    def id(self, id: Optional[str]) -> None:
        self._id = id

    @property
    @serializable.xml_sequence(30)
    def state(self) -> Optional[RelatedCryptoMaterialState]:
        """
        The key state as defined by NIST SP 800-57.

        Returns:
             `RelatedCryptoMaterialState` or `None`
        """
        return self._state

    @state.setter
    def state(self, state: Optional[RelatedCryptoMaterialState]) -> None:
        self._state = state

    @property
    @serializable.type_mapping(BomRef)
    @serializable.xml_sequence(40)
    def algorithm_ref(self) -> Optional[BomRef]:
        """
        The bom-ref to the algorithm used to generate the related cryptographic material.

        Returns:
            `BomRef` or `None`
        """
        return self._algorithm_ref

    @algorithm_ref.setter
    def algorithm_ref(self, algorithm_ref: Optional[BomRef]) -> None:
        self._algorithm_ref = algorithm_ref

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(50)
    def creation_date(self) -> Optional[datetime]:
        """
        The date and time (timestamp) when the related cryptographic material was created.

        Returns:
            `datetime` or `None`
        """
        return self._creation_date

    @creation_date.setter
    def creation_date(self, creation_date: Optional[datetime]) -> None:
        self._creation_date = creation_date

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(60)
    def activation_date(self) -> Optional[datetime]:
        """
        The date and time (timestamp) when the related cryptographic material was activated.

        Returns:
            `datetime` or `None`
        """
        return self._activation_date

    @activation_date.setter
    def activation_date(self, activation_date: Optional[datetime]) -> None:
        self._activation_date = activation_date

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(70)
    def update_date(self) -> Optional[datetime]:
        """
        The date and time (timestamp) when the related cryptographic material was updated.

        Returns:
            `datetime` or `None`
        """
        return self._update_date

    @update_date.setter
    def update_date(self, update_date: Optional[datetime]) -> None:
        self._update_date = update_date

    @property
    @serializable.type_mapping(serializable.helpers.XsdDateTime)
    @serializable.xml_sequence(80)
    def expiration_date(self) -> Optional[datetime]:
        """
        The date and time (timestamp) when the related cryptographic material expires.

        Returns:
            `datetime` or `None`
        """
        return self._expiration_date

    @expiration_date.setter
    def expiration_date(self, expiration_date: Optional[datetime]) -> None:
        self._expiration_date = expiration_date

    @property
    @serializable.xml_sequence(90)
    def value(self) -> Optional[str]:
        """
        The associated value of the cryptographic material.

        Returns:
            `str` or `None`
        """
        return self._value

    @value.setter
    def value(self, value: Optional[str]) -> None:
        self._value = value

    @property
    @serializable.xml_sequence(100)
    def size(self) -> Optional[int]:
        """
        The size of the cryptographic asset (in bits).

        Returns:
             `int` or `None`
        """
        return self._size

    @size.setter
    def size(self, size: Optional[int]) -> None:
        if size and size < 0:
            raise InvalidRelatedCryptoMaterialSizeException('Size must be greater than zero')
        self._size = size

    @property
    @serializable.xml_sequence(110)
    def format(self) -> Optional[str]:
        """
        The format of the related cryptographic material (e.g. P8, PEM, DER).

        Returns:
            `str` or `None`
        """
        return self._format

    @format.setter
    def format(self, format: Optional[str]) -> None:
        self._format = format

    @property
    @serializable.xml_sequence(120)
    def secured_by(self) -> Optional[RelatedCryptoMaterialSecuredBy]:
        """
        The mechanism by which the cryptographic asset is secured by.

        Returns:
            `RelatedCryptoMaterialSecuredBy` or `None`
        """
        return self._secured_by

    @secured_by.setter
    def secured_by(self, secured_by: Optional[RelatedCryptoMaterialSecuredBy]) -> None:
        self._secured_by = secured_by

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.type, self.id, self.state, self.algorithm_ref, self.creation_date, self.activation_date,
            self.update_date, self.expiration_date, self.value, self.size, self.format, self.secured_by
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RelatedCryptoMaterialProperties):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, RelatedCryptoMaterialProperties):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<RelatedCryptoMaterialProperties type={self.type}, id={self.id} state={self.state}>'


@serializable.serializable_enum
class ProtocolPropertiesType(str, Enum):
    """
    This is our internal representation of the cryptoPropertiesType.protocolProperties.type ENUM type
    within the CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6

    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    DTLS = 'dtls'  # since CDX1.7
    EAP_AKA = 'eap-aka'  # since CDX1.7
    EAP_AKA_PRIME = 'eap-aka-prime'  # since CDX1.7
    FIVEG_AKA = '5g-aka'  # since CDX1.7
    IKE = 'ike'
    IPSEC = 'ipsec'
    PRINS = 'prins'  # since CDX1.7
    QUIC = 'quic'  # since CDX1.7
    SSH = 'ssh'
    SSTP = 'sstp'
    TLS = 'tls'
    WPA = 'wpa'
    # --
    OTHER = 'other'
    UNKNOWN = 'unknown'


class _ProtocolPropertiesTypeSerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    __CASES: dict[type[serializable.ViewType], frozenset[ProtocolPropertiesType]] = dict()
    __CASES[SchemaVersion1Dot6] = frozenset({
        ProtocolPropertiesType.IKE,
        ProtocolPropertiesType.IPSEC,
        ProtocolPropertiesType.SSH,
        ProtocolPropertiesType.SSTP,
        ProtocolPropertiesType.TLS,
        ProtocolPropertiesType.WPA,
        ProtocolPropertiesType.OTHER,
        ProtocolPropertiesType.UNKNOWN,
    })
    __CASES[SchemaVersion1Dot7] = __CASES[SchemaVersion1Dot6] | {
        ProtocolPropertiesType.DTLS,
        ProtocolPropertiesType.EAP_AKA,
        ProtocolPropertiesType.EAP_AKA_PRIME,
        ProtocolPropertiesType.FIVEG_AKA,
        ProtocolPropertiesType.PRINS,
        ProtocolPropertiesType.QUIC,
    }

    @classmethod
    def __normalize(cls, ppt: ProtocolPropertiesType, view: type[serializable.ViewType]) -> str:
        return (
            ppt
            if ppt in cls.__CASES.get(view, ())
            else ProtocolPropertiesType.OTHER
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
    def deserialize(cls, o: Any) -> ProtocolPropertiesType:
        return ProtocolPropertiesType(o)


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class ProtocolPropertiesCipherSuite:
    """
    This is our internal representation of the `cryptoPropertiesType.protocolProperties.cipherSuites.cipherSuite`
    complex type within CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        name: Optional[str] = None,
        algorithms: Optional[Iterable[BomRef]] = None,
        identifiers: Optional[Iterable[str]] = None,
    ) -> None:
        self.name = name
        self.algorithms = algorithms or []
        self.identifiers = identifiers or []

    @property
    @serializable.xml_sequence(10)
    def name(self) -> Optional[str]:
        """
        A common name for the cipher suite. For example: TLS_DHE_RSA_WITH_AES_128_CCM.

        Returns:
            `str` or `None`
        """
        return self._name

    @name.setter
    def name(self, name: Optional[str]) -> None:
        self._name = name

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'algorithm')
    @serializable.xml_sequence(20)
    def algorithms(self) -> 'SortedSet[BomRef]':
        """
        A list BomRefs to algorithms related to the cipher suite.

        Returns:
            `Iterable[BomRef]` or `None`
        """
        return self._algorithms

    @algorithms.setter
    def algorithms(self, algorithms: Iterable[BomRef]) -> None:
        self._algorithms = SortedSet(algorithms)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'identifier')
    @serializable.xml_sequence(20)
    def identifiers(self) -> 'SortedSet[str]':
        """
        A list of common identifiers for the cipher suite. Examples include 0xC0 and 0x9E.

        Returns:
            `Iterable[str]` or `None`
        """
        return self._identifiers

    @identifiers.setter
    def identifiers(self, identifiers: Iterable[str]) -> None:
        self._identifiers = SortedSet(identifiers)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.name, _ComparableTuple(self.algorithms), _ComparableTuple(self.identifiers)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ProtocolPropertiesCipherSuite):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ProtocolPropertiesCipherSuite):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<ProtocolPropertiesCipherSuite name={self.name}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Ikev2TransformTypes:
    """
    This is our internal representation of the `cryptoPropertiesType.protocolProperties.ikev2TransformTypes`
    complex type within CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        encr: Optional[Iterable[BomRef]] = None,
        prf: Optional[Iterable[BomRef]] = None,
        integ: Optional[Iterable[BomRef]] = None,
        ke: Optional[Iterable[BomRef]] = None,
        esn: Optional[bool] = None,
        auth: Optional[Iterable[BomRef]] = None,
    ) -> None:
        self.encr = encr or []
        self.prf = prf or []
        self.integ = integ or []
        self.ke = ke or []
        self.esn = esn
        self.auth = auth or []

    @property
    @serializable.xml_sequence(10)
    def encr(self) -> 'SortedSet[BomRef]':
        """
        Transform Type 1: encryption algorithms.

        Returns:
            `Iterable[BomRef]` or `None`
        """
        return self._encr

    @encr.setter
    def encr(self, encr: Iterable[BomRef]) -> None:
        self._encr = SortedSet(encr)

    @property
    @serializable.xml_sequence(20)
    def prf(self) -> 'SortedSet[BomRef]':
        """
        Transform Type 2: pseudorandom functions.

        Returns:
            `Iterable[BomRef]` or `None`
        """
        return self._prf

    @prf.setter
    def prf(self, prf: Iterable[BomRef]) -> None:
        self._prf = SortedSet(prf)

    @property
    @serializable.xml_sequence(30)
    def integ(self) -> 'SortedSet[BomRef]':
        """
        Transform Type 3: integrity algorithms.

        Returns:
            `Iterable[BomRef]` or `None`
        """
        return self._integ

    @integ.setter
    def integ(self, integ: Iterable[BomRef]) -> None:
        self._integ = SortedSet(integ)

    @property
    @serializable.xml_sequence(40)
    def ke(self) -> 'SortedSet[BomRef]':
        """
        Transform Type 4: Key Exchange Method (KE) per RFC9370, formerly called Diffie-Hellman Group (D-H).

        Returns:
            `Iterable[BomRef]` or `None`
        """
        return self._ke

    @ke.setter
    def ke(self, ke: Iterable[BomRef]) -> None:
        self._ke = SortedSet(ke)

    @property
    @serializable.xml_sequence(50)
    def esn(self) -> Optional[bool]:
        """
        Specifies if an Extended Sequence Number (ESN) is used.

        Returns:
            `bool` or `None`
        """
        return self._esn

    @esn.setter
    def esn(self, esn: Optional[bool]) -> None:
        self._esn = esn

    @property
    @serializable.xml_sequence(60)
    def auth(self) -> 'SortedSet[BomRef]':
        """
        IKEv2 Authentication method.

        Returns:
            `Iterable[BomRef]` or `None`
        """
        return self._auth

    @auth.setter
    def auth(self, auth: Iterable[BomRef]) -> None:
        self._auth = SortedSet(auth)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            _ComparableTuple(self.encr),
            _ComparableTuple(self.prf),
            _ComparableTuple(self.integ),
            _ComparableTuple(self.ke),
            self.esn,
            _ComparableTuple(self.auth)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Ikev2TransformTypes):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Ikev2TransformTypes):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Ikev2TransformTypes esn={self.esn}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class ProtocolProperties:
    """
    This is our internal representation of the `cryptoPropertiesType.protocolProperties` complex type within
    CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        type: Optional[ProtocolPropertiesType] = None,
        version: Optional[str] = None,
        cipher_suites: Optional[Iterable[ProtocolPropertiesCipherSuite]] = None,
        ikev2_transform_types: Optional[Ikev2TransformTypes] = None,
        crypto_refs: Optional[Iterable[BomRef]] = None,
    ) -> None:
        self.type = type
        self.version = version
        self.cipher_suites = cipher_suites or []
        self.ikev2_transform_types = ikev2_transform_types
        self.crypto_refs = crypto_refs or []

    @property
    @serializable.type_mapping(_ProtocolPropertiesTypeSerializationHelper)
    @serializable.xml_sequence(10)
    def type(self) -> Optional[ProtocolPropertiesType]:
        """
        The concrete protocol type.

        Returns:
            `ProtocolPropertiesType` or `None`
        """
        return self._type

    @type.setter
    def type(self, type: Optional[ProtocolPropertiesType]) -> None:
        self._type = type

    @property
    @serializable.xml_sequence(20)
    def version(self) -> Optional[str]:
        """
        The version of the protocol. Examples include 1.0, 1.2, and 1.99.

        Returns:
            `str` or `None`
        """
        return self._version

    @version.setter
    def version(self, version: Optional[str]) -> None:
        self._version = version

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'cipherSuite')
    @serializable.xml_sequence(30)
    def cipher_suites(self) -> 'SortedSet[ProtocolPropertiesCipherSuite]':
        """
        A list of cipher suites related to the protocol.

        Returns:
            `Iterable[ProtocolPropertiesCipherSuite]`
        """
        return self._cipher_suites

    @cipher_suites.setter
    def cipher_suites(self, cipher_suites: Iterable[ProtocolPropertiesCipherSuite]) -> None:
        self._cipher_suites = SortedSet(cipher_suites)

    @property
    @serializable.xml_sequence(40)
    def ikev2_transform_types(self) -> Optional[Ikev2TransformTypes]:
        """
        The IKEv2 transform types supported (types 1-4), defined in RFC7296 section 3.3.2, and additional properties.

        Returns:
            `Ikev2TransformTypes` or `None`
        """
        return self._ikev2_transform_types

    @ikev2_transform_types.setter
    def ikev2_transform_types(self, ikev2_transform_types: Optional[Ikev2TransformTypes]) -> None:
        self._ikev2_transform_types = ikev2_transform_types

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, 'cryptoRef')
    @serializable.json_name('cryptoRefArray')
    def crypto_refs(self) -> 'SortedSet[BomRef]':
        """
        A list of protocol-related cryptographic assets.

        Returns:
            `Iterable[BomRef]`
        """
        return self._crypto_refs

    @crypto_refs.setter
    def crypto_refs(self, crypto_refs: Iterable[BomRef]) -> None:
        self._crypto_refs = SortedSet(crypto_refs)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.type,
            self.version,
            _ComparableTuple(self.cipher_suites),
            self.ikev2_transform_types,
            _ComparableTuple(self.crypto_refs)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ProtocolProperties):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ProtocolProperties):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<ProtocolProperties type={self.type}, version={self.version}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class CryptoProperties:
    """
    This is our internal representation of the `cryptoPropertiesType` complex type within CycloneDX standard.

    .. note::
        Introduced in CycloneDX v1.6


    .. note::
        See the CycloneDX Schema for hashType: https://cyclonedx.org/docs/1.7/xml/#type_cryptoPropertiesType
    """

    def __init__(
        self, *,
        asset_type: Optional[CryptoAssetType] = None,
        algorithm_properties: Optional[AlgorithmProperties] = None,
        certificate_properties: Optional[CertificateProperties] = None,
        related_crypto_material_properties: Optional[RelatedCryptoMaterialProperties] = None,
        protocol_properties: Optional[ProtocolProperties] = None,
        oid: Optional[str] = None,
    ) -> None:
        self.asset_type = asset_type
        self.algorithm_properties = algorithm_properties
        self.certificate_properties = certificate_properties
        self.related_crypto_material_properties = related_crypto_material_properties
        self.protocol_properties = protocol_properties
        self.oid = oid

    @property
    @serializable.xml_sequence(10)
    def asset_type(self) -> Optional[CryptoAssetType]:
        """
        Cryptographic assets occur in several forms. Algorithms and protocols are most commonly implemented in
        specialized cryptographic libraries. They may however also be 'hardcoded' in software components. Certificates
        and related cryptographic material like keys, tokens, secrets or passwords are other cryptographic assets to be
        modelled.

        Returns:
            `CryptoAssetType`
        """
        return self._asset_type

    @asset_type.setter
    def asset_type(self, asset_type: Optional[CryptoAssetType]) -> None:
        self._asset_type = asset_type

    @property
    @serializable.xml_sequence(20)
    def algorithm_properties(self) -> Optional[AlgorithmProperties]:
        """
        Additional properties specific to a cryptographic algorithm.

        Returns:
            `AlgorithmProperties` or `None`
        """
        return self._algorithm_properties

    @algorithm_properties.setter
    def algorithm_properties(self, algorithm_properties: Optional[AlgorithmProperties]) -> None:
        self._algorithm_properties = algorithm_properties

    @property
    @serializable.xml_sequence(30)
    def certificate_properties(self) -> Optional[CertificateProperties]:
        """
        Properties for cryptographic assets of asset type 'certificate'.

        Returns:
            `CertificateProperties` or `None`
        """
        return self._certificate_properties

    @certificate_properties.setter
    def certificate_properties(self, certificate_properties: Optional[CertificateProperties]) -> None:
        self._certificate_properties = certificate_properties

    @property
    @serializable.xml_sequence(40)
    def related_crypto_material_properties(self) -> Optional[RelatedCryptoMaterialProperties]:
        """
        Properties for cryptographic assets of asset type 'relatedCryptoMaterial'.

        Returns:
            `RelatedCryptoMaterialProperties` or `None`
        """
        return self._related_crypto_material_properties

    @related_crypto_material_properties.setter
    def related_crypto_material_properties(
        self,
        related_crypto_material_properties: Optional[RelatedCryptoMaterialProperties]
    ) -> None:
        self._related_crypto_material_properties = related_crypto_material_properties

    @property
    @serializable.xml_sequence(50)
    def protocol_properties(self) -> Optional[ProtocolProperties]:
        """
        Properties specific to cryptographic assets of type: 'protocol'.

        Returns:
            `ProtocolProperties` or `None`
        """
        return self._protocol_properties

    @protocol_properties.setter
    def protocol_properties(self, protocol_properties: Optional[ProtocolProperties]) -> None:
        self._protocol_properties = protocol_properties

    @property
    @serializable.xml_sequence(60)
    def oid(self) -> Optional[str]:
        """
        The object identifier (OID) of the cryptographic asset.

        Returns:
            `str` or `None`
        """
        return self._oid

    @oid.setter
    def oid(self, oid: Optional[str]) -> None:
        self._oid = oid

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.asset_type,
            self.algorithm_properties,
            self.certificate_properties,
            self.related_crypto_material_properties,
            self.protocol_properties,
            self.oid,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CryptoProperties):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, CryptoProperties):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<CryptoProperties asset_type={self.asset_type}, oid={self.oid}>'
