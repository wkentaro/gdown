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

import re
import sys
from collections.abc import Iterable
from enum import Enum
from typing import Any, Optional, Union
from warnings import warn

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

# See https://github.com/package-url/packageurl-python/issues/65
import py_serializable as serializable
from packageurl import PackageURL
from sortedcontainers import SortedSet

from .._internal.bom_ref import bom_ref_from_str as _bom_ref_from_str
from .._internal.compare import ComparablePackageURL as _ComparablePackageURL, ComparableTuple as _ComparableTuple
from ..exception.model import InvalidOmniBorIdException, InvalidSwhidException
from ..exception.serialization import (
    CycloneDxDeserializationException,
    SerializationOfUnexpectedValueException,
    SerializationOfUnsupportedComponentTypeException,
)
from ..schema.deprecation import SchemaDeprecationWarning1Dot3, SchemaDeprecationWarning1Dot6
from ..schema.schema import (
    SchemaVersion1Dot0,
    SchemaVersion1Dot1,
    SchemaVersion1Dot2,
    SchemaVersion1Dot3,
    SchemaVersion1Dot4,
    SchemaVersion1Dot5,
    SchemaVersion1Dot6,
    SchemaVersion1Dot7,
)
from ..serialization import PackageUrl as PackageUrlSH, XmlBoolAttribute as _XmlBoolAttributeSH
from . import (
    AttachedText,
    ExternalReference,
    HashAlgorithm,
    HashType,
    IdentifiableAction,
    Property,
    XsUri,
    _HashTypeRepositorySerializationHelper,
)
from .bom_ref import BomRef
from .component_evidence import ComponentEvidence, _ComponentEvidenceSerializationHelper
from .contact import OrganizationalContact, OrganizationalEntity
from .crypto import CryptoProperties
from .dependency import Dependable
from .issue import IssueType
from .license import License, LicenseRepository, _LicenseRepositorySerializationHelper
from .release_note import ReleaseNotes


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Commit:
    """
    Our internal representation of the `commitType` complex type.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_commitType
    """

    def __init__(
        self, *,
        uid: Optional[str] = None,
        url: Optional[XsUri] = None,
        author: Optional[IdentifiableAction] = None,
        committer: Optional[IdentifiableAction] = None,
        message: Optional[str] = None,
    ) -> None:
        self.uid = uid
        self.url = url
        self.author = author
        self.committer = committer
        self.message = message

    @property
    @serializable.xml_sequence(1)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def uid(self) -> Optional[str]:
        """
        A unique identifier of the commit. This may be version control specific. For example, Subversion uses revision
        numbers whereas git uses commit hashes.

        Returns:
            `str` if set else `None`
        """
        return self._uid

    @uid.setter
    def uid(self, uid: Optional[str]) -> None:
        self._uid = uid

    @property
    @serializable.xml_sequence(2)
    def url(self) -> Optional[XsUri]:
        """
        The URL to the commit. This URL will typically point to a commit in a version control system.

        Returns:
             `XsUri` if set else `None`
        """
        return self._url

    @url.setter
    def url(self, url: Optional[XsUri]) -> None:
        self._url = url

    @property
    @serializable.xml_sequence(3)
    def author(self) -> Optional[IdentifiableAction]:
        """
        The author who created the changes in the commit.

        Returns:
            `IdentifiableAction` if set else `None`
        """
        return self._author

    @author.setter
    def author(self, author: Optional[IdentifiableAction]) -> None:
        self._author = author

    @property
    @serializable.xml_sequence(4)
    def committer(self) -> Optional[IdentifiableAction]:
        """
        The person who committed or pushed the commit

        Returns:
            `IdentifiableAction` if set else `None`
        """
        return self._committer

    @committer.setter
    def committer(self, committer: Optional[IdentifiableAction]) -> None:
        self._committer = committer

    @property
    @serializable.xml_sequence(5)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def message(self) -> Optional[str]:
        """
        The text description of the contents of the commit.

        Returns:
            `str` if set else `None`
        """
        return self._message

    @message.setter
    def message(self, message: Optional[str]) -> None:
        self._message = message

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.uid, self.url,
            self.author, self.committer,
            self.message
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Commit):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Commit):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Commit uid={self.uid}, url={self.url}, message={self.message}>'


@serializable.serializable_enum
class ComponentScope(str, Enum):
    """
    Enum object that defines the permissable 'scopes' for a Component according to the CycloneDX schema.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_scope
    """
    # see `_ComponentScopeSerializationHelper.__CASES` for view/case map
    REQUIRED = 'required'
    OPTIONAL = 'optional'
    EXCLUDED = 'excluded'  # Only supported in >= 1.1


