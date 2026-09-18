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


from typing import TYPE_CHECKING, Any, Literal, Optional, Union
from xml.dom.minidom import parseString as dom_parseString  # nosec B408
from xml.etree.ElementTree import Element as XmlElement, tostring as xml_dumps  # nosec B405

from ..contrib.bom.utils import BomRefDiscriminator
from ..schema import OutputFormat, SchemaVersion
from ..schema.schema import (
    SCHEMA_VERSIONS,
    BaseSchemaVersion,
    SchemaVersion1Dot0,
    SchemaVersion1Dot1,
    SchemaVersion1Dot2,
    SchemaVersion1Dot3,
    SchemaVersion1Dot4,
    SchemaVersion1Dot5,
    SchemaVersion1Dot6,
    SchemaVersion1Dot7,
)
from . import BaseOutput

if TYPE_CHECKING:  # pragma: no cover
    from ..model.bom import Bom


class Xml(BaseSchemaVersion, BaseOutput):
    def __init__(self, bom: 'Bom') -> None:
        super().__init__(bom=bom)
        self._bom_xml: str = ''

    @property
    def schema_version(self) -> SchemaVersion:
        return self.schema_version_enum

    @property
    def output_format(self) -> Literal[OutputFormat.XML]:
        return OutputFormat.XML

    def generate(self, force_regeneration: bool = False) -> None:
        if self.generated and not force_regeneration:
            return

        _view = SCHEMA_VERSIONS[self.schema_version_enum]
        bom = self.get_bom()
        bom.validate()
        xmlns = self.get_target_namespace()
        with BomRefDiscriminator.from_bom(bom):
            self._bom_xml = '<?xml version="1.0" ?>\n' + xml_dumps(  # type:ignore[call-overload]
                bom.as_xml(  # type:ignore[attr-defined]
                    _view, as_string=False, xmlns=xmlns),
                method='xml', default_namespace=xmlns, encoding='unicode',
                # `xml-declaration` is inconsistent/bugged in py38,
                # especially on Windows it will print a non-UTF8 codepage.
                # Furthermore, it might add an encoding of "utf-8" which is redundant default value of XML.
                # -> so we write the declaration manually, as long as py38 is supported.
                xml_declaration=False)

        self.generated = True

    @staticmethod
    def __make_indent(v: Optional[Union[int, str]]) -> str:
        if isinstance(v, int):
            return ' ' * v
        if isinstance(v, str):
            return v
        return ''

    def output_as_string(self, *,
                         indent: Optional[Union[int, str]] = None,
                         **kwargs: Any) -> str:
        self.generate()
        return self._bom_xml if indent is None else dom_parseString(  # nosecc B318
            self._bom_xml).toprettyxml(
            indent=self.__make_indent(indent)
            # do not set `encoding` - this would convert result to binary, not string
        )

    def get_target_namespace(self) -> str:
        return f'http://cyclonedx.org/schema/bom/{self.get_schema_version()}'


class XmlV1Dot0(Xml, SchemaVersion1Dot0):

    def _create_bom_element(self) -> XmlElement:
        return XmlElement('bom', {'xmlns': self.get_target_namespace(), 'version': '1'})


class XmlV1Dot1(Xml, SchemaVersion1Dot1):
    pass


class XmlV1Dot2(Xml, SchemaVersion1Dot2):
    pass


class XmlV1Dot3(Xml, SchemaVersion1Dot3):
    pass


class XmlV1Dot4(Xml, SchemaVersion1Dot4):
    pass


class XmlV1Dot5(Xml, SchemaVersion1Dot5):
    pass


class XmlV1Dot6(Xml, SchemaVersion1Dot6):
    pass


class XmlV1Dot7(Xml, SchemaVersion1Dot7):
    pass


BY_SCHEMA_VERSION: dict[SchemaVersion, type[Xml]] = {
    SchemaVersion.V1_7: XmlV1Dot7,
    SchemaVersion.V1_6: XmlV1Dot6,
    SchemaVersion.V1_5: XmlV1Dot5,
    SchemaVersion.V1_4: XmlV1Dot4,
    SchemaVersion.V1_3: XmlV1Dot3,
    SchemaVersion.V1_2: XmlV1Dot2,
    SchemaVersion.V1_1: XmlV1Dot1,
    SchemaVersion.V1_0: XmlV1Dot0,
}
