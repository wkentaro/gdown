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
from typing import TYPE_CHECKING, Any, Literal, Optional, Protocol, Union, overload

from ..schema import OutputFormat

if TYPE_CHECKING:  # pragma: no cover
    from ..schema import SchemaVersion
    from .json import JsonValidator
    from .xml import XmlValidator


class ValidationError:
    """Validation failed with this specific error.

    Use :attr:`~data` to access the content.
    """

    data: Any
    """Raw error data from one of the underlying validation methods."""

    def __init__(self, data: Any) -> None:
        self.data = data

    def __repr__(self) -> str:
        return repr(self.data)

    def __str__(self) -> str:
        return str(self.data)


class SchemabasedValidator(Protocol):
    """Schema-based Validator protocol"""

    @overload
    def validate_str(self, data: str, *, all_errors: Literal[False] = ...) -> Optional[ValidationError]:
        """Validate a string

        :param data: the data string to validate
        :param all_errors: whether to return all errors or only (any)one - if any
        :return: validation error
        :retval None: if ``data`` is valid
        :retval ValidationError:  if ``data`` is invalid
        """
        ...  # pragma: no cover

    @overload
    def validate_str(self, data: str, *, all_errors: Literal[True]) -> Optional[Iterable[ValidationError]]:
        """Validate a string

        :param data: the data string to validate
        :param all_errors: whether to return all errors or only (any)one - if any
        :return: validation error
        :retval None: if ``data`` is valid
        :retval Iterable[ValidationError]:  if ``data`` is invalid
        """
        ...   # pragma: no cover

    def validate_str(
        self, data: str, *,
        all_errors: bool = False
    ) -> Union[None, ValidationError, Iterable[ValidationError]]:
        """Validate a string

        :param data: the data string to validate
        :param all_errors: whether to return all errors or only (any)one - if any
        :return: validation error
        :retval None: if ``data`` is valid
        :retval ValidationError:  if ``data`` is invalid and ``all_errors`` is ``False``
        :retval Iterable[ValidationError]:  if ``data`` is invalid and ``all_errors`` is ``True``
        """
        ...  # pragma: no cover


class BaseSchemabasedValidator(ABC, SchemabasedValidator):
    """Base Schema-based Validator"""

    def __init__(self, schema_version: 'SchemaVersion') -> None:
        self.__schema_version = schema_version
        if not self._schema_file:
            raise ValueError(f'Unsupported schema_version: {schema_version!r}')

    @property
    def schema_version(self) -> 'SchemaVersion':
        """Get the schema version."""
        return self.__schema_version

    @property
    @abstractmethod
    def output_format(self) -> OutputFormat:
        """Get the format."""
        ...  # pragma: no cover

    @property
    @abstractmethod
    def _schema_file(self) -> Optional[str]:
        """Get the schema file according to schema version."""
        ...  # pragma: no cover


@overload
def make_schemabased_validator(output_format: Literal[OutputFormat.JSON], schema_version: 'SchemaVersion'
                               ) -> 'JsonValidator':
    ...  # pragma: no cover


@overload
def make_schemabased_validator(output_format: Literal[OutputFormat.XML], schema_version: 'SchemaVersion'
                               ) -> 'XmlValidator':
    ...  # pragma: no cover


@overload
def make_schemabased_validator(output_format: OutputFormat, schema_version: 'SchemaVersion'
                               ) -> Union['JsonValidator', 'XmlValidator']:
    ...  # pragma: no cover


def make_schemabased_validator(output_format: OutputFormat, schema_version: 'SchemaVersion'
                               ) -> 'BaseSchemabasedValidator':
    """Get the default Schema-based Validator for a certain :class:`OutputFormat`.

    Raises error when no instance could be made.
    """
    if TYPE_CHECKING:  # pragma: no cover
        Validator: type[BaseSchemabasedValidator]  # noqa:N806
    if OutputFormat.JSON is output_format:
        from .json import JsonValidator as Validator
    elif OutputFormat.XML is output_format:
        from .xml import XmlValidator as Validator
    else:
        raise ValueError(f'Unexpected output_format: {output_format!r}')
    return Validator(schema_version)
