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

"""Representation of this very python library.

.. deprecated:: next
"""

__all__ = ['this_component', 'this_tool']

import sys
from typing import TYPE_CHECKING

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

from ..contrib.this.builders import this_component as _this_component, this_tool as _this_tool

# region deprecated re-export

if TYPE_CHECKING:
    from ..model.component import Component
    from ..model.tool import Tool


@deprecated('Deprecated re-export location - see docstring of "this_component" for details.')
def this_component() -> 'Component':
    """Deprecated — Alias of :func:`cyclonedx.contrib.this.builders.this_component`.

    .. deprecated:: next
        This re-export location is deprecated.
        Use ``from cyclonedx.contrib.this.builders import this_component`` instead.
        The exported symbol itself is NOT deprecated — only this import path.
    """
    return _this_component()


@deprecated('Deprecated re-export location - see docstring of "this_tool" for details.')
def this_tool() -> 'Tool':
    """Deprecated — Alias of :func:`cyclonedx.contrib.this.builders.this_tool`.

    .. deprecated:: next
        This re-export location is deprecated.
        Use ``from cyclonedx.contrib.this.builders import this_tool`` instead.
        The exported symbol itself is NOT deprecated — only this import path.
    """
    return _this_tool()

# endregion deprecated re-export
