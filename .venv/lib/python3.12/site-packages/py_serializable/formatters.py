# This file is part of py-serializable
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
# Copyright (c) Paul Horton. All Rights Reserved.

from abc import ABC, abstractmethod
from re import compile as re_compile
from typing import Type


class BaseNameFormatter(ABC):

    @classmethod
    @abstractmethod
    def encode(cls, property_name: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def decode(cls, property_name: str) -> str:
        pass

    @classmethod
    def decode_as_class_name(cls, name: str) -> str:
        name = CamelCasePropertyNameFormatter.encode(cls.decode(property_name=name))
        return name[:1].upper() + name[1:]

    @classmethod
    def decode_handle_python_builtins_and_keywords(cls, name: str) -> str:
        return name

    @classmethod
    def encode_handle_python_builtins_and_keywords(cls, name: str) -> str:
        return name


class CamelCasePropertyNameFormatter(BaseNameFormatter):
    _ENCODE_PATTERN = re_compile(r'_([a-z])')
    _DECODE_PATTERN = re_compile(r'(?<!^)(?=[A-Z])')

    @classmethod
    def encode(cls, property_name: str) -> str:
        property_name = property_name[:1].lower() + property_name[1:]
        return cls.encode_handle_python_builtins_and_keywords(
            CamelCasePropertyNameFormatter._ENCODE_PATTERN.sub(lambda x: x.group(1).upper(), property_name)
        )

    @classmethod
    def decode(cls, property_name: str) -> str:
        return cls.decode_handle_python_builtins_and_keywords(
            CamelCasePropertyNameFormatter._DECODE_PATTERN.sub('_', property_name).lower()
        )


class KebabCasePropertyNameFormatter(BaseNameFormatter):
    _ENCODE_PATTERN = re_compile(r'(_)')

    @classmethod
    def encode(cls, property_name: str) -> str:
        property_name = cls.encode_handle_python_builtins_and_keywords(name=property_name)
        property_name = property_name[:1].lower() + property_name[1:]
        return KebabCasePropertyNameFormatter._ENCODE_PATTERN.sub(lambda x: '-', property_name)

    @classmethod
    def decode(cls, property_name: str) -> str:
        return cls.decode_handle_python_builtins_and_keywords(property_name.replace('-', '_'))


class SnakeCasePropertyNameFormatter(BaseNameFormatter):
    _ENCODE_PATTERN = re_compile(r'(.)([A-Z][a-z]+)')

    @classmethod
    def encode(cls, property_name: str) -> str:
        property_name = property_name[:1].lower() + property_name[1:]
        return cls.encode_handle_python_builtins_and_keywords(
            SnakeCasePropertyNameFormatter._ENCODE_PATTERN.sub(lambda x: x.group(1).upper(), property_name)
        )

    @classmethod
    def decode(cls, property_name: str) -> str:
        return cls.decode_handle_python_builtins_and_keywords(property_name)


class CurrentFormatter:
    formatter: Type['BaseNameFormatter'] = CamelCasePropertyNameFormatter