class _ComponentScopeSerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    __CASES: dict[type[serializable.ViewType], frozenset[ComponentScope]] = dict()
    __CASES[SchemaVersion1Dot0] = frozenset({
        ComponentScope.REQUIRED,
        ComponentScope.OPTIONAL,
    })
    __CASES[SchemaVersion1Dot1] = __CASES[SchemaVersion1Dot0] | {
        ComponentScope.EXCLUDED,
    }
    __CASES[SchemaVersion1Dot2] = __CASES[SchemaVersion1Dot1]
    __CASES[SchemaVersion1Dot3] = __CASES[SchemaVersion1Dot2]
    __CASES[SchemaVersion1Dot4] = __CASES[SchemaVersion1Dot3]
    __CASES[SchemaVersion1Dot5] = __CASES[SchemaVersion1Dot4]
    __CASES[SchemaVersion1Dot6] = __CASES[SchemaVersion1Dot5]
    __CASES[SchemaVersion1Dot7] = __CASES[SchemaVersion1Dot6]

    @classmethod
    def __normalize(cls, cs: ComponentScope, view: type[serializable.ViewType]) -> Optional[str]:
        return cs.value \
            if cs in cls.__CASES.get(view, ()) \
            else None

    @classmethod
    def json_normalize(cls, o: Any, *,
                       view: Optional[type[serializable.ViewType]],
                       **__: Any) -> Optional[str]:
        assert view is not None
        return cls.__normalize(o, view)

    @classmethod
    def xml_normalize(cls, o: Any, *,
                      view: Optional[type[serializable.ViewType]],
                      **__: Any) -> Optional[str]:
        assert view is not None
        return cls.__normalize(o, view)

    @classmethod
    def deserialize(cls, o: Any) -> ComponentScope:
        return ComponentScope(o)


@serializable.serializable_enum
class ComponentType(str, Enum):
    """
    Enum object that defines the permissible 'types' for a Component according to the CycloneDX schema.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_classification
    """
    # see `_ComponentTypeSerializationHelper.__CASES` for view/case map
    APPLICATION = 'application'
    CONTAINER = 'container'  # Only supported in >= 1.2
    CRYPTOGRAPHIC_ASSET = 'cryptographic-asset'  # Only supported in >= 1.6
    DATA = 'data'  # Only supported in >= 1.5
    DEVICE = 'device'
    DEVICE_DRIVER = 'device-driver'  # Only supported in >= 1.5
    FILE = 'file'  # Only supported in >= 1.1
    FIRMWARE = 'firmware'  # Only supported in >= 1.2
    FRAMEWORK = 'framework'
    LIBRARY = 'library'
    MACHINE_LEARNING_MODEL = 'machine-learning-model'  # Only supported in >= 1.5
    OPERATING_SYSTEM = 'operating-system'
    PLATFORM = 'platform'  # Only supported in >= 1.5


class _ComponentTypeSerializationHelper(serializable.helpers.BaseHelper):
    """  THIS CLASS IS NON-PUBLIC API  """

    __CASES: dict[type[serializable.ViewType], frozenset[ComponentType]] = dict()
    __CASES[SchemaVersion1Dot0] = frozenset({
        ComponentType.APPLICATION,
        ComponentType.DEVICE,
        ComponentType.FRAMEWORK,
        ComponentType.LIBRARY,
        ComponentType.OPERATING_SYSTEM,
    })
    __CASES[SchemaVersion1Dot1] = __CASES[SchemaVersion1Dot0] | {
        ComponentType.FILE,
    }
    __CASES[SchemaVersion1Dot2] = __CASES[SchemaVersion1Dot1] | {
        ComponentType.CONTAINER,
        ComponentType.FIRMWARE,
    }
    __CASES[SchemaVersion1Dot3] = __CASES[SchemaVersion1Dot2]
    __CASES[SchemaVersion1Dot4] = __CASES[SchemaVersion1Dot3]
    __CASES[SchemaVersion1Dot5] = __CASES[SchemaVersion1Dot4] | {
        ComponentType.DATA,
        ComponentType.DEVICE_DRIVER,
        ComponentType.MACHINE_LEARNING_MODEL,
        ComponentType.PLATFORM,
    }
    __CASES[SchemaVersion1Dot6] = __CASES[SchemaVersion1Dot5] | {
        ComponentType.CRYPTOGRAPHIC_ASSET,
    }
    __CASES[SchemaVersion1Dot7] = __CASES[SchemaVersion1Dot6]

    @classmethod
    def __normalize(cls, ct: ComponentType, view: type[serializable.ViewType]) -> Optional[str]:
        if ct in cls.__CASES.get(view, ()):
            return ct.value
        raise SerializationOfUnsupportedComponentTypeException(f'unsupported {ct!r} for view {view!r}')

    @classmethod
    def json_normalize(cls, o: Any, *,
                       view: Optional[type[serializable.ViewType]],
                       **__: Any) -> Optional[str]:
        assert view is not None
        return cls.__normalize(o, view)

    @classmethod
    def xml_normalize(cls, o: Any, *,
                      view: Optional[type[serializable.ViewType]],
                      **__: Any) -> Optional[str]:
        assert view is not None
        return cls.__normalize(o, view)

    @classmethod
    def deserialize(cls, o: Any) -> ComponentType:
        return ComponentType(o)


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Diff:
    """
    Our internal representation of the `diffType` complex type.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_diffType
    """

    def __init__(
        self, *,
        text: Optional[AttachedText] = None,
        url: Optional[XsUri] = None,
    ) -> None:
        self.text = text
        self.url = url

    @property
    def text(self) -> Optional[AttachedText]:
        """
        Specifies the optional text of the diff.

        Returns:
            `AttachedText` if set else `None`
        """
        return self._text

    @text.setter
    def text(self, text: Optional[AttachedText]) -> None:
        self._text = text

    @property
    def url(self) -> Optional[XsUri]:
        """
        Specifies the URL to the diff.

        Returns:
            `XsUri` if set else `None`
        """
        return self._url

    @url.setter
    def url(self, url: Optional[XsUri]) -> None:
        self._url = url

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.url,
            self.text,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Diff):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Diff):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Diff url={self.url}>'


