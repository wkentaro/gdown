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

"""Hash related factories"""

__all__ = ['HashTypeFactory']

from ...exception.model import UnknownHashTypeException
from ...model import HashAlgorithm, HashType

_MAP_HASHLIB: dict[str, HashAlgorithm] = {
    # from hashlib.algorithms_guaranteed
    'md5': HashAlgorithm.MD5,
    'sha1': HashAlgorithm.SHA_1,
    # sha224:
    'sha256': HashAlgorithm.SHA_256,
    'sha384': HashAlgorithm.SHA_384,
    'sha512': HashAlgorithm.SHA_512,
    # blake2b:
    # blake2s:
    # sha3_224:
    'sha3_256': HashAlgorithm.SHA3_256,
    'sha3_384': HashAlgorithm.SHA3_384,
    'sha3_512': HashAlgorithm.SHA3_512,
    # shake_128:
    # shake_256:
}


class HashTypeFactory:

    def from_hashlib_alg(self, hashlib_alg: str, content: str) -> HashType:
        """
        Attempts to convert a hashlib-algorithm to our internal model classes.

        Args:
             hashlib_alg:
                Hash algorithm - like it is used by `hashlib`.
                Example: `sha256`.

            content:
                Hash value.

        Raises:
            `UnknownHashTypeException` if the algorithm of hash cannot be determined.

        Returns:
            An instance of `HashType`.
        """
        alg = _MAP_HASHLIB.get(hashlib_alg.lower())
        if alg is None:
            raise UnknownHashTypeException(f'Unable to determine hash alg for {hashlib_alg!r}')
        return HashType(alg=alg, content=content)

    def from_composite_str(self, composite_hash: str) -> HashType:
        """
        Attempts to convert a string which includes both the Hash Algorithm and Hash Value and represent using our
        internal model classes.

        Args:
             composite_hash:
                Composite Hash string of the format `HASH_ALGORITHM`:`HASH_VALUE`.
                Example: `sha256:806143ae5bfb6a3c6e736a764057db0e6a0e05e338b5630894a5f779cabb4f9b`.

                Valid case insensitive prefixes are:
                `md5`, `sha1`, `sha256`, `sha384`, `sha512`, `blake2b256`, `blake2b384`, `blake2b512`,
                `blake2256`, `blake2384`, `blake2512`, `sha3-256`, `sha3-384`, `sha3-512`,
                `blake3`.

        Raises:
            `UnknownHashTypeException` if the type of hash cannot be determined.

        Returns:
            An instance of `HashType`.
        """
        parts = composite_hash.split(':')

        algorithm_prefix = parts[0].lower()
        if algorithm_prefix == 'md5':
            return HashType(
                alg=HashAlgorithm.MD5,
                content=parts[1].lower()
            )
        elif algorithm_prefix[0:4] == 'sha3':
            return HashType(
                alg=getattr(HashAlgorithm, f'SHA3_{algorithm_prefix[5:]}'),
                content=parts[1].lower()
            )
        elif algorithm_prefix == 'sha1':
            return HashType(
                alg=HashAlgorithm.SHA_1,
                content=parts[1].lower()
            )
        elif algorithm_prefix[0:3] == 'sha':
            # This is actually SHA2...
            return HashType(
                alg=getattr(HashAlgorithm, f'SHA_{algorithm_prefix[3:]}'),
                content=parts[1].lower()
            )
        elif algorithm_prefix[0:7] == 'blake2b':
            return HashType(
                alg=getattr(HashAlgorithm, f'BLAKE2B_{algorithm_prefix[7:]}'),
                content=parts[1].lower()
            )
        elif algorithm_prefix[0:6] == 'blake2':
            return HashType(
                alg=getattr(HashAlgorithm, f'BLAKE2B_{algorithm_prefix[6:]}'),
                content=parts[1].lower()
            )
        elif algorithm_prefix[0:6] == 'blake3':
            return HashType(
                alg=HashAlgorithm.BLAKE3,
                content=parts[1].lower()
            )
        raise UnknownHashTypeException(f'Unable to determine hash type from {composite_hash!r}')
