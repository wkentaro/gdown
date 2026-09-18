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

"""Component related builders"""

__all__ = ['ComponentBuilder']

from hashlib import sha1
from os.path import exists
from typing import Optional

from ...model import HashAlgorithm, HashType
from ...model.component import Component, ComponentType


class ComponentBuilder:

    def make_for_file(self, absolute_file_path: str, *,
                      name: Optional[str]) -> Component:
        """
        Helper method to create a :class:`cyclonedx.model.component.Component`
        that represents the provided local file as a Component.

        Args:
            absolute_file_path:
                Absolute path to the file you wish to represent
            name:
                Optionally, if supplied this is the name that will be used for the component.
                Defaults to arg ``absolute_file_path``.

        Returns:
            `Component` representing the supplied file
        """
        if not exists(absolute_file_path):
            raise FileExistsError(f'Supplied file path {absolute_file_path!r} does not exist')

        return Component(
            type=ComponentType.FILE,
            name=name or absolute_file_path,
            hashes=[
                HashType(alg=HashAlgorithm.SHA_1, content=self._file_sha1sum(absolute_file_path))
            ]
        )

    @staticmethod
    def _file_sha1sum(filename: str) -> str:
        """
        Generate a SHA1 hash of the provided file.

        Args:
            filename:
                Absolute path to file to hash as `str`

        Returns:
            SHA-1 hash
        """
        h = sha1()  # nosec B303, B324
        with open(filename, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b''):
                h.update(byte_block)
        return h.hexdigest()
