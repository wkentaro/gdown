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
Exceptions relating to specific conditions that occur when (de)serializing/(de)normalizing CycloneDX BOM.
"""

from . import CycloneDxException


class CycloneDxSerializationException(CycloneDxException):
    """
    Base exception that covers all exceptions that may be thrown during model serializing/normalizing.
    """
    pass


class CycloneDxDeserializationException(CycloneDxException):
    """
    Base exception that covers all exceptions that may be thrown during model deserializing/denormalizing.
    """
    pass


class SerializationOfUnsupportedComponentTypeException(CycloneDxSerializationException):
    """
    Raised when attempting serializing/normalizing a :py:class:`cyclonedx.model.component.Component`
    to a :py:class:`cyclonedx.schema.schema.BaseSchemaVersion`
    which does not support that :py:class:`cyclonedx.model.component.ComponentType`
    .
    """


class SerializationOfUnexpectedValueException(CycloneDxSerializationException, ValueError):
    """
    Raised when attempting serializing/normalizing a type that is not expected there.
    """
