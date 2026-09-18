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
Content in here is internal, not for public use.
Breaking changes without notice may happen.
"""


from os.path import dirname, join
from typing import Optional

from .. import SchemaVersion

__DIR = dirname(__file__)

BOM_XML: dict[SchemaVersion, Optional[str]] = {
    SchemaVersion.V1_7: join(__DIR, 'bom-1.7.SNAPSHOT.xsd'),
    SchemaVersion.V1_6: join(__DIR, 'bom-1.6.SNAPSHOT.xsd'),
    SchemaVersion.V1_5: join(__DIR, 'bom-1.5.SNAPSHOT.xsd'),
    SchemaVersion.V1_4: join(__DIR, 'bom-1.4.SNAPSHOT.xsd'),
    SchemaVersion.V1_3: join(__DIR, 'bom-1.3.SNAPSHOT.xsd'),
    SchemaVersion.V1_2: join(__DIR, 'bom-1.2.SNAPSHOT.xsd'),
    SchemaVersion.V1_1: join(__DIR, 'bom-1.1.SNAPSHOT.xsd'),
    SchemaVersion.V1_0: join(__DIR, 'bom-1.0.SNAPSHOT.xsd'),
}

BOM_JSON: dict[SchemaVersion, Optional[str]] = {
    SchemaVersion.V1_7: join(__DIR, 'bom-1.7.SNAPSHOT.schema.json'),
    SchemaVersion.V1_6: join(__DIR, 'bom-1.6.SNAPSHOT.schema.json'),
    SchemaVersion.V1_5: join(__DIR, 'bom-1.5.SNAPSHOT.schema.json'),
    SchemaVersion.V1_4: join(__DIR, 'bom-1.4.SNAPSHOT.schema.json'),
    SchemaVersion.V1_3: join(__DIR, 'bom-1.3.SNAPSHOT.schema.json'),
    SchemaVersion.V1_2: join(__DIR, 'bom-1.2.SNAPSHOT.schema.json'),
    # <= v1.1 is not defined in JSON
    SchemaVersion.V1_1: None,
    SchemaVersion.V1_0: None,
}

BOM_JSON_STRICT: dict[SchemaVersion, Optional[str]] = {
    SchemaVersion.V1_7: BOM_JSON[SchemaVersion.V1_7],
    SchemaVersion.V1_6: BOM_JSON[SchemaVersion.V1_6],
    SchemaVersion.V1_5: BOM_JSON[SchemaVersion.V1_5],
    SchemaVersion.V1_4: BOM_JSON[SchemaVersion.V1_4],
    # <= 1.3 need special files
    SchemaVersion.V1_3: join(__DIR, 'bom-1.3-strict.SNAPSHOT.schema.json'),
    SchemaVersion.V1_2: join(__DIR, 'bom-1.2-strict.SNAPSHOT.schema.json'),
    # <= v1.1 is not defined in JSON
    SchemaVersion.V1_1: None,
    SchemaVersion.V1_0: None,
}

SPDX_JSON = join(__DIR, 'spdx.SNAPSHOT.schema.json')
SPDX_XML = join(__DIR, 'spdx.SNAPSHOT.xsd')

CRYPTOGRAPHY_DEFS = join(__DIR, 'cryptography-defs.SNAPSHOT.schema.json')

JSF = join(__DIR, 'jsf-0.82.SNAPSHOT.schema.json')
