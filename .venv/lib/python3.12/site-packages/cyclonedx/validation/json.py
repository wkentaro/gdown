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


__all__ = ['JsonValidator', 'JsonStrictValidator', 'JsonValidationError']

from abc import ABC
from collections.abc import Iterable
from itertools import chain
from json import loads as json_loads
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, overload

from ..schema import OutputFormat

if TYPE_CHECKING:  # pragma: no cover
    from ..schema import SchemaVersion

from ..exception import MissingOptionalDependencyException
from ..schema._res import (
    BOM_JSON as _S_BOM,
    BOM_JSON_STRICT as _S_BOM_STRICT,
    CRYPTOGRAPHY_DEFS as _S_CDEFS,
    JSF as _S_JSF,
    SPDX_JSON as _S_SPDX,
)
from . import BaseSchemabasedValidator, SchemabasedValidator, ValidationError

_missing_deps_error: Optional[tuple[MissingOptionalDependencyException, ImportError]] = None
try:
    from jsonschema.validators import Draft7Validator  # type:ignore[import-untyped]
    from referencing import Registry
    from referencing.jsonschema import DRAFT7

    if TYPE_CHECKING:  # pragma: no cover
        from jsonschema.exceptions import ValidationError as JsonSchemaValidationError  # type:ignore[import-untyped]
        from jsonschema.protocols import Validator as JsonSchemaValidator  # type:ignore[import-untyped]
except ImportError as err:
    _missing_deps_error = MissingOptionalDependencyException(
        'This functionality requires optional dependencies.\n'
        'Please install `cyclonedx-python-lib` with the extra "json-validation".\n'
    ), err


class JsonValidationError(ValidationError):
    @classmethod
    def _make_from_jsve(cls, e: 'JsonSchemaValidationError') -> 'JsonValidationError':
        """⚠️ This is an internal API. It is not part of the public interface and may change without notice."""
        # in preparation for https://github.com/CycloneDX/cyclonedx-python-lib/pull/836
        return cls(e)


class _BaseJsonValidator(BaseSchemabasedValidator, ABC):
    @property
    def output_format(self) -> Literal[OutputFormat.JSON]:
        return OutputFormat.JSON

    def __init__(self, schema_version: 'SchemaVersion') -> None:
        # this is the def that is used for generating the documentation
        super().__init__(schema_version)

    # region typing-relevant copy from parent class - needed for mypy and doc tools

    @overload
    def validate_str(self, data: str, *, all_errors: Literal[False] = ...) -> Optional[JsonValidationError]:
        ...  # pragma: no cover

    @overload
    def validate_str(self, data: str, *, all_errors: Literal[True]) -> Optional[Iterable[JsonValidationError]]:
        ...  # pragma: no cover

    def validate_str(
        self, data: str, *, all_errors: bool = False
    ) -> Union[None, JsonValidationError, Iterable[JsonValidationError]]:
        ...  # pragma: no cover

    # endregion

    if _missing_deps_error:  # noqa:C901
        __MDERROR = _missing_deps_error

        def validate_str(  # type:ignore[no-redef] # noqa:F811 # typing-relevant headers go first
            self, data: str, *, all_errors: bool = False
        ) -> Union[None, JsonValidationError, Iterable[JsonValidationError]]:
            raise self.__MDERROR[0] from self.__MDERROR[1]

    else:

        def validate_str(  # type:ignore[no-redef] # noqa:F811 # typing-relevant headers go first
            self, data: str, *, all_errors: bool = False
        ) -> Union[None, JsonValidationError, Iterable[JsonValidationError]]:
            validator = self._validator  # may throw on error that MUST NOT be caught
            structure = json_loads(data)
            errors = validator.iter_errors(structure)
            first_error = next(errors, None)
            if first_error is None:
                return None
            first_error = JsonValidationError._make_from_jsve(first_error)
            return chain((first_error,), map(JsonValidationError._make_from_jsve, errors)) \
                if all_errors \
                else first_error

        __validator: Optional['JsonSchemaValidator'] = None

        @property
        def _validator(self) -> 'JsonSchemaValidator':
            if not self.__validator:
                schema_file = self._schema_file
                if schema_file is None:
                    raise NotImplementedError('missing schema file')
                with open(schema_file) as sf:
                    self.__validator = Draft7Validator(
                        json_loads(sf.read()),
                        registry=self.__make_validator_registry(),
                        format_checker=Draft7Validator.FORMAT_CHECKER)
            return self.__validator

        @staticmethod
        def __make_validator_registry() -> Registry[Any]:
            schema_prefix = 'http://cyclonedx.org/schema/'
            with open(_S_SPDX) as spdx, open(_S_JSF) as jsf, open(_S_CDEFS) as cdefs:
                return Registry().with_resources([
                    (f'{schema_prefix}spdx.SNAPSHOT.schema.json', DRAFT7.create_resource(json_loads(spdx.read()))),
                    (f'{schema_prefix}cryptography-defs.SNAPSHOT.schema.json',
                     DRAFT7.create_resource(json_loads(cdefs.read()))),
                    (f'{schema_prefix}jsf-0.82.SNAPSHOT.schema.json', DRAFT7.create_resource(json_loads(jsf.read()))),
                ])


class JsonValidator(_BaseJsonValidator, BaseSchemabasedValidator, SchemabasedValidator):
    """Validator for CycloneDX documents in JSON format."""

    @property
    def _schema_file(self) -> Optional[str]:
        return _S_BOM.get(self.schema_version)


class JsonStrictValidator(_BaseJsonValidator, BaseSchemabasedValidator, SchemabasedValidator):
    """Strict validator for CycloneDX documents in JSON format.

    In contrast to :class:`~JsonValidator`,
    the document must not have additional or unknown JSON properties.
    """
    @property
    def _schema_file(self) -> Optional[str]:
        return _S_BOM_STRICT.get(self.schema_version)