@serializable.serializable_enum
class PatchClassification(str, Enum):
    """
    Enum object that defines the permissible `patchClassification`s.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_patchClassification
    """
    BACKPORT = 'backport'
    CHERRY_PICK = 'cherry-pick'
    MONKEY = 'monkey'
    UNOFFICIAL = 'unofficial'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Patch:
    """
    Our internal representation of the `patchType` complex type.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_patchType
    """

    def __init__(
        self, *,
        type: PatchClassification,
        diff: Optional[Diff] = None,
        resolves: Optional[Iterable[IssueType]] = None,
    ) -> None:
        self.type = type
        self.diff = diff
        self.resolves = resolves or []

    @property
    @serializable.xml_attribute()
    def type(self) -> PatchClassification:
        """
        Specifies the purpose for the patch including the resolution of defects, security issues, or new behavior or
        functionality.

        Returns:
            `PatchClassification`
        """
        return self._type

    @type.setter
    def type(self, type: PatchClassification) -> None:
        self._type = type

    @property
    def diff(self) -> Optional[Diff]:
        """
        The patch file (or diff) that show changes.

        .. note::
            Refer to https://en.wikipedia.org/wiki/Diff.

        Returns:
            `Diff` if set else `None`
        """
        return self._diff

    @diff.setter
    def diff(self, diff: Optional[Diff]) -> None:
        self._diff = diff

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'issue')
    def resolves(self) -> 'SortedSet[IssueType]':
        """
        Optional list of issues resolved by this patch.

        Returns:
            Set of `IssueType`
        """
        return self._resolves

    @resolves.setter
    def resolves(self, resolves: Iterable[IssueType]) -> None:
        self._resolves = SortedSet(resolves)

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.type, self.diff,
            _ComparableTuple(self.resolves)
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Patch):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Patch):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Patch type={self.type}, id={id(self)}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Pedigree:
    """
    Our internal representation of the `pedigreeType` complex type.

    Component pedigree is a way to document complex supply chain scenarios where components are created, distributed,
    modified, redistributed, combined with other components, etc. Pedigree supports viewing this complex chain from the
    beginning, the end, or anywhere in the middle. It also provides a way to document variants where the exact relation
    may not be known.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_pedigreeType
    """

    def __init__(
        self, *,
        ancestors: Optional[Iterable['Component']] = None,
        descendants: Optional[Iterable['Component']] = None,
        variants: Optional[Iterable['Component']] = None,
        commits: Optional[Iterable[Commit]] = None,
        patches: Optional[Iterable[Patch]] = None,
        notes: Optional[str] = None,
    ) -> None:
        self.ancestors = ancestors or []
        self.descendants = descendants or []
        self.variants = variants or []
        self.commits = commits or []
        self.patches = patches or []
        self.notes = notes

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'component')
    @serializable.xml_sequence(1)
    def ancestors(self) -> "SortedSet['Component']":
        """
        Describes zero or more components in which a component is derived from. This is commonly used to describe forks
        from existing projects where the forked version contains a ancestor node containing the original component it
        was forked from.

        For example, Component A is the original component. Component B is the component being used and documented in
        the BOM. However, Component B contains a pedigree node with a single ancestor documenting Component A - the
        original component from which Component B is derived from.

        Returns:
            Set of `Component`
        """
        return self._ancestors

    @ancestors.setter
    def ancestors(self, ancestors: Iterable['Component']) -> None:
        self._ancestors = SortedSet(ancestors)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'component')
    @serializable.xml_sequence(2)
    def descendants(self) -> "SortedSet['Component']":
        """
        Descendants are the exact opposite of ancestors. This provides a way to document all forks (and their forks) of
        an original or root component.

        Returns:
            Set of `Component`
        """
        return self._descendants

    @descendants.setter
    def descendants(self, descendants: Iterable['Component']) -> None:
        self._descendants = SortedSet(descendants)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'component')
    @serializable.xml_sequence(3)
    def variants(self) -> "SortedSet['Component']":
        """
        Variants describe relations where the relationship between the components are not known. For example, if
        Component A contains nearly identical code to Component B. They are both related, but it is unclear if one is
        derived from the other, or if they share a common ancestor.

        Returns:
            Set of `Component`
        """
        return self._variants

    @variants.setter
    def variants(self, variants: Iterable['Component']) -> None:
        self._variants = SortedSet(variants)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'commit')
    @serializable.xml_sequence(4)
    def commits(self) -> 'SortedSet[Commit]':
        """
        A list of zero or more commits which provide a trail describing how the component deviates from an ancestor,
        descendant, or variant.

        Returns:
            Set of `Commit`
        """
        return self._commits

    @commits.setter
    def commits(self, commits: Iterable[Commit]) -> None:
        self._commits = SortedSet(commits)

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'patch')
    @serializable.xml_sequence(5)
    def patches(self) -> 'SortedSet[Patch]':
        """
        A list of zero or more patches describing how the component deviates from an ancestor, descendant, or variant.
        Patches may be complimentary to commits or may be used in place of commits.

        Returns:
            Set of `Patch`
        """
        return self._patches

    @patches.setter
    def patches(self, patches: Iterable[Patch]) -> None:
        self._patches = SortedSet(patches)

    @property
    @serializable.xml_sequence(6)
    def notes(self) -> Optional[str]:
        """
        Notes, observations, and other non-structured commentary describing the components pedigree.

        Returns:
            `str` if set else `None`
        """
        return self._notes

    @notes.setter
    def notes(self, notes: Optional[str]) -> None:
        self._notes = notes

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            _ComparableTuple(self.ancestors),
            _ComparableTuple(self.descendants),
            _ComparableTuple(self.variants),
            _ComparableTuple(self.commits),
            _ComparableTuple(self.patches),
            self.notes
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Pedigree):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Pedigree):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Pedigree id={id(self)}, hash={hash(self)}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Swid:
    """
    Our internal representation of the `swidType` complex type.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_swidType
    """

    def __init__(
        self, *,
        tag_id: str,
        name: str,
        version: Optional[str] = None,
        tag_version: Optional[int] = None,
        patch: Optional[bool] = None,
        text: Optional[AttachedText] = None,
        url: Optional[XsUri] = None,
    ) -> None:
        self.tag_id = tag_id
        self.name = name
        self.version = version
        self.tag_version = tag_version
        self.patch = patch
        self.text = text
        self.url = url

    @property
    @serializable.xml_attribute()
    def tag_id(self) -> str:
        """
        Maps to the tagId of a SoftwareIdentity.

        Returns:
            `str`
        """
        return self._tag_id

    @tag_id.setter
    def tag_id(self, tag_id: str) -> None:
        self._tag_id = tag_id

    @property
    @serializable.xml_attribute()
    def name(self) -> str:
        """
        Maps to the name of a SoftwareIdentity.

        Returns:
             `str`
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    @serializable.xml_attribute()
    def version(self) -> Optional[str]:
        """
        Maps to the version of a SoftwareIdentity.

        Returns:
             `str` if set else `None`.
        """
        return self._version

    @version.setter
    def version(self, version: Optional[str]) -> None:
        self._version = version

    @property
    @serializable.xml_attribute()
    def tag_version(self) -> Optional[int]:
        """
        Maps to the tagVersion of a SoftwareIdentity.

        Returns:
            `int` if set else `None`
        """
        return self._tag_version

    @tag_version.setter
    def tag_version(self, tag_version: Optional[int]) -> None:
        self._tag_version = tag_version

    @property
    @serializable.xml_attribute()
    def patch(self) -> Optional[bool]:
        """
        Maps to the patch of a SoftwareIdentity.

        Returns:
             `bool` if set else `None`
        """
        return self._patch

    @patch.setter
    def patch(self, patch: Optional[bool]) -> None:
        self._patch = patch

    @property
    def text(self) -> Optional[AttachedText]:
        """
        Specifies the full content of the SWID tag.

        Returns:
            `AttachedText` if set else `None`
        """
        return self._text

    @text.setter
    def text(self, text: Optional[AttachedText]) -> None:
        self._text = text

    @property
    def url(self) -> Optional[XsUri]:
        """
        The URL to the SWID file.

        Returns:
            `XsUri` if set else `None`
        """
        return self._url

    @url.setter
    def url(self, url: Optional[XsUri]) -> None:
        self._url = url

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.tag_id,
            self.name, self.version,
            self.tag_version,
            self.patch,
            self.url,
            self.text,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Swid):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Swid):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Swid tagId={self.tag_id}, name={self.name}, version={self.version}>'


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class OmniborId(serializable.helpers.BaseHelper):
    """
    Helper class that allows us to perform validation on data strings that must conform to
    https://www.iana.org/assignments/uri-schemes/prov/gitoid.

    """

    _VALID_OMNIBOR_ID_REGEX = re.compile(r'^gitoid:(blob|tree|commit|tag):sha(1|256):([a-z0-9]+)$')

    def __init__(self, id: str) -> None:
        if OmniborId._VALID_OMNIBOR_ID_REGEX.match(id) is None:
            raise InvalidOmniBorIdException(
                f'Supplied value "{id} does not meet format specification.'
            )
        self._id = id

    @property
    @serializable.json_name('.')
    @serializable.xml_name('.')
    def id(self) -> str:
        return self._id

    @classmethod
    def serialize(cls, o: Any) -> str:
        if isinstance(o, OmniborId):
            return str(o)
        raise SerializationOfUnexpectedValueException(
            f'Attempt to serialize a non-OmniBorId: {o!r}')

    @classmethod
    def deserialize(cls, o: Any) -> 'OmniborId':
        try:
            return OmniborId(id=str(o))
        except ValueError as err:
            raise CycloneDxDeserializationException(
                f'OmniBorId string supplied does not parse: {o!r}'
            ) from err

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, OmniborId):
            return self._id == other._id
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, OmniborId):
            return self._id < other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f'<OmniBorId {self._id}>'

    def __str__(self) -> str:
        return self._id


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Swhid(serializable.helpers.BaseHelper):
    """
    Helper class that allows us to perform validation on data strings that must conform to
    https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html.

    """

    _VALID_SWHID_REGEX = re.compile(r'^swh:1:(cnp|rel|rev|dir|cnt):([0-9a-z]{40})(.*)?$')

    def __init__(self, id: str) -> None:
        if Swhid._VALID_SWHID_REGEX.match(id) is None:
            raise InvalidSwhidException(
                f'Supplied value "{id} does not meet format specification.'
            )
        self._id = id

    @property
    @serializable.json_name('.')
    @serializable.xml_name('.')
    def id(self) -> str:
        return self._id

    @classmethod
    def serialize(cls, o: Any) -> str:
        if isinstance(o, Swhid):
            return str(o)
        raise SerializationOfUnexpectedValueException(
            f'Attempt to serialize a non-Swhid: {o!r}')

    @classmethod
    def deserialize(cls, o: Any) -> 'Swhid':
        try:
            return Swhid(id=str(o))
        except ValueError as err:
            raise CycloneDxDeserializationException(
                f'Swhid string supplied does not parse: {o!r}'
            ) from err

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Swhid):
            return self._id == other._id
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Swhid):
            return self._id < other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f'<Swhid {self._id}>'

    def __str__(self) -> str:
        return self._id


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class Component(Dependable):
    """
    This is our internal representation of a Component within a Bom.

    .. note::
        See the CycloneDX Schema definition: https://cyclonedx.org/docs/1.7/xml/#type_component
    """

    @staticmethod
    @deprecated('Deprecated - use cyclonedx.contrib.component.builders.ComponentBuilder().make_for_file() instead')
    def for_file(absolute_file_path: str, path_for_bom: Optional[str]) -> 'Component':
        """Deprecated — Wrapper of :func:`cyclonedx.contrib.component.builders.ComponentBuilder.make_for_file`.

        Helper method to create a Component that represents the provided local file as a Component.

        .. deprecated:: next
            Use ``cyclonedx.contrib.component.builders.ComponentBuilder().make_for_file()`` instead.
        """
        from ..contrib.component.builders import ComponentBuilder

        component = ComponentBuilder().make_for_file(absolute_file_path, name=path_for_bom)
        sha1_hash = next((h.content for h in component.hashes if h.alg is HashAlgorithm.SHA_1), None)
        assert sha1_hash is not None
        component.version = f'0.0.0-{sha1_hash[0:12]}'
        component.purl = PackageURL(  # DEPRECATED: a file has no PURL!
            type='generic', name=path_for_bom if path_for_bom else absolute_file_path,
            version=f'0.0.0-{sha1_hash[0:12]}'
        )
        return component

    def __init__(
        self, *,
        name: str,
        type: ComponentType = ComponentType.LIBRARY,
        mime_type: Optional[str] = None,
        bom_ref: Optional[Union[str, BomRef]] = None,
        supplier: Optional[OrganizationalEntity] = None,
        publisher: Optional[str] = None,
        group: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        scope: Optional[ComponentScope] = None,
        is_external: Optional[bool] = None,
        hashes: Optional[Iterable[HashType]] = None,
        licenses: Optional[Iterable[License]] = None,
        copyright: Optional[str] = None,
        purl: Optional[PackageURL] = None,
        external_references: Optional[Iterable[ExternalReference]] = None,
        properties: Optional[Iterable[Property]] = None,
        release_notes: Optional[ReleaseNotes] = None,
        cpe: Optional[str] = None,
        swid: Optional[Swid] = None,
        pedigree: Optional[Pedigree] = None,
        components: Optional[Iterable['Component']] = None,
        evidence: Optional[ComponentEvidence] = None,
        modified: bool = False,
        manufacturer: Optional[OrganizationalEntity] = None,
        authors: Optional[Iterable[OrganizationalContact]] = None,
        omnibor_ids: Optional[Iterable[OmniborId]] = None,
        swhids: Optional[Iterable[Swhid]] = None,
        crypto_properties: Optional[CryptoProperties] = None,
        tags: Optional[Iterable[str]] = None,
        # Deprecated in v1.6
        author: Optional[str] = None,
    ) -> None:
        self.type = type
        self.mime_type = mime_type
        self._bom_ref = _bom_ref_from_str(bom_ref)
        self.supplier = supplier
        self.manufacturer = manufacturer
        self.authors = authors or []
        self.publisher = publisher
        self.group = group
        self.name = name
        self.description = description
        self.scope = scope
        self.is_external = is_external
        self.hashes = hashes or []
        self.licenses = licenses or []
        self.copyright = copyright
        self.cpe = cpe
        self.purl = purl
        self.omnibor_ids = omnibor_ids or []
        self.swhids = swhids or []
        self.swid = swid
        self.pedigree = pedigree
        self.external_references = external_references or []
        self.properties = properties or []
        self.components = components or []
        self.evidence = evidence
        self.release_notes = release_notes
        self.crypto_properties = crypto_properties
        self.tags = tags or []
        # spec-deprecated properties below
        self.author = author
        self.modified = modified
        self.version = version

    @property
    @serializable.type_mapping(_ComponentTypeSerializationHelper)
    @serializable.xml_attribute()
    def type(self) -> ComponentType:
        """
        Get the type of this Component.

        Returns:
            Declared type of this Component as `ComponentType`.
        """
        return self._type

    @type.setter
    def type(self, type: ComponentType) -> None:
        self._type = type

    @property
    @serializable.xml_string(serializable.XmlStringSerializationType.TOKEN)
    def mime_type(self) -> Optional[str]:
        """
        Get any declared mime-type for this Component.

        When used on file components, the mime-type can provide additional context about the kind of file being
        represented such as an image, font, or executable. Some library or framework components may also have an
        associated mime-type.

        Returns:
            `str` if set else `None`
        """
        return self._mime_type

    @mime_type.setter
    def mime_type(self, mime_type: Optional[str]) -> None:
        self._mime_type = mime_type

    @property
    @serializable.json_name('bom-ref')
    @serializable.type_mapping(BomRef)
    @serializable.view(SchemaVersion1Dot1)
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_attribute()
    @serializable.xml_name('bom-ref')
    def bom_ref(self) -> BomRef:
        """
        An optional identifier which can be used to reference the component elsewhere in the BOM. Every bom-ref MUST be
        unique within the BOM.

        Returns:
            `BomRef`
        """
        return self._bom_ref

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(1)
    def supplier(self) -> Optional[OrganizationalEntity]:
        """
        The organization that supplied the component. The supplier may often be the manufacture, but may also be a
        distributor or repackager.

        Returns:
            `OrganizationalEntity` if set else `None`
        """
        return self._supplier

    @supplier.setter
    def supplier(self, supplier: Optional[OrganizationalEntity]) -> None:
        self._supplier = supplier

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(2)
    def manufacturer(self) -> Optional[OrganizationalEntity]:
        """
        The organization that created the component.
        Manufacturer is common in components created through automated processes.
        Components created through manual means may have `@.authors` instead.

        Returns:
            `OrganizationalEntity` if set else `None`
        """
        return self._manufacturer

    @manufacturer.setter
    def manufacturer(self, manufacturer: Optional[OrganizationalEntity]) -> None:
        self._manufacturer = manufacturer

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'author')
    @serializable.xml_sequence(3)
    def authors(self) -> 'SortedSet[OrganizationalContact]':
        """
        The person(s) who created the component.
        Authors are common in components created through manual processes.
        Components created through automated means may have `@.manufacturer` instead.

        Returns:
            `Iterable[OrganizationalContact]` if set else `None`
        """
        return self._authors

    @authors.setter
    def authors(self, authors: Iterable[OrganizationalContact]) -> None:
        self._authors = SortedSet(authors)

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(4)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def author(self) -> Optional[str]:
        """
        The person(s) or organization(s) that authored the component.

        Returns:
            `str` if set else `None`
        """
        return self._author

    @author.setter
    def author(self, author: Optional[str]) -> None:
        if author is not None:
            SchemaDeprecationWarning1Dot6._warn('@.author', '@.authors` or `@.manufacturer')
        self._author = author

    @property
    @serializable.xml_sequence(5)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def publisher(self) -> Optional[str]:
        """
        The person(s) or organization(s) that published the component

        Returns:
            `str` if set else `None`
        """
        return self._publisher

    @publisher.setter
    def publisher(self, publisher: Optional[str]) -> None:
        self._publisher = publisher

    @property
    @serializable.xml_sequence(6)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def group(self) -> Optional[str]:
        """
        The grouping name or identifier. This will often be a shortened, single name of the company or project that
        produced the component, or the source package or domain name. Whitespace and special characters should be
        avoided.

        Examples include: `apache`, `org.apache.commons`, and `apache.org`.

        Returns:
            `str` if set else `None`
        """
        return self._group

    @group.setter
    def group(self, group: Optional[str]) -> None:
        self._group = group

    @property
    @serializable.xml_sequence(7)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def name(self) -> str:
        """
        The name of the component.

        This will often be a shortened, single name of the component.

        Examples: `commons-lang3` and `jquery`.

        Returns:
            `str`
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    @serializable.include_none(SchemaVersion1Dot0, '')
    @serializable.include_none(SchemaVersion1Dot1, '')
    @serializable.include_none(SchemaVersion1Dot2, '')
    @serializable.include_none(SchemaVersion1Dot3, '')
    @serializable.xml_sequence(8)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def version(self) -> Optional[str]:
        """
        The component version. The version should ideally comply with semantic versioning but is not enforced.

        This is NOT optional for CycloneDX Schema Version < 1.4 but was agreed to default to an empty string where a
        version was not supplied for schema versions < 1.4

        Returns:
            Declared version of this Component as `str` or `None`
        """
        return self._version

    @version.setter
    def version(self, version: Optional[str]) -> None:
        if version and len(version) > 1024:
            warn('`@.version`has a maximum length of 1024 from CycloneDX v1.6 onwards.', UserWarning)
        self._version = version

    @property
    @serializable.xml_sequence(9)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def description(self) -> Optional[str]:
        """
        Get the description of this Component.

        Returns:
            `str` if set, else `None`.
        """
        return self._description

    @description.setter
    def description(self, description: Optional[str]) -> None:
        self._description = description

    @property
    @serializable.type_mapping(_ComponentScopeSerializationHelper)
    @serializable.xml_sequence(10)
    def scope(self) -> Optional[ComponentScope]:
        """
        Specifies the scope of the component.

        If scope is not specified, 'required' scope should be assumed by the consumer of the BOM.

        Returns:
            `ComponentScope` or `None`
        """
        return self._scope

    @scope.setter
    def scope(self, scope: Optional[ComponentScope]) -> None:
        self._scope = scope

    @property
    @serializable.json_name('isExternal')
    @serializable.xml_name('isExternal')
    @serializable.xml_attribute()
    @serializable.type_mapping(_XmlBoolAttributeSH)
    @serializable.view(SchemaVersion1Dot7)
    def is_external(self) -> Optional[bool]:
        """
        Determine whether this component is external. An external component is one that is not part of an assembly,
        but is expected to be provided by the environment, regardless of the component's scope. This setting can be
        useful for distinguishing which components are bundled with the product and which can be relied upon to be
        present in the deployment environment. This may be set to true for runtime components only. For
        metadata.component, it must be set to false.

        Returns:
            `bool` if set else `None`
        """
        return self._is_external

    @is_external.setter
    def is_external(self, is_external: Optional[bool]) -> None:
        self._is_external = is_external

    @property
    @serializable.type_mapping(_HashTypeRepositorySerializationHelper)
    @serializable.xml_sequence(11)
    def hashes(self) -> 'SortedSet[HashType]':
        """
        Optional list of hashes that help specify the integrity of this Component.

        Returns:
             Set of `HashType`
        """
        return self._hashes

    @hashes.setter
    def hashes(self, hashes: Iterable[HashType]) -> None:
        self._hashes = SortedSet(hashes)

    @property
    @serializable.view(SchemaVersion1Dot1)
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.type_mapping(_LicenseRepositorySerializationHelper)
    @serializable.xml_sequence(12)
    def licenses(self) -> LicenseRepository:
        """
        A optional list of statements about how this Component is licensed.

        Returns:
            Set of `LicenseChoice`
        """
        return self._licenses

    @licenses.setter
    def licenses(self, licenses: Iterable[License]) -> None:
        self._licenses = LicenseRepository(licenses)

    @property
    @serializable.xml_sequence(13)
    @serializable.xml_string(serializable.XmlStringSerializationType.NORMALIZED_STRING)
    def copyright(self) -> Optional[str]:
        """
        An optional copyright notice informing users of the underlying claims to copyright ownership in a published
        work.

        Returns:
            `str` or `None`
        """
        return self._copyright

    @copyright.setter
    def copyright(self, copyright: Optional[str]) -> None:
        self._copyright = copyright

    @property
    @serializable.xml_sequence(14)
    def cpe(self) -> Optional[str]:
        """
        Specifies a well-formed CPE name that conforms to the CPE 2.2 or 2.3 specification.
        See https://nvd.nist.gov/products/cpe

        Returns:
            `str` if set else `None`
        """
        return self._cpe

    @cpe.setter
    def cpe(self, cpe: Optional[str]) -> None:
        self._cpe = cpe

    @property
    @serializable.type_mapping(PackageUrlSH)
    @serializable.xml_sequence(15)
    def purl(self) -> Optional[PackageURL]:
        """
        Specifies the package-url (PURL).

        The purl, if specified, must be valid and conform to the specification defined at:
        https://github.com/package-url/purl-spec

        Returns:
            `PackageURL` or `None`
        """
        return self._purl

    @purl.setter
    def purl(self, purl: Optional[PackageURL]) -> None:
        self._purl = purl

    @property
    @serializable.json_name('omniborId')
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, child_name='omniborId')
    @serializable.xml_sequence(16)
    def omnibor_ids(self) -> 'SortedSet[OmniborId]':
        """
        Specifies the OmniBOR Artifact ID. The OmniBOR, if specified, MUST be valid and conform to the specification
        defined at: https://www.iana.org/assignments/uri-schemes/prov/gitoid

        Returns:
            `Iterable[str]` or `None`
        """

        return self._omnibor_ids

    @omnibor_ids.setter
    def omnibor_ids(self, omnibor_ids: Iterable[OmniborId]) -> None:
        self._omnibor_ids = SortedSet(omnibor_ids)

    @property
    @serializable.json_name('swhid')
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.FLAT, child_name='swhid')
    @serializable.xml_sequence(17)
    def swhids(self) -> 'SortedSet[Swhid]':
        """
        Specifies the Software Heritage persistent identifier (SWHID). The SWHID, if specified, MUST be valid and
        conform to the specification defined at:
        https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html

        Returns:
            `Iterable[Swhid]` if set else `None`
        """
        return self._swhids

    @swhids.setter
    def swhids(self, swhids: Iterable[Swhid]) -> None:
        self._swhids = SortedSet(swhids)

    @property
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(18)
    def swid(self) -> Optional[Swid]:
        """
        Specifies metadata and content for ISO-IEC 19770-2 Software Identification (SWID) Tags.

        Returns:
            `Swid` if set else `None`
        """
        return self._swid

    @swid.setter
    def swid(self, swid: Optional[Swid]) -> None:
        self._swid = swid

    @property
    @serializable.view(SchemaVersion1Dot0)  # todo: Deprecated in v1.3
    @serializable.xml_sequence(19)
    def modified(self) -> bool:
        return self._modified

    @modified.setter
    def modified(self, modified: bool) -> None:
        if modified:
            SchemaDeprecationWarning1Dot3._warn('@.modified', '@.pedigree')
        self._modified = modified

    @property
    @serializable.view(SchemaVersion1Dot1)
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(20)
    def pedigree(self) -> Optional[Pedigree]:
        """
        Component pedigree is a way to document complex supply chain scenarios where components are created,
        distributed, modified, redistributed, combined with other components, etc.

        Returns:
            `Pedigree` if set else `None`
        """
        return self._pedigree

    @pedigree.setter
    def pedigree(self, pedigree: Optional[Pedigree]) -> None:
        self._pedigree = pedigree

    @property
    @serializable.view(SchemaVersion1Dot1)
    @serializable.view(SchemaVersion1Dot2)
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'reference')
    @serializable.xml_sequence(21)
    def external_references(self) -> 'SortedSet[ExternalReference]':
        """
        Provides the ability to document external references related to the component or to the project the component
        describes.

        Returns:
            Set of `ExternalReference`
        """
        return self._external_references

    @external_references.setter
    def external_references(self, external_references: Iterable[ExternalReference]) -> None:
        self._external_references = SortedSet(external_references)

    @property
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'property')
    @serializable.xml_sequence(22)
    def properties(self) -> 'SortedSet[Property]':
        """
        Provides the ability to document properties in a key/value store. This provides flexibility to include data not
        officially supported in the standard without having to use additional namespaces or create extensions.

        Return:
            Set of `Property`
        """
        return self._properties

    @properties.setter
    def properties(self, properties: Iterable[Property]) -> None:
        self._properties = SortedSet(properties)

    @property
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'component')
    @serializable.xml_sequence(23)
    def components(self) -> "SortedSet['Component']":
        """
        A list of software and hardware components included in the parent component. This is not a dependency tree. It
        provides a way to specify a hierarchical representation of component assemblies, similar to system -> subsystem
        -> parts assembly in physical supply chains.

        Returns:
            Set of `Component`
        """
        return self._components

    @components.setter
    def components(self, components: Iterable['Component']) -> None:
        self._components = SortedSet(components)

    @property
    @serializable.view(SchemaVersion1Dot3)
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(24)
    @serializable.type_mapping(_ComponentEvidenceSerializationHelper)
    def evidence(self) -> Optional[ComponentEvidence]:
        """
        Provides the ability to document evidence collected through various forms of extraction or analysis.

        Returns:
            `ComponentEvidence` if set else `None`
        """
        return self._evidence

    @evidence.setter
    def evidence(self, evidence: Optional[ComponentEvidence]) -> None:
        self._evidence = evidence

    @property
    @serializable.view(SchemaVersion1Dot4)
    @serializable.view(SchemaVersion1Dot5)
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(25)
    def release_notes(self) -> Optional[ReleaseNotes]:
        """
        Specifies optional release notes.

        Returns:
            `ReleaseNotes` or `None`
        """
        return self._release_notes

    @release_notes.setter
    def release_notes(self, release_notes: Optional[ReleaseNotes]) -> None:
        self._release_notes = release_notes

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot5)
    # @serializable.xml_sequence(22)
    # def model_card(self) -> ...:
    #     ...  # TODO since CDX1.5
    #
    # @model_card.setter
    # def model_card(self, ...) -> None:
    #     ...  # TODO since CDX1.5

    # @property
    # ...
    # @serializable.view(SchemaVersion1Dot5)
    # @serializable.xml_sequence(23)
    # def data(self) -> ...:
    #     ...  # TODO since CDX1.5
    #
    # @data.setter
    # def data(self, ...) -> None:
    #     ...  # TODO since CDX1.5

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_sequence(30)
    def crypto_properties(self) -> Optional[CryptoProperties]:
        """
        Cryptographic assets have properties that uniquely define them and that make them actionable for further
        reasoning. As an example, it makes a difference if one knows the algorithm family (e.g. AES) or the specific
        variant or instantiation (e.g. AES-128-GCM). This is because the security level and the algorithm primitive
        (authenticated encryption) is only defined by the definition of the algorithm variant. The presence of a weak
        cryptographic algorithm like SHA1 vs. HMAC-SHA1 also makes a difference.

        Returns:
            `CryptoProperties` or `None`
        """
        return self._crypto_properties

    @crypto_properties.setter
    def crypto_properties(self, crypto_properties: Optional[CryptoProperties]) -> None:
        self._crypto_properties = crypto_properties

    @property
    @serializable.view(SchemaVersion1Dot6)
    @serializable.view(SchemaVersion1Dot7)
    @serializable.xml_array(serializable.XmlArraySerializationType.NESTED, 'tag')
    @serializable.xml_sequence(31)
    def tags(self) -> 'SortedSet[str]':
        """
        Textual strings that aid in discovery, search, and retrieval of the associated object.
        Tags often serve as a way to group or categorize similar or related objects by various attributes.

        Returns:
            `Iterable[str]`
        """
        return self._tags

    @tags.setter
    def tags(self, tags: Iterable[str]) -> None:
        self._tags = SortedSet(tags)

    def get_all_nested_components(self, include_self: bool = False) -> set['Component']:
        components = set()
        if include_self:
            components.add(self)

        for c in self.components:
            components.update(c.get_all_nested_components(include_self=True))

        return components

    def get_pypi_url(self) -> str:
        if self.version:
            return f'https://pypi.org/project/{self.name}/{self.version}'
        else:
            return f'https://pypi.org/project/{self.name}'

    def __comparable_tuple(self) -> _ComparableTuple:
        return _ComparableTuple((
            self.type, self.group, self.name, self.version,
            self.bom_ref.value,
            None if self.purl is None else _ComparablePackageURL(self.purl),
            self.swid, self.cpe, _ComparableTuple(self.swhids),
            self.supplier, self.author, self.publisher,
            self.description,
            self.mime_type, self.scope, _ComparableTuple(self.hashes),
            _ComparableTuple(self.licenses), self.copyright,
            self.pedigree,
            _ComparableTuple(self.external_references), _ComparableTuple(self.properties),
            _ComparableTuple(self.components), self.evidence, self.release_notes, self.modified,
            _ComparableTuple(self.authors), _ComparableTuple(self.omnibor_ids), self.manufacturer,
            self.crypto_properties, _ComparableTuple(self.tags),
            self.is_external,
        ))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Component):
            return self.__comparable_tuple() == other.__comparable_tuple()
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Component):
            return self.__comparable_tuple() < other.__comparable_tuple()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__comparable_tuple())

    def __repr__(self) -> str:
        return f'<Component bom-ref={self.bom_ref!r}, group={self.group}, name={self.name}, ' \
            f'version={self.version}, type={self.type}>'
