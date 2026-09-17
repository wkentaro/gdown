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
This set of classes represents the data about Impact Analysis.

Impact Analysis is new for CycloneDX schema version 1.

.. note::
    See the CycloneDX Schema extension definition https://cyclonedx.org/docs/1.6
"""


from enum import Enum

import py_serializable as serializable


@serializable.serializable_enum
class ImpactAnalysisAffectedStatus(str, Enum):
    """
    Enum object that defines the permissible impact analysis affected states.

    The vulnerability status of a given version or range of versions of a product.

    The statuses 'affected' and 'unaffected' indicate that the version is affected or unaffected by the vulnerability.

    The status 'unknown' indicates that it is unknown or unspecified whether the given version is affected. There can
    be many reasons for an 'unknown' status, including that an investigation has not been undertaken or that a vendor
    has not disclosed the status.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_impactAnalysisAffectedStatusType
    """

    AFFECTED = 'affected'
    UNAFFECTED = 'unaffected'
    UNKNOWN = 'unknown'


@serializable.serializable_enum
class ImpactAnalysisJustification(str, Enum):
    """
    Enum object that defines the rationale of why the impact analysis state was asserted.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_impactAnalysisJustificationType
    """

    CODE_NOT_PRESENT = 'code_not_present'
    CODE_NOT_REACHABLE = 'code_not_reachable'
    PROTECTED_AT_PERIMITER = 'protected_at_perimeter'
    PROTECTED_AT_RUNTIME = 'protected_at_runtime'
    PROTECTED_BY_COMPILER = 'protected_by_compiler'
    PROTECTED_BY_MITIGATING_CONTROL = 'protected_by_mitigating_control'
    REQUIRES_CONFIGURATION = 'requires_configuration'
    REQUIRES_DEPENDENCY = 'requires_dependency'
    REQUIRES_ENVIRONMENT = 'requires_environment'


@serializable.serializable_enum
class ImpactAnalysisResponse(str, Enum):
    """
    Enum object that defines the valid rationales as to why the impact analysis state was asserted.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_impactAnalysisResponsesType
    """

    CAN_NOT_FIX = 'can_not_fix'
    ROLLBACK = 'rollback'
    UPDATE = 'update'
    WILL_NOT_FIX = 'will_not_fix'
    WORKAROUND_AVAILABLE = 'workaround_available'


@serializable.serializable_enum
class ImpactAnalysisState(str, Enum):
    """
    Enum object that defines the permissible impact analysis states.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_impactAnalysisStateType
    """

    RESOLVED = 'resolved'
    RESOLVED_WITH_PEDIGREE = 'resolved_with_pedigree'
    EXPLOITABLE = 'exploitable'
    IN_TRIAGE = 'in_triage'
    FALSE_POSITIVE = 'false_positive'
    NOT_AFFECTED = 'not_affected'
