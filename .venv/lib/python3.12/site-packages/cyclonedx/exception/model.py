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
Exceptions relating to specific conditions that occur when modelling CycloneDX BOM.
"""

from . import CycloneDxException


class CycloneDxModelException(CycloneDxException):
    """
    Base exception that covers all exceptions that may be thrown during model creation.
    """
    pass


class InvalidValueException(CycloneDxModelException):
    pass


class InvalidLocaleTypeException(CycloneDxModelException):
    """
    Raised when the supplied locale does not conform to ISO-639 specification.

    Good examples:
        - en
        - en-US
        - en-GB
        - fr
        - fr-CA

    The language code MUST be lowercase. If the country code is specified, the country code MUST be upper case.
    The language code and country code MUST be separated by a minus sign.
    """
    pass


class InvalidNistQuantumSecurityLevelException(CycloneDxModelException):
    """
    Raised when an invalid value is provided for an NIST Quantum Security Level
    as defined at https://csrc.nist.gov/projects/post-quantum-cryptography/post-quantum-cryptography-standardization/
    evaluation-criteria/security-(evaluation-criteria).
    """
    pass


class InvalidOmniBorIdException(CycloneDxModelException):
    """
    Raised when a supplied value for an OmniBOR ID does not meet the format requirements
    as defined at https://www.iana.org/assignments/uri-schemes/prov/gitoid.
    """
    pass


class InvalidRelatedCryptoMaterialSizeException(CycloneDxModelException):
    """
    Raised when the supplied size of a Related Crypto Material is negative.
    """
    pass


class InvalidSwhidException(CycloneDxModelException):
    """
    Raised when a supplied value for an Swhid does not meet the format requirements
    as defined at https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html.
    """
    pass


class InvalidUriException(CycloneDxModelException):
    """
    Raised when a `str` is provided that needs to be a valid URI, but isn't.
    """
    pass


class MutuallyExclusivePropertiesException(CycloneDxModelException):
    """
    Raised when mutually exclusive properties are provided.
    """
    pass


class NoPropertiesProvidedException(CycloneDxModelException):
    """
    Raised when attempting to construct a model class and providing NO values (where all properites are defined as
    Optional, but at least one is required).
    """
    pass


class UnknownComponentDependencyException(CycloneDxModelException):
    """
    Exception raised when a dependency has been noted for a Component that is NOT a Component BomRef in this Bom.
    """
    pass


class UnknownHashTypeException(CycloneDxModelException):
    """
    Exception raised when we are unable to determine the type of hash from a composite hash string.
    """
    pass  # TODO research deprecation of this...


class LicenseExpressionAlongWithOthersException(CycloneDxModelException):
    """
    Exception raised when a LicenseExpression was detected along with other licenses.
    If a LicenseExpression exists, than it must stand alone.

    See https://github.com/CycloneDX/specification/pull/205
    """
    pass


class InvalidCreIdException(CycloneDxModelException):
    """
    Raised when a supplied value for an CRE ID does not meet the format requirements
    as defined at https://opencre.org/
    """
    pass


class InvalidConfidenceException(CycloneDxModelException):
    """
    Raised when an invalid value is provided for a Confidence.
    The confidence of the evidence from 0 - 1, where 1 is 100% confidence.
    """
    pass
