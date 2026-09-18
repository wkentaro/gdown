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
Set of classes and methods for outputting our libraries internal Bom model to CycloneDX documents in varying formats
and according to different versions of the CycloneDX schema standard.
"""

import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, overload

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

from ..contrib.bom.utils import BomRefDiscriminator as _BomRefDiscriminator
from ..schema import OutputFormat, SchemaVersion

if TYPE_CHECKING:  # pragma: no cover
    from ..model.bom import Bom
    from .json import Json as JsonOutputter
    from .xml import Xml as XmlOutputter


class BaseOutput(ABC):

    def __init__(self, bom: 'Bom', **kwargs: int) -> None:
        super().__init__(**kwargs)
        self._bom = bom
        self._generated: bool = False

    @property
    @abstractmethod
    def schema_version(self) -> SchemaVersion:
        ...  # pragma: no cover

    @property
    @abstractmethod
    def output_format(self) -> OutputFormat:
        ...  # pragma: no cover

    @property
    def generated(self) -> bool:
        return self._generated

    @generated.setter
    def generated(self, generated: bool) -> None:
        self._generated = generated

    def get_bom(self) -> 'Bom':
        return self._bom

    def set_bom(self, bom: 'Bom') -> None:
        self._bom = bom

    @abstractmethod
    def generate(self, force_regeneration: bool = False) -> None:
        ...  # pragma: no cover

    @abstractmethod
    def output_as_string(self, *,
                         indent: Optional[Union[int, str]] = None,
                         **kwargs: Any) -> str:
        ...  # pragma: no cover

    def output_to_file(self, filename: str, allow_overwrite: bool = False, *,
                       indent: Optional[Union[int, str]] = None,
                       **kwargs: Any) -> None:
        # Check directory writable
        output_filename = os.path.realpath(filename)
        output_directory = os.path.dirname(output_filename)
        if not os.access(output_directory, os.W_OK):
            raise PermissionError(output_directory)
        if os.path.exists(output_filename) and not allow_overwrite:
            raise FileExistsError(output_filename)
        with open(output_filename, mode='wb') as f_out:
            f_out.write(self.output_as_string(indent=indent).encode('utf-8'))


@overload
def make_outputter(bom: 'Bom', output_format: Literal[OutputFormat.JSON],
                   schema_version: SchemaVersion) -> 'JsonOutputter':
    ...  # pragma: no cover


@overload
def make_outputter(bom: 'Bom', output_format: Literal[OutputFormat.XML],
                   schema_version: SchemaVersion) -> 'XmlOutputter':
    ...  # pragma: no cover


@overload
def make_outputter(bom: 'Bom', output_format: OutputFormat,
                   schema_version: SchemaVersion) -> Union['XmlOutputter', 'JsonOutputter']:
    ...  # pragma: no cover


def make_outputter(bom: 'Bom', output_format: OutputFormat, schema_version: SchemaVersion) -> BaseOutput:
    """
    Helper method to quickly get the correct output class/formatter.

    Pass in your BOM and optionally an output format and schema version (defaults to XML and latest schema version).


    Raises error when no instance could be made.

    :param bom: Bom
    :param output_format: OutputFormat
    :param schema_version: SchemaVersion
    :return: BaseOutput
    """
    if TYPE_CHECKING:  # pragma: no cover
        BY_SCHEMA_VERSION: Mapping[SchemaVersion, type[BaseOutput]]  # noqa:N806
    if OutputFormat.JSON is output_format:
        from .json import BY_SCHEMA_VERSION
    elif OutputFormat.XML is output_format:
        from .xml import BY_SCHEMA_VERSION
    else:
        raise ValueError(f'Unexpected output_format: {output_format!r}')

    klass = BY_SCHEMA_VERSION.get(schema_version, None)
    if klass is None:
        raise ValueError(f'Unknown {output_format.name}/schema_version: {schema_version!r}')
    return klass(bom)

# region deprecated re-export


@deprecated('Deprecated re-export location - see docstring of "BomRefDiscriminator" for details.')
class BomRefDiscriminator(_BomRefDiscriminator):
    """Deprecated — Alias of :class:`cyclonedx.contrib.bom.utils.BomRefDiscriminator`.

    .. deprecated:: next
        This re-export location is deprecated.
        Use ``from cyclonedx.contrib.bom.utils import BomRefDiscriminator`` instead.
        The exported symbol itself is NOT deprecated — only this import path.
    """
    pass


# endregion deprecated re-export
