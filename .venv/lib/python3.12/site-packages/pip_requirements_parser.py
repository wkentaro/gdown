
# Copyright (c) The pip developers (see AUTHORS.txt file)
# portions Copyright (C) 2016 Jason R Coombs <jaraco@jaraco.com>
# portions Copyright (C) nexB Inc. and others
#
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import codecs
import locale
import functools
import io
import logging
import operator
import optparse
import os
import posixpath
import re
import shlex
import shutil
import string
import sys
import tempfile
import urllib.parse
import urllib.request

from functools import partial
from optparse import Values
from optparse import Option

from typing import (
    Any,
    BinaryIO,
    Callable,
    Collection,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    NewType,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from packaging.markers import Marker
from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement
from packaging.specifiers import Specifier
from packaging.specifiers import SpecifierSet
from packaging.tags import Tag
from packaging.version import parse
from packaging.version import Version

from packaging_legacy_version import LegacyVersion
"""
A pip requirements files parser, doing it as well as pip does it because it is
based on pip's own code.

The code is merged from multiple pip modules. And each pip code section is
tagged with comments:
    # PIPREQPARSE: from ...
    # PIPREQPARSE: end from ...

We also kept the pip git line-level, blame history of all these modules.

In constrast with pip, it may not fail on invalid requirements.
Instead it will accumulate these as invalid lines.

It can also dump back a requirements file, preserving most but not all
formatting. Dumping does these high level transformations:

- include informative extra comment lines about a line with an error before that
  line.

- some lines with errors (such as invalid per requirement options) may be
  stripped from their original lines and reported as an error comment instead

- multiple empty lines are folded in one empty line,

- spaces are normalized, including spaces before an end of line comment, and 
  leading and trailing spaces on a line, and spaces inside a requirement

- short form options (such as -e or -r) are converted to their long form
  (--editable).

- most lines with continuations \\ are folded back on a single line except
  for the --hash option which is always folded using pip-tools folding
  style.


Architecture and API
---------------------

The ``RequirementsFile`` object is the main API and entry point. It contains lists
of objects resulting from parsing:

- requirements (as in "django==3.2") as ``InstallRequirement`` or ``EditableRequirement``
- options (as in "--requirement file.txt") as ``OptionLine``
- comment lines (as in "# comment" including EOL comments) as simple ``CommentLine``
- invalid lines that cannot be parsed with an error message as
  ``InvalidRequirementLine`` or `IncorrectRequirement``

Each item of these lists must be on a single unfolded line. Each object has
a "requirement_line" to track the original text line, line number and filename.

These objects are the API for now.
"""

################################################################################
# The pip requirement styles
"""
A pip requirement line comes in many styles. Some are supported by the
``packaging`` library some are not.


Standard ``packaging``-supported requirement lines
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- a standard ``packaging`` requirement as name[extras]<specifiers,>;marker
  For example: "django[extras]==3.2;marker"

    - non-standard pip additions: same with pip per-requirement options such
      as --hash

- a standard ``packaging`` pep 508 URL as in name[extras]@url
  This is a standard packaging requirement.
  For example: boolean.py[bar]@https://github.com/bastikr/boolean.py.git

    - non-standard pip additions: support for VCS URLs. packaging can parse
      these though pip's code is needed to interpret them.
      For example: boolean.py[bar]@git+https://github.com/bastikr/boolean.py.git

    - non-standard pip additions: same with trailing #fragment. pip will
      recognize trailing name[extra]@url#[extras]<specifiers>;marker and when
      these exist they override the extra before the @ if any. They must also
      align with whatever is behind the URL in terms of name and version or else
      pip will error out. This may be an undocumented non-feature. For example: 
      boolean.py@git+https://github.com/bastikr/boolean.py.git#[foo]==3.8;python_version=="3.6"

    - non-standard pip additions: same with pip per-requirement options such
      as --hash but --hash is an error for a pip VCS URL and non-pinned
      requirements.


pip-specific requirement lines:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- a # comment line, including end-of-line comments

- a pip option such as --index-url

- a pip local path to a directory, archive or wheel.
  A local path to a dir with a single segment must ends with a / else it will be
  recognized only as a name and looked up on PyPI or the provided index.

- a pip URL to an archive or wheel or a pip VCS URL
  For example: git+https://github.com/bastikr/boolean.py.git

- same with an #egg=[extras]<specifiers>;marker fragment in which case the
  name must match what is installable.
  For example: git+https://github.com/bastikr/boolean.py.git#egg=boolean.py[foo]==3.12

- a pip editable requirement with a -e/--editable option which translates
  roughly to the setuptools develop mode:

  - with a local project directory/ path and optional [extras]
    For example: -e boolean.py-3.8/[sdfsf]

  - with a VCS URL with an #egg=<name>[extras]<specifier> suffix where the name
    is mandatory (no marker).
    For example: -e git+https://github.com/bastikr/boolean.py.git#egg=boolean.py[foo]==3.1
"""


class RequirementsFile:
    """
    This represents a pip requirements file. It contains the requirements and
    other pip-related options found in a requirerents file. Optionally contains
    nested requirements and constraints files content.
    """

    def __init__(self,
        filename: str,
        requirements: List["InstallRequirement"],
        options: List["OptionLine"],
        invalid_lines: List["InvalidRequirementLine"],
        comments: List["CommentRequirementLine"],
    ) -> None:
        """
        Initialise a new RequirementsFile from a ``filename`` path string.
        """
        self.filename = filename
        self.requirements = requirements
        self.options = options
        self.invalid_lines = invalid_lines
        self.comments = comments

    @classmethod
    def from_file(cls, filename: str, include_nested=False) -> "RequirementsFile":
        """
        Return a new RequirementsFile from a ``filename`` path string.

        If ``include_nested`` is True also resolve, parse and load
        -r/--requirement adn -c--constraint requirements and constraints files
        referenced in the requirements file.
        """
        requirements: List[InstallRequirement] = []
        options: List[OptionLine] = []
        invalid_lines: List[Union[IncorrectRequirementLine, InvalidRequirementLine]] = []
        comments: List[CommentRequirementLine] = []

        for parsed in cls.parse(
            filename=filename,
            include_nested=include_nested,
        ):

            if isinstance(parsed, InvalidRequirementLine):
                invalid_lines.append(parsed)
            elif isinstance(parsed, CommentRequirementLine):
                comments.append(parsed)
            elif isinstance(parsed, OptionLine):
                options.append(parsed)
            elif isinstance(parsed, InstallRequirement):
                requirements.append(parsed)
            else:
                raise Exception("Unknown requirement line type: {parsed!r}")

        return RequirementsFile(
            filename=filename,
            requirements=requirements,
            options=options,
            invalid_lines=invalid_lines,
            comments=comments,
        )

    @classmethod
    def from_string(cls, text: str) -> "RequirementsFile":
        """
        Return a new RequirementsFile from a ``text`` string.

        Since pip requirements are deeply based on files, we create a temp file
        to feed to pip even if this feels a bit hackish.
        """
        tmpdir = None
        try:
            tmpdir = Path(str(tempfile.mkdtemp()))
            req_file = tmpdir / "requirements.txt"
            with open(req_file, "w") as rf:
                rf.write(text)
            return cls.from_file(filename=str(req_file), include_nested=False)
        finally:
            if tmpdir and tmpdir.exists():
                shutil.rmtree(path=str(tmpdir), ignore_errors=True)

    @classmethod
    def parse(
        cls, 
        filename: str, 
        include_nested=False,
        is_constraint=False,
    ) -> Iterator[Union[
        "InstallRequirement",
        "OptionLine",
        "InvalidRequirementLine",
        "CommentRequirementLine",
    ]]:
        """
        Yield requirements, options and lines from a ``filename``.

        If ``include_nested`` is True also resolve, parse and load
        -r/--requirement adn -c--constraint requirements and constraints files
        referenced in the requirements file.

        """
        for parsed in parse_requirements(
            filename=filename,
            include_nested=include_nested,
            is_constraint=is_constraint,
        ):
            if isinstance(parsed, (InvalidRequirementLine, CommentRequirementLine)):
                yield parsed

            elif isinstance(parsed, OptionLine):
                yield parsed
                for opt in parsed.options:
                    if opt in LEGACY_OPTIONS_DEST:
                        opts = OPT_BY_OPTIONS_DEST[opt]
                        yield IncorrectRequirementLine(
                            requirement_line=parsed.requirement_line,
                            error_message=f"Unsupported, legacy option: {opts}",
                        )

            else:
                try:
                    assert isinstance(parsed, ParsedRequirement)
                    req = build_req_from_parsedreq(parsed)
                    if req.invalid_options:
                        invos = dumps_global_options(req.invalid_options)
                        msg = (
                            f"Invalid global options, not supported with a "
                            f"requirement spec: {invos}"
                        )
                        yield InvalidRequirementLine(
                            requirement_line=parsed.requirement_line,
                            error_message=msg,
                        )
                    else:
                        yield req
                except Exception as e:
                    yield InvalidRequirementLine(
                        requirement_line=parsed.requirement_line,
                        error_message=str(e).strip(),
                    )

    def to_dict(self, include_filename=False):
        """
        Return a mapping of plain Python objects for this RequirementsFile
        """
        return dict(
            options =  [
                o.to_dict(include_filename=include_filename)
                for o in self.options
            ],

            requirements = [
                ir.to_dict(include_filename=include_filename)
                for ir in self.requirements
            ],

            invalid_lines = [
                upl.to_dict(include_filename=include_filename)
                for upl in self.invalid_lines
            ],

            comments = [
                cl.to_dict(include_filename=include_filename)
                for cl in self.comments
            ]
        )

    def dumps(self, preserve_one_empty_line=False):
        """
        Return a requirements string representing this requirements file. The
        requirements are reconstructed from the parsed data.
        """
        items = (
            self.requirements
            + self.invalid_lines
            + self.options
            + self.comments
        )

        # always sort the comments after any other line type
        # and then but InvalidRequirementLine before other lines
        # so we can report error messages as comments before the actual line
        sort_by = lambda l: (
            l.line_number, 
            isinstance(l, CommentRequirementLine,),
            not isinstance(l, InvalidRequirementLine,),
        )

        by_line_number = sorted(items, key=sort_by)

        dumped = []
        previous = None

        for rq in by_line_number:
            if previous:
                if previous.line_number == rq.line_number:
                    if isinstance(rq, CommentRequirementLine):
                        # trailing comment, append to end of previous line
                        previous_line = dumped[-1]
                        trailing_comment = rq.dumps()
                        line_with_comment =  f"{previous_line} {trailing_comment}"
                        dumped[-1] = line_with_comment
                        continue
                else:
                    if (
                        preserve_one_empty_line
                        and rq.line_number > previous.line_number + 1
                        and not isinstance(rq, InvalidRequirementLine)
                    ):
                        dumped.append("")

            dumped.append(rq.dumps())
            previous = rq

        dumps = "\n".join(dumped) + "\n"
        return dumps


class ToDictMixin:

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.to_dict(include_filename=True)
                == other.to_dict(include_filename=True)
        )

    def to_dict(self, include_filename=False):
        data = dict(
            line_number=self.line_number,
            line=self.line,
        )
        if include_filename:
            data.update(dict(filename=self.filename))
        return data


class RequirementLineMixin:

    @property
    def line(self) -> Optional[str]:
        return self.requirement_line and self.requirement_line.line  or None

    @property
    def line_number(self) -> Optional[int]:
        return self.requirement_line and self.requirement_line.line_number  or None

    @property
    def filename(self) -> Optional[str]:
        return self.requirement_line and self.requirement_line.filename  or None


IS_VALID_NAME =re.compile(
    r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", 
    re.IGNORECASE
).match


def is_valid_name(name: str):
    """
    Return True if the name is a valid Python package name
    per:
    - https://www.python.org/dev/peps/pep-0426/#name
    - https://www.python.org/dev/peps/pep-0508/#names
    """
    return name and IS_VALID_NAME(name)


class RequirementLine(ToDictMixin):
    """
    A line from a requirement ``filename``. This is a logical line with folded
    continuations where ``line_number`` is the first line number where this
    logical line started.
    """
    def __init__(
        self,
        line: str,
        line_number: Optional[int] = 0,
        filename: Optional[str] = None,
    ) -> None:

        self.line =line 
        self.filename = filename
        self.line_number = line_number

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
                f"line_number={self.line_number!r}, "
                f"line={self.line!r}, "
                f"filename={self.filename!r}"
            ")"
        )

    def dumps(self):
        return self.line


class CommentRequirementLine(RequirementLine):
    """
    This represents the comment portion of a line in a requirements file.
    """


def dumps_requirement_options(
    options,
    opt_string,
    quote_value=False,
    one_per_line=False,
):
    """
    Given a list of ``options`` and an ``opt_string``, return a string suitable
    for use in a pip requirements file. Raise Exception if any option name or
    value type is unknown.
    """
    option_items = []
    if quote_value:
        q = '"'
    else:
        q = ""

    if one_per_line:
        l = "\\\n    "
    else:
        l = ""

    for opt in options:
        if isinstance(opt, str):
            option_items.append(f"{l}{opt_string}={q}{opt}{q}")
        elif isinstance(opt, list):
            for val in sorted(opt):
                option_items.append(f"{l}{opt_string}={q}{val}{q}")
        else:
            raise Exception(
                f"Internal error: Unknown requirement option {opt!r} "
            )

    return " ".join(option_items)


class OptionLine(RequirementLineMixin, ToDictMixin):
    """
    This represents an a CLI-style "global" option line in a requirements file
    with a mapping of name to values. Technically only one global option per
    line is allowed, but we track a mapping in case this is not the case.
    """
    def __init__(
        self,
        requirement_line: RequirementLine,
        options: Dict,
    ) -> None:

        self.requirement_line = requirement_line
        self.options = options

    def to_dict(self, include_filename=False):
        data = self.requirement_line.to_dict(include_filename=include_filename)
        data.update(self.options)
        return data

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
                f"requirement_line={self.requirement_line!r}, "
                f"options={self.options!r}"
            ")"
        )

    def dumps(self):
        return dumps_global_options(self.options)


def dumps_global_options(options):
    """
    Given a mapping of options, return a string suitable for use in a pip
    requirements file. Raise Exception if the options name or value type is
    unknown.
    """
    option_items = []

    for name, value in sorted(options.items()):
        opt_string = OPT_BY_OPTIONS_DEST.get(name)

        invalid_message = (
            f"Internal error: Unknown requirement option {name!r} "
            f"with value: {value!r}"
        )

        if not opt_string:
            raise InstallationError(invalid_message)

        if isinstance(value, list):
            for val in value:
                option_items.append(f"{opt_string} {val}")

        elif isinstance(value, str):
            option_items.append(f"{opt_string} {value}")

        elif isinstance(value, bool) or value is None:
            option_items.append(f"{opt_string}")

        else:
            raise InstallationError(invalid_message)

    return " ".join(option_items)


class InvalidRequirementLine(RequirementLineMixin, ToDictMixin):
    """
    This represents an unparsable or invalid line of a requirements file.
    """
    def __init__(
        self,
        requirement_line: RequirementLine,
        error_message: str,
    ) -> None:
        self.requirement_line = requirement_line
        self.error_message = error_message.strip()

    def to_dict(self, include_filename=False):
        data = self.requirement_line.to_dict(include_filename=include_filename)
        data.update(error_message=self.error_message)
        return data

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
                f"requirement_line={self.requirement_line!r}, "
                f"error_message={self.error_message!r}"
            ")"
        )

    def dumps(self):
        # dump error message as an extra comment line so it is
        # quite visible in diffs
        return f"# {self.error_message}\n{self.line}"


class IncorrectRequirementLine(InvalidRequirementLine):
    """
    This represents an incorrect line of a requirements file. It can be parsed
    but is not correct.
    """

    def dumps(self):
        # dump error message as an extra comment line, do not dump the line
        # itself since it does exists on its own elsewhere
        return f"# {self.error_message}"

################################################################################
# From here down, most of the code is derived from pip


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/compat.py

# windows detection, covers cpython and ironpython
WINDOWS = (sys.platform.startswith("win") or
           (sys.platform == 'cli' and os.name == 'nt'))

# PIPREQPARSE: end from src/pip/_internal/utils/compat.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/encoding.py

BOMS: List[Tuple[bytes, str]] = [
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF32, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
]

ENCODING_RE = re.compile(rb"coding[:=]\s*([-\w.]+)")


def auto_decode(data: bytes) -> str:
    """Check a bytes string for a BOM to correctly detect the encoding
    Fallback to locale.getpreferredencoding(False) like open() on Python3"""
    for bom, encoding in BOMS:
        if data.startswith(bom):
            return data[len(bom) :].decode(encoding)
    # Lets check the first two lines as in PEP263
    for line in data.split(b"\n")[:2]:
        if line[0:1] == b"#" and ENCODING_RE.search(line):
            result = ENCODING_RE.search(line)
            assert result is not None
            encoding = result.groups()[0].decode("ascii")
            return data.decode(encoding)
    return data.decode(
        locale.getpreferredencoding(False) or sys.getdefaultencoding(),
    )

# PIPREQPARSE: end from src/pip/_internal/utils/encoding.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/exceptions.py

class PipError(Exception):
    """The base pip error."""


class InstallationError(PipError):
    """General exception during installation"""


class RequirementsFileParseError(InstallationError):
    """Raised when a general error occurs parsing a requirements file line."""


class CommandError(PipError):
    """Raised when there is an error in command-line arguments"""


class InvalidWheelFilename(InstallationError):
    """Invalid wheel filename."""


# PIPREQPARSE: end from src/pip/_internal/exceptions.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/cli/cmdoptions.py:
# most callable renamed with cmdoptions_ prefix


index_url: Callable[..., Option] = partial(
    Option,
    "-i",
    "--index-url",
    "--pypi-url",
    dest="index_url",
    metavar="URL",
    default=None,
    help="Base URL of the Python Package Index (default %default). "
    "This should point to a repository compliant with PEP 503 "
    "(the simple repository API) or a local directory laid out "
    "in the same format.",
)


# use a wrapper to ensure the default [] is not a shared global
def extra_index_url() -> Option:
    return Option(
        "--extra-index-url",
        dest="extra_index_urls",
        metavar="URL",
        action="append",
        default=[],
        help="Extra URLs of package indexes to use in addition to "
        "--index-url. Should follow the same rules as "
        "--index-url.",
    )


no_index: Callable[..., Option] = partial(
    Option,
    "--no-index",
    dest="no_index",
    action="store_true",
    default=False,
    help="Ignore package index (only looking at --find-links URLs instead).",
)


# use a wrapper to ensure the default [] is not a shared global
def find_links() -> Option:
    return Option(
        "-f",
        "--find-links",
        dest="find_links",
        action="append",
        default=[],
        metavar="url",
        help="If a URL or path to an html file, then parse for links to "
        "archives such as sdist (.tar.gz) or wheel (.whl) files. "
        "If a local path or file:// URL that's a directory, "
        "then look for archives in the directory listing. "
        "Links to VCS project URLs are not supported.",
    )


# use a wrapper to ensure the default [] is not a shared global
def trusted_host() -> Option:
    return Option(
        "--trusted-host",
        dest="trusted_hosts",
        action="append",
        metavar="HOSTNAME",
        default=[],
        help="Mark this host or host:port pair as trusted, even though it "
        "does not have valid or any HTTPS.",
    )


# use a wrapper to ensure the default [] is not a shared global
def constraints() -> Option:
    return Option(
        "-c",
        "--constraint",
        dest="constraints",
        action="append",
        default=[],
        metavar="file",
        help="Constrain versions using the given constraints file. "
        "This option can be used multiple times.",
    )


# use a wrapper to ensure the default [] is not a shared global
def requirements() -> Option:
    return Option(
        "-r",
        "--requirement",
        # See https://github.com/di/pip-api/commit/7e2f1e8693da249156b99ec593af1e61192c611a#r64188234
        # --requirements is not a valid pip option
        # but we accept anyway as it may exist in the wild
        "--requirements",
        dest="requirements",
        action="append",
        default=[],
        metavar="file",
        help="Install from the given requirements file. "
        "This option can be used multiple times.",
    )


# use a wrapper to ensure the default [] is not a shared global
def editable() -> Option:
    return Option(
        "-e",
        "--editable",
        dest="editables",
        action="append",
        default=[],
        metavar="path/url",
        help=(
            "Install a project in editable mode (i.e. setuptools "
            '"develop mode") from a local project path or a VCS url.'
        ),
    )


# use a wrapper to ensure the default [] is not a shared global
def no_binary() -> Option:
    return Option(
        "--no-binary",
        dest="no_binary",
        action="append",
        default=[],
        type="str",
        help="Do not use binary packages. Can be supplied multiple times, and "
        'each time adds to the existing value. Accepts either ":all:" to '
        'disable all binary packages, ":none:" to empty the set (notice '
        "the colons), or one or more package names with commas between "
        "them (no colons). Note that some packages are tricky to compile "
        "and may fail to install when this option is used on them.",
    )


# use a wrapper to ensure the default [] is not a shared global
def only_binary() -> Option:
    return Option(
        "--only-binary",
        dest="only_binary",
        action="append",
        default=[],
        help="Do not use source packages. Can be supplied multiple times, and "
        'each time adds to the existing value. Accepts either ":all:" to '
        'disable all source packages, ":none:" to empty the set, or one '
        "or more package names with commas between them. Packages "
        "without binary distributions will fail to install when this "
        "option is used on them.",
    )


prefer_binary: Callable[..., Option] = partial(
    Option,
    "--prefer-binary",
    dest="prefer_binary",
    action="store_true",
    default=False,
    help="Prefer older binary packages over newer source packages.",
)


install_options: Callable[..., Option] = partial(
    Option,
    "--install-option",
    dest="install_options",
    action="append",
    metavar="options",
    help="Extra arguments to be supplied to the setup.py install "
    'command (use like --install-option="--install-scripts=/usr/local/'
    'bin"). Use multiple --install-option options to pass multiple '
    "options to setup.py install. If you are using an option with a "
    "directory path, be sure to use absolute path.",
)


global_options: Callable[..., Option] = partial(
    Option,
    "--global-option",
    dest="global_options",
    action="append",
    metavar="options",
    help="Extra global options to be supplied to the setup.py "
    "call before the install or bdist_wheel command.",
)


pre: Callable[..., Option] = partial(
    Option,
    "--pre",
    action="store_true",
    default=False,
    help="Include pre-release and development versions. By default, "
    "pip only finds stable versions.",
)


# use a wrapper to ensure the default [] is not a shared global
def cmdoptions_hash() -> Option:
    return Option(
        "--hash",
        dest="hashes",
        action="append",
        default=[],
        help="Verify that the package's archive matches this "
        "hash before installing. Example: --hash=sha256:abcdef...",
    )


require_hashes: Callable[..., Option] = partial(
    Option,
    "--require-hashes",
    dest="require_hashes",
    action="store_true",
    default=False,
    help="Require a hash to check each requirement against, for "
    "repeatable installs. This option is implied when any package in a "
    "requirements file has a --hash option.",
)


# use a wrapper to ensure the default [] is not a shared global
def use_feature() -> Option:
    return Option(
    "--use-feature",
    dest="use_features",
    action="append",
    default=[],
    help="Enable new functionality, that may be backward incompatible.",
)

# PIPREQPARSE: end from src/pip/_internal/cli/cmdoptions.py:
################################################################################

# Support for deprecated, legacy options

"""
See https://github.com/pypa/pip/pull/3070
See https://legacy.python.org/dev/peps/pep-0470/
--allow-all-external
--allow-external
--allow-unverified
"""

allow_all_external: Callable[..., Option] = partial(
    Option,
    "--allow-all-external",
    dest="allow_all_external",
    action="store_true",
    default=False,
)

# use a wrapper to ensure the default [] is not a shared global
def allow_external() -> Option:
    return Option(
        "--allow-external",
        dest="allow_external",
        action="append",
        default=[],
    )

# use a wrapper to ensure the default [] is not a shared global
def allow_unverified() -> Option:
    return Option(
        "--allow-unverified",
        dest="allow_unverified",
        action="append",
        default=[],
    )

"""
See https://github.com/pypa/pip/issues/8408
-Z
--always-unzip
"""
always_unzip: Callable[..., Option] = partial(
    Option,
    "-Z",
    "--always-unzip",
    dest="always_unzip",
    action="store_true",
    default=False,
)


"""
Per https://github.com/voxpupuli/puppet-python/issues/309#issuecomment-292292637
--no-use-wheel renamed to --no-binary :all: in pip 7.0 and newer 
pip <= 1.4.1 has no --no-use-wheel option
pip >= 1.5.0 <= 7.0.0 has the --no-use-wheel option but not --no-binary
pip >= 7.0.0 deprecates the --no-use-wheel option in favour to --no-binary
"""
no_use_wheel: Callable[..., Option] = partial(
    Option,
    "--no-use-wheel",
    dest="no_use_wheel",
    action="store_true",
    default=False,
)


LEGACY_OPTIONS: List[Callable[..., optparse.Option]] = [
    allow_all_external,
    allow_external,
    allow_unverified,
    always_unzip,
    no_use_wheel
]

LEGACY_OPTIONS_DEST = [str(o().dest) for o in LEGACY_OPTIONS]


################################################################################
# PIPREQPARSE: from src/pip/_internal/req/req_file.py


class TextLine(NamedTuple):
    line_number: int
    line: str


class CommentLine(NamedTuple):
    line_number: int
    line: str

ReqFileLines = Iterable[Union[Tuple[int, str], TextLine,CommentLine]]

LineParser = Callable[[str], Tuple[str, Values]]

SCHEME_RE = re.compile(r"^(http|https|file):", re.I)
COMMENT_RE = re.compile(r"(^|\s+)(#.*)$")

SUPPORTED_OPTIONS: List[Callable[..., optparse.Option]] = [
    index_url,
    extra_index_url,
    no_index,
    constraints,
    requirements,
    editable,
    find_links,
    no_binary,
    only_binary,
    prefer_binary,
    require_hashes,
    pre,
    trusted_host,
    use_feature,
]

SUPPORTED_OPTIONS_DEST = [str(o().dest) for o in SUPPORTED_OPTIONS]

TOP_LEVEL_OPTIONS_DEST = set(SUPPORTED_OPTIONS_DEST + LEGACY_OPTIONS_DEST)

# options to be passed to requirements
SUPPORTED_OPTIONS_REQ: List[Callable[..., optparse.Option]] = [
    install_options,
    global_options,
    cmdoptions_hash,
]

# the 'dest' string values
SUPPORTED_OPTIONS_REQ_DEST = [str(o().dest) for o in SUPPORTED_OPTIONS_REQ]

# all the options string as "--requirement" by "dest" to help unparse
OPT_BY_OPTIONS_DEST = (
    o() for o in SUPPORTED_OPTIONS + SUPPORTED_OPTIONS_REQ + LEGACY_OPTIONS
)

OPT_BY_OPTIONS_DEST = {
    str(o.dest): o.get_opt_string()
    for o in OPT_BY_OPTIONS_DEST
}


class ParsedRequirement:
    def __init__(
        self,
        requirement_string: str,
        is_editable: bool,
        is_constraint: bool,
        options: Optional[Dict[str, Any]] = None,
        requirement_line: Optional[RequirementLine] = None,
        invalid_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.requirement_string = requirement_string
        self.is_editable = is_editable
        self.is_constraint = is_constraint
        self.options = options
        self.requirement_line = requirement_line
        self.invalid_options = invalid_options


class ParsedLine:
    def __init__(
        self,
        requirement_line: RequirementLine,
        requirement_string: str,
        options: Values,
        is_constraint: bool,
        arguments: Optional[List[str]] = ()
    ) -> None:

        self.requirement_line = requirement_line
        self.options = options
        self.is_constraint = is_constraint

        self.arguments = arguments or []

        self.is_requirement = True
        self.is_editable = False

        if requirement_string:
            self.requirement_string = requirement_string
        elif options.editables:
            self.is_editable = True
            # We don't support multiple -e on one line
            # FIXME: report warning if there are more than one
            self.requirement_string = options.editables[0]
        else:
            self.is_requirement = False


def parse_requirements(
    filename: str,
    is_constraint: bool = False,
    include_nested: bool = True,
) -> Iterator[Union[
    ParsedRequirement,
    OptionLine,
    InvalidRequirementLine,
    CommentRequirementLine,
]]:
    """Parse a requirements file and yield ParsedRequirement,
    InvalidRequirementLine or CommentRequirementLine instances.

    :param filename:    Path or url of requirements file.
    :param is_constraint:  If true, parsing a constraint file rather than
        requirements file.
    :param include_nested: if true, also load and parse -r/--requirements
        and -c/--constraints nested files.
    """
    line_parser = get_line_parser()
    parser = RequirementsFileParser(line_parser)

    for parsed_line in parser.parse(
        filename=filename,
        is_constraint=is_constraint,
        include_nested=include_nested,
    ):

        if isinstance(parsed_line, ParsedLine):
            for parsed_req_or_opt in handle_line(parsed_line=parsed_line):
                if parsed_req_or_opt is not None:
                    yield parsed_req_or_opt

        else:
            assert isinstance(parsed_line, (InvalidRequirementLine, CommentRequirementLine,))
            yield parsed_line


def preprocess(content: str) -> ReqFileLines:
    """Split, filter, and join lines, and return a line iterator.
    This contains both CommentLine and TextLine.

    :param content: the content of the requirements file
    """
    lines_enum: ReqFileLines = enumerate(content.splitlines(), start=1)
    lines_enum = join_lines(lines_enum)
    lines_and_comments_enum = split_comments(lines_enum)
    return lines_and_comments_enum


def get_options_by_dest(optparse_options, skip_editable=False):
    """
    Given an optparse Values object, return a {dest: value} mapping.
    """
    options_by_dest = optparse_options.__dict__
    options = {}
    for dest in OPT_BY_OPTIONS_DEST:
        if skip_editable and dest == "editables":
            continue
        value = options_by_dest.get(dest)
        if value:
            options[dest] = value
    return options


def handle_requirement_line(
    parsed_line: ParsedLine,
) -> ParsedRequirement:

    assert parsed_line.is_requirement

    if parsed_line.is_editable:
        # For editable requirements, we don't support per-requirement options,
        # so just return the parsed requirement: options are all invalid except
        # --editable of course
        invalid_options = get_options_by_dest(
            optparse_options=parsed_line.options,
            skip_editable=True,
        )

        return ParsedRequirement(
            requirement_string=parsed_line.requirement_string,
            is_editable=parsed_line.is_editable,
            is_constraint=parsed_line.is_constraint,
            requirement_line=parsed_line.requirement_line,
            invalid_options=invalid_options,
        )
    else:
        options = get_options_by_dest(
            optparse_options=parsed_line.options
        )

        # get the options that apply to requirements
        req_options = {}

        # these global options should not be on a requirement line
        invalid_options = {}

        for dest, value in options.items():
            if dest in SUPPORTED_OPTIONS_REQ_DEST:
                req_options[dest] = value
            else:
                invalid_options[dest] = value

        return ParsedRequirement(
            requirement_string=parsed_line.requirement_string,
            is_editable=parsed_line.is_editable,
            is_constraint=parsed_line.is_constraint,
            options=req_options,
            requirement_line=parsed_line.requirement_line,
            invalid_options=invalid_options,
        )


def handle_option_line(opts: Values) -> Dict:
    """
    Return a mapping of {name: value} for supported pip options.
    """
    options = {}
    for name in SUPPORTED_OPTIONS_DEST + LEGACY_OPTIONS_DEST:
        if hasattr(opts, name):
            value = getattr(opts, name)
            if name in options:
                # An option cannot be repeated on a single line
                raise InstallationError(f"Invalid duplicated option name: {name}")
            if value:
                # strip possible legacy leading equal
                if isinstance(value, str):
                    value = value.lstrip("=")
                if isinstance(value, list):
                    value = [v.lstrip("=") for v in value]
                options[name] = value

    return options


def handle_line(parsed_line: ParsedLine
) -> Iterator[Union[ParsedRequirement, OptionLine, InvalidRequirementLine]]:
    """Handle a single parsed requirements line

    :param parsed_line:        The parsed line to be processed.

    Yield one or mpre a ParsedRequirement, OptionLine or InvalidRequirementLine

    For lines that contain requirements, the only options that have an effect
    are from SUPPORTED_OPTIONS_REQ, and they are scoped to the
    requirement. Other options from SUPPORTED_OPTIONS may be present, but are
    ignored.

    For lines that do not contain requirements, the only options that have an
    effect are from SUPPORTED_OPTIONS. Options from SUPPORTED_OPTIONS_REQ may
    be present, but are ignored. These lines may contain multiple options
    (although our docs imply only one is supported)
    """

    if parsed_line.is_requirement:
        yield handle_requirement_line(parsed_line=parsed_line)
    else:
        options = handle_option_line(
            opts=parsed_line.options,
        )

        args = parsed_line.arguments
        if options and args:
        # there cannot be an option with arguments; if this happens we yield
        # both an OptionLine and an IncorrectRequirementLine
            args = ", ".join(args)
            yield IncorrectRequirementLine(
                requirement_line=parsed_line.requirement_line,
                error_message=f"Incorrect and ignored trailing argument(s): {args}",
            )

        yield OptionLine(
            requirement_line=parsed_line.requirement_line,
            options=options,
        )


class RequirementsFileParser:

    def __init__(self, line_parser: LineParser) -> None:
        self._line_parser = line_parser

    def parse(
        self, 
        filename: str, 
        is_constraint: bool, 
        include_nested: bool = True
    ) -> Iterator[Union[ParsedLine, InvalidRequirementLine, CommentRequirementLine]]:
        """
        Parse a requirements ``filename``, yielding ParsedLine,
        InvalidRequirementLine or CommentRequirementLine.

        If ``include_nested`` is True, also load nested requirements and
        constraints files -r/--requirements and -c/--constraints recursively.

        If ``is_constraint`` is True, tag the ParsedLine as being "constraint"
        originating from a "constraint" file rather than a requirements file.
        """
        yield from self._parse_and_recurse(
            filename=filename,
            is_constraint=is_constraint,
            include_nested=include_nested,
        )

    def _parse_and_recurse(
        self, 
        filename: str, 
        is_constraint: bool, 
        include_nested: bool = True
    ) -> Iterator[Union[ParsedLine, InvalidRequirementLine, CommentRequirementLine]]:
        """
        Parse a requirements ``filename``, yielding ParsedLine,
        InvalidRequirementLine or CommentRequirementLine.

        If ``include_nested`` is True, also load nested requirements and
        constraints files -r/--requirements and -c/--constraints recursively.

        If ``is_constraint`` is True, tag the ParsedLine as being "constraint"
        originating from a "constraint" file rather than a requirements file.
        """
        for line in self._parse_file(filename=filename, is_constraint=is_constraint):

            if (include_nested
                and isinstance(line, ParsedLine) 
                and not line.is_requirement and
                (line.options.requirements or line.options.constraints)
            ):
                # parse a nested requirements file
                if line.options.requirements:
                    if len(line.options.requirements) !=1:
                        # FIXME: this should be an error condition
                        pass
                    req_path = line.options.requirements[0]
                    is_nested_constraint = False

                else:
                    if len(line.options.constraints) !=1:
                        # FIXME: this should be an error condition
                        pass
                    req_path = line.options.constraints[0]
                    is_nested_constraint = True

                # original file is over http
                if SCHEME_RE.search(filename):
                    # do a url join so relative paths work
                    req_path = urllib.parse.urljoin(filename, req_path)
                
                # original file and nested file are paths
                elif not SCHEME_RE.search(req_path):
                    # do a join so relative paths work
                    req_path = os.path.join(
                        os.path.dirname(filename),
                        req_path,
                    )

                yield from self._parse_and_recurse(
                    filename=req_path, 
                    is_constraint=is_nested_constraint,
                    include_nested=include_nested,
                )
            # always yield the line even if we recursively included other
            # nested requirements or constraints files
            yield line

    def _parse_file(self, filename: str, is_constraint: bool
    ) -> Iterator[Union[ParsedLine, InvalidRequirementLine, CommentRequirementLine]]:
        """
        Parse a single requirements ``filename``, yielding ParsedLine,
        InvalidRequirementLine or CommentRequirementLine.

        If ``is_constraint`` is True, tag the ParsedLine as being "constraint"
        originating from a "constraint" file rather than a requirements file.
        """
        content = get_file_content(filename)
        numbered_lines = preprocess(content)

        for numbered_line in numbered_lines:
            line_number, line = numbered_line

            if isinstance(numbered_line, CommentLine):
                yield CommentRequirementLine(
                    line=line,
                    line_number=line_number,
                    filename=filename,
                )
                continue

            requirement_line = RequirementLine(
                line=line,
                line_number=line_number,
                filename=filename,
            )

            try:
                requirement_string, options, arguments = self._line_parser(line)
                yield ParsedLine(
                    requirement_string=requirement_string,
                    options=options,
                    is_constraint=is_constraint,
                    requirement_line=requirement_line,
                    arguments=arguments,
                )
            except Exception as e:
                # return offending line
                yield InvalidRequirementLine(
                    requirement_line=requirement_line,
                    error_message=str(e),
                )


def get_line_parser() -> LineParser:
    def parse_line(line: str) -> Tuple[str, Values]:
        # Build new parser for each line since it accumulates appendable
        # options.
        parser = build_parser()
        defaults = parser.get_default_values()
        args_str, options_str = break_args_options(line)
        opts, arguments = parser.parse_args(shlex.split(options_str), defaults)
        return args_str, opts, arguments
    return parse_line


def break_args_options(line: str) -> Tuple[str, str]:
    """Break up the line into an args and options string.  We only want to shlex
    (and then optparse) the options, not the args.  args can contain marker
    which are corrupted by shlex.
    """
    tokens = line.split(" ")
    args = []
    options = tokens[:]
    for token in tokens:
        if token.startswith("-") or token.startswith("--"):
            break
        else:
            args.append(token)
            options.pop(0)
    return " ".join(args), " ".join(options)


class OptionParsingError(Exception):
    def __init__(self, msg: str) -> None:
        self.msg = msg


def print_usage(self, file=None):
    """
    A mock optparse.OptionParser method to avoid junk outputs on option parsing
    errors.
    """
    return


def build_parser() -> optparse.OptionParser:
    """
    Return a parser for parsing requirement lines
    """
    parser = optparse.OptionParser(
        add_help_option=False,
        # override this otherwise, pytest or the name of the current running main
        # will show up in exceptions
        prog="pip_requirements_parser",
    )
    parser.print_usage = print_usage

    option_factories = SUPPORTED_OPTIONS + SUPPORTED_OPTIONS_REQ + LEGACY_OPTIONS
    for option_factory in option_factories:
        option = option_factory()
        parser.add_option(option)

    # By default optparse sys.exits on parsing errors. We want to wrap
    # that in our own exception.
    def parser_exit(self: Any, msg: str) -> "NoReturn":
        raise OptionParsingError(msg)

    # NOTE: mypy disallows assigning to a method
    #       https://github.com/python/mypy/issues/2427
    parser.exit = parser_exit  # type: ignore

    return parser


def join_lines(lines_enum: ReqFileLines) -> ReqFileLines:
    """Joins a line ending in '\' with the previous line (except when following
    comments).  The joined line takes on the index of the first line.
    """
    primary_line_number = None
    new_line: List[str] = []
    for line_number, line in lines_enum:
        if not line.endswith("\\") or COMMENT_RE.match(line):
            if COMMENT_RE.match(line):
                # this ensures comments are always matched later
                line = " " + line
            if new_line:
                new_line.append(line)
                assert primary_line_number is not None
                yield primary_line_number, "".join(new_line)
                new_line = []
            else:
                yield line_number, line
        else:
            if not new_line:
                primary_line_number = line_number
            new_line.append(line.strip("\\"))

    # last line contains \
    if new_line:
        assert primary_line_number is not None
        yield primary_line_number, "".join(new_line)

    # TODO: handle space after '\'.


def split_comments(lines_enum: ReqFileLines) -> ReqFileLines:
    """
    Split comments from text, strip text and filter empty lines.
    Yield TextLine or Commentline
    """
    for line_number, line in lines_enum:
        parts = [l.strip() for l in COMMENT_RE.split(line) if l.strip()]

        if len(parts) == 1:
            part = parts[0]
            if part.startswith('#'):
                yield CommentLine(line_number=line_number, line=part)
            else:
                yield TextLine(line_number=line_number, line=part)

        elif len(parts) == 2:
            line, comment = parts
            yield TextLine(line_number=line_number, line=line)
            yield CommentLine(line_number=line_number, line=comment)

        else:
            if parts:
                # this should not ever happen
                raise Exception(f"Invalid line/comment: {line!r}")


def get_file_content(filename: str) -> str:
    """
    Return the unicode text content of a filename.
    Respects # -*- coding: declarations on the retrieved files.

    :param filename:         File path.
    """
    try:
        with open(filename, "rb") as f:
            content = auto_decode(f.read())
    except OSError as exc:
        raise InstallationError(
            f"Could not open requirements file: {filename}|n{exc}"
        )
    return content

# PIPREQPARSE: end src/pip/_internal/req/from req_file.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/urls.py

def get_url_scheme(url: str) -> Optional[str]:
    if ":" not in url:
        return None
    return url.split(":", 1)[0].lower()


def url_to_path(url: str) -> str:
    """
    Convert a file: URL to a path.
    """
    assert url.startswith(
        "file:"
    ), f"You can only turn file: urls into filenames (not {url!r})"

    _, netloc, path, _, _ = urllib.parse.urlsplit(url)

    if not netloc or netloc == "localhost":
        # According to RFC 8089, same as empty authority.
        netloc = ""
    elif WINDOWS:
        # If we have a UNC path, prepend UNC share notation.
        netloc = "\\\\" + netloc
    else:
        raise ValueError(
            f"non-local file URIs are not supported on this platform: {url!r}"
        )

    path = urllib.request.url2pathname(netloc + path)

    # On Windows, urlsplit parses the path as something like "/C:/Users/foo".
    # This creates issues for path-related functions like io.open(), so we try
    # to detect and strip the leading slash.
    if (
        WINDOWS
        and not netloc  # Not UNC.
        and len(path) >= 3
        and path[0] == "/"  # Leading slash to strip.
        and path[1] in string.ascii_letters  # Drive letter.
        and path[2:4] in (":", ":/")  # Colon + end of string, or colon + absolute path.
    ):
        path = path[1:]

    return path

# PIPREQPARSE: end from src/pip/_internal/utils/urls.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/models.py

class KeyBasedCompareMixin:
    """Provides comparison capabilities that is based on a key"""

    __slots__ = ["_compare_key", "_defining_class"]

    def __init__(self, key: Any, defining_class: Type["KeyBasedCompareMixin"]) -> None:
        self._compare_key = key
        self._defining_class = defining_class

    def __hash__(self) -> int:
        return hash(self._compare_key)

    def __lt__(self, other: Any) -> bool:
        return self._compare(other, operator.__lt__)

    def __le__(self, other: Any) -> bool:
        return self._compare(other, operator.__le__)

    def __gt__(self, other: Any) -> bool:
        return self._compare(other, operator.__gt__)

    def __ge__(self, other: Any) -> bool:
        return self._compare(other, operator.__ge__)

    def __eq__(self, other: Any) -> bool:
        return self._compare(other, operator.__eq__)

    def _compare(self, other: Any, method: Callable[[Any, Any], bool]) -> bool:
        if not isinstance(other, self._defining_class):
            return NotImplemented

        return method(self._compare_key, other._compare_key)

# PIPREQPARSE: end from src/pip/_internal/utils/models.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/packaging.py

NormalizedExtra = NewType("NormalizedExtra", str)


def safe_extra(extra: str) -> NormalizedExtra:
    """Convert an arbitrary string to a standard 'extra' name

    Any runs of non-alphanumeric characters are replaced with a single '_',
    and the result is always lowercased.

    This function is duplicated from ``pkg_resources``. Note that this is not
    the same to either ``canonicalize_name`` or ``_egg_link_name``.
    """
    return cast(NormalizedExtra, re.sub("[^A-Za-z0-9.-]+", "_", extra).lower())

# PIPREQPARSE: end from src/pip/_internal/utils/packaging.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/models/link.py

_SUPPORTED_HASHES = ("sha1", "sha224", "sha384", "sha256", "sha512", "md5")


class Link(KeyBasedCompareMixin):
    """Represents a parsed link from a Package Index's simple URL"""

    __slots__ = [
        "_parsed_url",
        "_url",
    ]

    def __init__(
        self,
        url: str,
    ) -> None:
        """
        :param url: url of the resource pointed to (href of the link)
        """

        self._parsed_url = urllib.parse.urlsplit(url)
        # Store the url as a private attribute to prevent accidentally
        # trying to set a new value.
        self._url = url and url.strip() or url
        super().__init__(key=url, defining_class=Link)

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        return f"<Link {self}>"

    @property
    def url(self) -> str:
        return self._url

    @property
    def filename(self) -> str:
        path = self.path.rstrip("/")
        name = posixpath.basename(path)
        if not name:
            # Make sure we don't leak auth information if the netloc
            # includes a username and password.
            netloc, _user_pass = split_auth_from_netloc(self.netloc)
            return netloc

        name = urllib.parse.unquote(name)
        assert name, f"URL {self._url!r} produced no filename"
        return name

    @property
    def file_path(self) -> str:
        return url_to_path(self.url)

    @property
    def scheme(self) -> str:
        return self._parsed_url.scheme

    @property
    def netloc(self) -> str:
        """
        This can contain auth information.
        """
        return self._parsed_url.netloc

    @property
    def path(self) -> str:
        return urllib.parse.unquote(self._parsed_url.path)

    def splitext(self) -> Tuple[str, str]:
        return splitext(posixpath.basename(self.path.rstrip("/")))

    @property
    def ext(self) -> str:
        return self.splitext()[1]

    @property
    def url_without_fragment(self) -> str:
        scheme, netloc, path, query, _fragment = self._parsed_url
        return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))

    _egg_fragment_re = re.compile(r"[#&]egg=([^&]*)")

    @property
    def egg_fragment(self) -> Optional[str]:
        match = self._egg_fragment_re.search(self._url)
        if not match:
            return None
        return match.group(1)

    _subdirectory_fragment_re = re.compile(r"[#&]subdirectory=([^&]*)")

    @property
    def subdirectory_fragment(self) -> Optional[str]:
        match = self._subdirectory_fragment_re.search(self._url)
        if not match:
            return None
        return match.group(1)

    _hash_re = re.compile(
        r"({choices})=([a-f0-9]+)".format(choices="|".join(_SUPPORTED_HASHES))
    )

    @property
    def hash(self) -> Optional[str]:
        match = self._hash_re.search(self._url)
        if match:
            return match.group(2)
        return None

    @property
    def hash_name(self) -> Optional[str]:
        match = self._hash_re.search(self._url)
        if match:
            return match.group(1)
        return None

    @property
    def show_url(self) -> str:
        return posixpath.basename(self._url.split("#", 1)[0].split("?", 1)[0])

    @property
    def is_file(self) -> bool:
        return self.scheme == "file"

    @property
    def is_wheel(self) -> bool:
        return self.ext == WHEEL_EXTENSION

    @property
    def is_vcs(self) -> bool:
        return self.scheme in vcs_all_schemes

    @property
    def has_hash(self) -> bool:
        return self.hash_name is not None


class _CleanResult(NamedTuple):
    """Convert link for equivalency check.

    This is used in the resolver to check whether two URL-specified requirements
    likely point to the same distribution and can be considered equivalent. This
    equivalency logic avoids comparing URLs literally, which can be too strict
    (e.g. "a=1&b=2" vs "b=2&a=1") and produce conflicts unexpecting to users.

    Currently this does three things:

    1. Drop the basic auth part. This is technically wrong since a server can
       serve different content based on auth, but if it does that, it is even
       impossible to guarantee two URLs without auth are equivalent, since
       the user can input different auth information when prompted. So the
       practical solution is to assume the auth doesn't affect the response.
    2. Parse the query to avoid the ordering issue. Note that ordering under the
       same key in the query are NOT cleaned; i.e. "a=1&a=2" and "a=2&a=1" are
       still considered different.
    3. Explicitly drop most of the fragment part, except ``subdirectory=`` and
       hash values, since it should have no impact the downloaded content. Note
       that this drops the "egg=" part historically used to denote the requested
       project (and extras), which is wrong in the strictest sense, but too many
       people are supplying it inconsistently to cause superfluous resolution
       conflicts, so we choose to also ignore them.
    """

    parsed: urllib.parse.SplitResult
    query: Dict[str, List[str]]
    subdirectory: str
    hashes: Dict[str, str]


def _clean_link(link: Link) -> _CleanResult:
    parsed = link._parsed_url
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    # According to RFC 8089, an empty host in file: means localhost.
    if parsed.scheme == "file" and not netloc:
        netloc = "localhost"
    fragment = urllib.parse.parse_qs(parsed.fragment)
    if "egg" in fragment:
        logger.debug("Ignoring egg= fragment in %s", link)
    try:
        # If there are multiple subdirectory values, use the first one.
        # This matches the behavior of Link.subdirectory_fragment.
        subdirectory = fragment["subdirectory"][0]
    except (IndexError, KeyError):
        subdirectory = ""
    # If there are multiple hash values under the same algorithm, use the
    # first one. This matches the behavior of Link.hash_value.
    hashes = {k: fragment[k][0] for k in _SUPPORTED_HASHES if k in fragment}
    return _CleanResult(
        parsed=parsed._replace(netloc=netloc, query="", fragment=""),
        query=urllib.parse.parse_qs(parsed.query),
        subdirectory=subdirectory,
        hashes=hashes,
    )


@functools.lru_cache(maxsize=None)
def links_equivalent(link1: Link, link2: Link) -> bool:
    return _clean_link(link1) == _clean_link(link2)

# PIPREQPARSE: end from src/pip/_internal/models/link.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/req/req_install.py


class InstallRequirement(
    RequirementLineMixin,
    ToDictMixin
):
    """
    Represents a pip requirement either directly installable or a link where to
    fetch the relevant requirement.
    """

    def __init__(
        self,
        req: Optional[Requirement],
        requirement_line: RequirementLine,
        link: Optional[Link] = None,
        marker: Optional[Marker] = None,
        install_options: Optional[List[str]] = None,
        global_options: Optional[List[str]] = None,
        hash_options: Optional[List[str]] = None,
        is_constraint: bool = False,
        extras: Collection[str] = (),
        invalid_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize a new pip requirement
        
        - ``req`` is a packaging Requirement object that may be None
        - ``requirement_line`` is the original line this requirement was found
        - ``link`` is a Link object provided when the requirement is a path or URL
        - ``marker`` is a packaging Marker object.
          This is provided when a marker is used and there is no ``req`` Requirement.
        - ``install_options``, ``global_options`` and ``hash_options`` are the
          CLI-style pip options for this specifc requirement.
        - ``is_constraint`` is True if this requirement came from loading a
           nested ``-c/--constraint`` file.
        - ``extras`` is a list of [extra] strings for this package.
           This is provided when extras are used and there is no ``req`` Requirement.
        - ``invalid_options`` are global pip options that are mistakenly set at the line-level.
           This is an error.
        """
        assert req is None or isinstance(req, Requirement), req
        self.req = req
        self.requirement_line = requirement_line
        self.is_constraint = is_constraint

        if req and req.url:
            # PEP 440/508 URL requirement
            link = Link(req.url)
        self.link = link

        if extras:
            self.extras = extras
        elif req:
            self.extras = {safe_extra(extra) for extra in req.extras}
        else:
            self.extras = set()

        if marker is None and req:
            marker = req.marker
        self.marker = marker

        # Supplied options
        self.install_options = install_options or []
        self.global_options = global_options or []
        self.hash_options = hash_options or []
        self.invalid_options = invalid_options or {}

    def __str__(self) -> str:
        if self.req:
            s = str(self.req)
            if self.link:
                s += " from {}".format(self.link.url)
        elif self.link:
            s = self.link.url
        else:
            s = "<{self.__class__.__name__}>"
        s += f" (from {self.requirement_line})"
        return s

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: req={self.req!r}, "
            f"link={self.link!r}\n"
            f" (from {self.requirement_line})"
            ">"
        )

    @property
    def name(self) -> Optional[str]:
        return self.req and self.req.name or None

    @property
    def specifier(self) -> SpecifierSet:
        return self.req and self.req.specifier or None

    @property
    def is_pinned(self) -> bool:
        """Return whether I am pinned to an exact version.

        For example, some-package==1.2 is pinned; some-package>1.2 is not.
        """
        specifiers = self.specifier
        return specifiers and len(specifiers) == 1 and next(iter(specifiers)).operator in {"==", "==="}

    def match_marker(self, extras_requested: Optional[Iterable[str]] = None) -> bool:
        if not extras_requested:
            # Provide an extra to safely evaluate the marker
            # without matching any extra
            extras_requested = ("",)
        if self.marker is not None:
            return any(
                self.marker.evaluate({"extra": extra}) for extra in extras_requested
            )
        else:
            return True

    @property
    def is_wheel(self) -> bool:
        return (
            (self.link and self.link.is_wheel) 
            or (self.name and self.name.endswith(WHEEL_EXTENSION))
        )


# PIPREQPARSE: end from src/pip/_internal/req/req_install.py
################################################################################

    @property
    def get_pinned_version(self) -> str:
        """
        Return a pinned version or None.
        """
        if self.is_pinned:
            # we have only one spec which is pinned. Gte the version as string
            return str(list(self.specifier)[0].version)

    @property
    def is_editable(self) -> bool:
        return isinstance(self, EditableRequirement)

    @property
    def is_archive(self) -> bool:
        return is_archive_file(self.name) or (
            self.link and is_archive_file(self.link.url)
        )

    @property
    def is_url(self) -> bool:
        return self.link and is_url(self.link.url)

    @property
    def is_vcs_url(self) -> bool:
        return self.link and self.link.is_vcs

    @property
    def is_local_path(self) -> bool:
        return (
            (self.name and self.name.startswith("."))
            or (self.link and _looks_like_path(self.link.url))
        )

    @property
    def is_name_at_url(self) -> bool:
        return is_name_at_url_requirement(self.line)

    @property
    def has_egg_fragment(self) -> bool:
        return self.line and "#egg" in self.line

    def dumps_egg_fragment(self) -> str:
        if not self.has_egg_fragment:
            return ""
        if self.name:
            egg_frag = f"#egg={self.name}"
            egg_frag += self.dumps_extras()
            egg_frag += self.dumps_specifier()
            egg_frag += self.dumps_marker()
            return egg_frag
        else:
            return ""

    def dumps_name(self) -> str:
        return self.name or ""

    def dumps_specifier(self) -> str:
        return self.specifier and ",".join(sorted_specifiers(self.specifier)) or ""

    def dumps_extras(self) -> str:
        if not self.extras:
            return ""
        extras = ",".join(sorted(self.extras or []))
        return f"[{extras}]"

    def dumps_marker(self) -> str:
        return self.marker and f"; {self.marker}" or ""

    def dumps_url(self) -> str:
        return self.link and str(self.link.url) or ""

    def to_dict(self, include_filename=False) -> Dict:
        """
        Return a mapping of plain Python type representing this
        InstallRequirement.
        """
        return dict(
            name=self.name,
            specifier=sorted_specifiers(self.specifier),
            is_editable=self.is_editable,
            is_pinned=self.req and self.is_pinned or False,
            requirement_line=self.requirement_line.to_dict(include_filename),
            link=self.link and self.link.url or None,
            marker=self.marker and str(self.marker) or None,
            install_options=self.install_options or [],
            global_options=self.global_options or [],
            hash_options=self.hash_options or [],
            is_constraint=self.is_constraint,
            extras=self.extras and sorted(self.extras) or [],
            invalid_options=self.invalid_options or {},
            is_archive=self.is_archive,
            is_wheel=self.is_wheel,
            is_url=self.is_url,
            is_vcs_url=self.is_vcs_url,
            is_name_at_url=self.is_name_at_url,
            is_local_path=self.is_local_path,
            has_egg_fragment=self.has_egg_fragment,
        )

    def dumps(self, with_name=True) -> str:
        """
        Return a single string line representing this InstallRequirement
        suitable to use in a requirements file.
        Optionally exclude the name if ``with_name`` is False for simple
        requirements
        """
        parts = []

        if self.is_name_at_url:
            # we have two cases: a plain URL and a VCS URL
            name_at = self.dumps_name() + self.dumps_extras() + "@"
            if self.link:
                if not self.link.url.startswith(name_at):
                    parts.append(name_at)
                parts.append(self.dumps_url())

            if self.marker:
                parts.append(" ")
                parts.append(self.dumps_marker())

        elif self.is_vcs_url:
            ur = self.dumps_url()
            parts.append(ur)
            ef = self.dumps_egg_fragment()
            if ef and ef not in ur:
                parts.append(ef)

        elif self.is_url:
            ur = self.dumps_url()
            parts.append(ur)
            ef = self.dumps_egg_fragment()
            if ef and ef not in ur:
                parts.append(ef)

        elif self.is_local_path:
            if self.link:
                parts.append(self.dumps_url())
            else:
                parts.append(self.dumps_name())

            if self.extras:
                parts.append(" ")
                parts.append(self.dumps_extras())

            if self.marker:
                parts.append(" ")
                parts.append(self.dumps_marker())

        elif (self.is_wheel or self.is_archive):
            if self.link:
                parts.append(self.dumps_url())
            else:
                parts.append(self.dumps_name())
            if self.extras:
                parts.append(" ")
                parts.append(self.dumps_extras())
            if self.marker:
                if not self.extras:
                    parts.append(" ")
                parts.append(self.dumps_marker())

        else:
            if with_name:
                parts.append(self.dumps_name())
            parts.append(self.dumps_extras())
            parts.append(self.dumps_specifier())
            parts.append(self.dumps_marker())

        # options come last

        if self.install_options:
            parts.append(" ")
            parts.append(dumps_requirement_options(
                options=self.install_options, 
                opt_string="--install-option",
                quote_value=True,
            ))

        if self.global_options:
            parts.append(" ")
            parts.append(dumps_requirement_options(
                options=self.global_options, 
                opt_string="--global-option",
            ))

        if self.hash_options:
            parts.append(" ")
            parts.append(
                dumps_requirement_options(
                    options=self.hash_options, 
                    opt_string="--hash",
                    one_per_line=True,
                ))

        return "".join(parts)


def _as_version(version: Union[str, LegacyVersion, Version]
) -> Union[LegacyVersion, Version]:
    """
    Return a packaging Version-like object suitable for sorting
    """
    if isinstance(version, (LegacyVersion, Version)):
        return version
    else:
        # drop possible trailing star that make this a non version-like string
        version = version.rstrip(".*")
        return parse(version)


def sorted_specifiers(specifier: SpecifierSet) -> List[str]:
    """
    Return a list of sorted Specificier from a SpecifierSet, each converted to a
    string.
    The sort is done by version, then operator
    """
    by_version =  lambda spec: (_as_version(spec.version), spec.version, spec.operator)
    return [str(s) for s in sorted(specifier or [], key=by_version)]


class EditableRequirement(InstallRequirement):
    """
    Represents a pip editable requirement.
    These are special because they are unique to pip (e.g., they cannot be
    specified only as packaging.requriements.Requirement.
    They track:
    - a path/ or a path/subpath to a dir with an optional [extra]. 
    - a VCS URL with a package name i.e., the "#egg=<name>" fragment
      Using "#egg=<name>[extras]<specifier>" is accepted too, but version
      specifier and extras will be ignored and whatever is pointed to by the VCS
      will be used instead:
       -e git+https://github.com/bastikr/boolean.py.git#egg=boolean.py[foo]==3.8
      is the same as:
       -e git+https://github.com/bastikr/boolean.py.git#egg=boolean.py
    
    As a recap for VCS URL in #egg=<name> the <name> can be a packaging
    Requirement-compatible string, but only name is kept and used.
    Trailing marker is an error
    """

    def dumps(self):
        """
        Return a single string line representing this requirement
        suitable to use in a requirements file.
        """
        parts = ["--editable "]

        if self.link:
            link = self.link.url
        elif self.req and self.req.url:
            link = self.req.url

        parts.append(link)

        if _looks_like_path(link):
            extras = self.dumps_extras()
            if extras not in link:
                parts.append(self.dumps_extras())
            parts.append(self.dumps_marker())

        elif is_url(self.link and self.link.url):
            # we can only get fragments on URLs
            egg_frag = f"#egg={self.name}" if self.name else ""
            extras = self.dumps_extras()
            if extras not in link:
                egg_frag += extras

            egg_frag += self.dumps_specifier()
            egg_frag += self.dumps_marker()

            if egg_frag and egg_frag not in link:
                parts.append(egg_frag)

        return "".join(parts)


################################################################################
# PIPREQPARSE: from src/pip/_internal/vcs/versioncontrol.py

vcs_all_schemes = [
    'bzr+http', 'bzr+https', 'bzr+ssh', 'bzr+sftp', 'bzr+ftp', 'bzr+lp', 'bzr+file', 
    'git+http', 'git+https', 'git+ssh', 'git+git', 'git+file', 
    'hg+file', 'hg+http', 'hg+https', 'hg+ssh', 'hg+static-http', 
    'svn+ssh', 'svn+http', 'svn+https', 'svn+svn', 'svn+file',
]

vcs = ['ssh', 'git', 'hg', 'bzr', 'sftp', 'svn']


def is_url(name: str) -> bool:
    """
    Return true if the name looks like a URL.

    For example:
    >>> is_url("name@http://foo.com")
    False
    >>> is_url("git+http://foo.com")
    True
    >>> is_url("ftp://foo.com")
    True
    >>> is_url("file://foo.com")
    True
    >>> is_url("git://foo.com")
    False
    >>> is_url("www.foo.com")
    False
    """
    scheme = get_url_scheme(name)
    if scheme is None:
        return False
    return scheme in ["http", "https", "file", "ftp"] + vcs_all_schemes

# PIPREQPARSE: end from src/pip/_internal/vcs/versioncontrol.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/misc.py

NetlocTuple = Tuple[str, Tuple[Optional[str], Optional[str]]]


def read_chunks(file: BinaryIO, size: int = io.DEFAULT_BUFFER_SIZE) -> Iterator[bytes]:
    """Yield pieces of data from a file-like object until EOF."""
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk


def splitext(path: str) -> Tuple[str, str]:
    """Like os.path.splitext, but take off .tar too"""
    base, ext = posixpath.splitext(path)
    if base.lower().endswith(".tar"):
        ext = base[-4:] + ext
        base = base[:-4]
    return base, ext


def split_auth_from_netloc(netloc: str) -> NetlocTuple:
    """
    Parse out and remove the auth information from a netloc.

    Returns: (netloc, (username, password)).
    """
    if "@" not in netloc:
        return netloc, (None, None)

    # Split from the right because that's how urllib.parse.urlsplit()
    # behaves if more than one @ is present (which can be checked using
    # the password attribute of urlsplit()'s return value).
    auth, netloc = netloc.rsplit("@", 1)
    pw: Optional[str] = None
    if ":" in auth:
        # Split from the left because that's how urllib.parse.urlsplit()
        # behaves if more than one : is present (which again can be checked
        # using the password attribute of the return value)
        user, pw = auth.split(":", 1)
    else:
        user, pw = auth, None

    user = urllib.parse.unquote(user)
    if pw is not None:
        pw = urllib.parse.unquote(pw)

    return netloc, (user, pw)

# PIPREQPARSE: end from src/pip/_internal/utils/misc.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/utils/filetypes.py

WHEEL_EXTENSION = ".whl"
BZ2_EXTENSIONS: Tuple[str, ...] = (".tar.bz2", ".tbz")
XZ_EXTENSIONS: Tuple[str, ...] = (
    ".tar.xz",
    ".txz",
    ".tlz",
    ".tar.lz",
    ".tar.lzma",
)
ZIP_EXTENSIONS: Tuple[str, ...] = (".zip", WHEEL_EXTENSION)
TAR_EXTENSIONS: Tuple[str, ...] = (".tar.gz", ".tgz", ".tar")
ARCHIVE_EXTENSIONS = ZIP_EXTENSIONS + BZ2_EXTENSIONS + TAR_EXTENSIONS + XZ_EXTENSIONS


def is_archive_file(name: str) -> bool:
    """
    Return True if `name` is a considered as an archive file.
    For example:
    >>> assert is_archive_file("foo.whl")
    >>> assert is_archive_file("foo.zip")
    >>> assert is_archive_file("foo.tar.gz")
    >>> assert is_archive_file("foo.tar")
    >>> assert not is_archive_file("foo.tar.baz")
    """
    if not name:
        return False
    ext = splitext(name)[1].lower()
    if ext in ARCHIVE_EXTENSIONS:
        return True
    return False

# PIPREQPARSE: end from src/pip/_internal/utils/filetypes.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/req/constructors.py

logger = logging.getLogger(__name__)
operators = Specifier._operators.keys()


def _strip_extras(path: str) -> Tuple[str, Optional[str]]:
    m = re.match(r"^(.+)(\[[^\]]+\])$", path)
    extras = None
    if m:
        path_no_extras = m.group(1)
        extras = m.group(2)
    else:
        path_no_extras = path

    return path_no_extras, extras


def convert_extras(extras: Optional[str]) -> Set[str]:
    if not extras:
        return set()
    return Requirement("placeholder" + extras.lower()).extras


def parse_editable(editable_req: str) -> Tuple[Optional[str], str, Set[str]]:
    """Parses an editable requirement into:
        - a requirement name
        - an URL
        - extras

    Accepted requirements:
        svn+http://blahblah@rev#egg=Foobar[baz]
        .[some_extra]
    """

    url = editable_req

    # If a file path is specified with extras, strip off the extras.
    url_no_extras, extras = _strip_extras(url)

    unel = url_no_extras.lower()
    if (
        unel.startswith(("file:", ".",))
        or _looks_like_path(unel)
        or _is_plain_name(unel)
    ):
        package_name = Link(url_no_extras).egg_fragment
        if extras:
            return (
                package_name,
                url_no_extras,
                Requirement("placeholder" + extras.lower()).extras,
            )
        else:
            return package_name, url_no_extras, set()

    for version_control in vcs:
        if url.lower().startswith(f"{version_control}:"):
            url = f"{version_control}+{url}"
            break

    link = Link(url)

    is_path_like = _looks_like_path(url) or _is_plain_name(url)

    if not (link.is_vcs or is_path_like):
        backends = ", ".join(vcs_all_schemes)
        raise InstallationError(
            f"{editable_req} is not a valid editable requirement. "
            f"It should either be a path to a local project or a VCS URL "
            f"(beginning with {backends})."
        )

    package_name = link.egg_fragment
    if not package_name and not is_path_like:
        raise InstallationError(
            "Could not detect requirement name for '{}', please specify one "
            "with #egg=your_package_name".format(editable_req)
        )
    return package_name, url, set()


class RequirementParts:
    def __init__(
        self,
        requirement: Optional[Requirement],
        link: Optional[Link],
        marker: Optional[Marker],
        extras: Set[str],
    ):
        self.requirement = requirement
        self.link = link
        self.marker = marker
        self.extras = extras

    def __repr__(self):
        return (
            f"RequirementParts(requirement={self.requirement!r}, "
            f"link={self.link!r}, marker={self.marker!r}, "
            f"extras={self.extras!r})"
        )

def parse_reqparts_from_editable(editable_req: str) -> RequirementParts:

    name, url, extras_override = parse_editable(editable_req)

    req = None
    if name is not None:
        try:
            req = Requirement(name)
        except InvalidRequirement as e:
            raise InstallationError(f"Invalid requirement: '{name}': {e}")

    return RequirementParts(
        requirement=req, 
        link=Link(url), 
        marker=None, 
        extras=extras_override,
    )


# ---- The actual constructors follow ----


def build_editable_req(
    editable_req: str,
    requirement_line: Optional[RequirementLine] = None,  # optional for tests only
    options: Optional[Dict[str, Any]] = None,
    invalid_options: Optional[Dict[str, Any]] = None,
    is_constraint: bool = False,
) -> EditableRequirement:

    parts = parse_reqparts_from_editable(editable_req)

    return EditableRequirement(
        req=parts.requirement,
        requirement_line=requirement_line,
        link=parts.link,
        is_constraint=is_constraint,
        install_options=options.get("install_options", []) if options else [],
        global_options=options.get("global_options", []) if options else [],
        hash_options=options.get("hashes", []) if options else [],
        extras=parts.extras,
        invalid_options=invalid_options,
    )


# Return True if the name is a made only of alphanum, dot - and _ characters
_is_plain_name = re.compile(r"[\w\-\.\_]+").match


def _looks_like_path(name: str) -> bool:
    """Checks whether the string ``name``  "looks like" a path on the filesystem.

    This does not check whether the target actually exists, only judge from the
    appearance.

    Returns true if any of the following conditions is true:
    * a path separator is found (either os.path.sep or os.path.altsep);
    * a dot is found (which represents the current directory).
    """
    if not name:
        return False
    if os.path.sep in name:
        return True
    if os.path.altsep is not None and os.path.altsep in name:
        return True
    if name.startswith("."):
        return True
    return False


class NameAtUrl(NamedTuple):
    spec: str
    url: str


def split_as_name_at_url(reqstr: str) -> NamedTuple:
    """
    Split ``reqstr`` and return a NameAtUrl tuple or None if this is not
    a PEP-508-like requirement such as:
    foo @ https://fooo.com/bar.tgz

    For example::
    >>> assert split_as_name_at_url("foo") == None
    >>> assert split_as_name_at_url("") is None

    >>> split = split_as_name_at_url("foo@https://example.com")
    >>> expected = NameAtUrl(spec='foo', url='https://example.com')
    >>> assert split == expected, split

    >>> split = split_as_name_at_url("fo/o@https://example.com")
    >>> assert split is None

    >>> split = split_as_name_at_url("foo@example.com")
    >>> assert split is None

    >>> split = split_as_name_at_url("foo@git+https://example.com")
    >>> expected = NameAtUrl(spec='foo', url='git+https://example.com')
    >>> assert split == expected, split
    """
    if not reqstr:
        return
    if "@" in reqstr:
        # If the path contains '@' and the part before it does not look
        # like a path, try to treat it as a PEP 508 URL req.
        spec, _, url = reqstr.partition("@")
        spec = spec.strip()
        url = url.strip()
        if not _looks_like_path(spec) and is_url(url):
            return NameAtUrl(spec, url)


def is_name_at_url_requirement(reqstr: str) -> bool:
    """
    Return True if this requirement is in the "name@url" format.
    For example:
    >>> is_name_at_url_requirement("foo@https://foo.com")
    True
    >>> is_name_at_url_requirement("foo@ https://foo.com")
    True
    >>> is_name_at_url_requirement("foo @ https://foo.com")
    True
    """
    return bool(reqstr and split_as_name_at_url(reqstr))


def _get_url_from_path(path: str, name: str) -> Optional[str]:
    """
    First, it checks whether a provided path looks like a path. If it
    is, returns the path.

    Otherwise, check if the path is notan archive file (such as a .whl) or is a
    PEP 508 URL "name@url" requirement and return None
    """
    if not (path and name):
        return

    if _looks_like_path(name):
        return path

    if not is_archive_file(path):
        return None

    if is_name_at_url_requirement(name) or is_name_at_url_requirement(path):
        return None

    return path


def parse_reqparts_from_string(requirement_string: str) -> RequirementParts:
    """
    Return RequirementParts from a ``requirement_string``.
    Raise exceptions on error.
    """
    if is_url(requirement_string):
        marker_sep = "; "
    else:
        marker_sep = ";"

    if marker_sep in requirement_string:
        requirement_string, marker_as_string = requirement_string.split(marker_sep, 1)
        marker_as_string = marker_as_string.strip()
        if not marker_as_string:
            marker = None
        else:
            marker = Marker(marker_as_string)
    else:
        marker = None
    requirement_string_no_marker = requirement_string.strip()

    req_as_string = None
    path = requirement_string_no_marker
    link = None
    extras_as_string = None

    if is_url(requirement_string_no_marker):
        link = Link(requirement_string_no_marker)
    elif not is_name_at_url_requirement(requirement_string_no_marker):
        p, extras_as_string = _strip_extras(path)
        url = _get_url_from_path(p, requirement_string_no_marker)
        if url:
            link = Link(url)

    # it's a local file, dir, or url
    if link:
        # Handle relative file URLs
        if link.scheme == "file" and re.search(r"\.\./", link.url):
            link = Link(link.path)
        # wheel file
        if link.is_wheel:
            wheel = Wheel(link.filename)  # can raise InvalidWheelFilename
            req_as_string = f"{wheel.name}=={wheel.version}"
        else:
            # set the req to the egg fragment.  when it's not there, this
            # will become an 'unnamed' requirement
            req_as_string = link.egg_fragment

    # a requirement specifier that should be packaging-parsable.
    # this includes name@url
    else:
        req_as_string = requirement_string_no_marker

    extras = convert_extras(extras_as_string)

    def _parse_req_string(req_as_string: str) -> Requirement:
        rq = None
        try:
            rq = Requirement(req_as_string)
        except InvalidRequirement as e:
            if os.path.sep in req_as_string:
                add_msg = "It looks like a path."

            elif "=" in req_as_string and not any(
                op in req_as_string for op in operators
            ):
                add_msg = "= is not a valid operator. Did you mean == ?"

            else:
                add_msg = ""
            msg = f"Invalid requirement: {add_msg}: {e}"
            raise InstallationError(msg)
        else:
            # Deprecate extras after specifiers: "name>=1.0[extras]"
            # This currently works by accident because _strip_extras() parses
            # any extras in the end of the string and those are saved in
            # RequirementParts
            for spec in rq.specifier:
                spec_str = str(spec)
                if spec_str.endswith("]"):
                    msg = f"Unsupported extras after version '{spec_str}'."
                    raise InstallationError(msg)
        return rq

    if req_as_string is not None:
        req: Optional[Requirement] = _parse_req_string(req_as_string)
    else:
        req = None

    return RequirementParts(req, link, marker, extras)


def build_install_req(
    requirement_string: str,
    requirement_line: Optional[RequirementLine] = None, # optional only for testing
    options: Optional[Dict[str, Any]] = None,
    invalid_options: Optional[Dict[str, Any]] = None,
    is_constraint: bool=False,
) -> InstallRequirement:
    """Create an InstallRequirement from a requirement_string, which might be a
    requirement, directory containing 'setup.py', filename, or URL.

    :param requirement_line: An optional RequirementLine describing where the
        line is from, for logging purposes in case of an error.
    """
    parts = parse_reqparts_from_string(requirement_string=requirement_string)

    return InstallRequirement(
        req=parts.requirement,
        requirement_line=requirement_line,
        link=parts.link,
        marker=parts.marker,
        install_options=options.get("install_options", []) if options else [],
        global_options=options.get("global_options", []) if options else [],
        hash_options=options.get("hashes", []) if options else [],
        is_constraint=is_constraint,
        extras=parts.extras,
        invalid_options=invalid_options or {},
    )


def build_req_from_parsedreq(
    parsed_req: ParsedRequirement,
) -> InstallRequirement:

    requirement_string = parsed_req.requirement_string
    options = parsed_req.options
    invalid_options = parsed_req.invalid_options
    requirement_line = parsed_req.requirement_line
    is_constraint = parsed_req.is_constraint

    if parsed_req.is_editable:
        return build_editable_req(
            editable_req=requirement_string,
            requirement_line=requirement_line,
            options=options,
            is_constraint=is_constraint,
            invalid_options=invalid_options,
        )

    return build_install_req(
        requirement_string=requirement_string,
        requirement_line=requirement_line,
        options=options,
        is_constraint=is_constraint,
        invalid_options=invalid_options,
    )

# PIPREQPARSE: end from src/pip/_internal/req/constructors.py
################################################################################


################################################################################
# PIPREQPARSE: from src/pip/_internal/models/wheel.py

class Wheel:
    """A wheel file"""

    wheel_file_re = re.compile(
        r"""^(?P<namever>(?P<name>.+?)-(?P<ver>.*?))
        ((-(?P<build>\d[^-]*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)
        \.whl|\.dist-info)$""",
        re.VERBOSE,
    )

    def __init__(self, filename: str) -> None:
        """
        :raises InvalidWheelFilename: when the filename is invalid for a wheel
        """
        wheel_info = self.wheel_file_re.match(filename)
        if not wheel_info:
            raise InvalidWheelFilename(f"{filename} is not a valid wheel filename.")
        self.filename = filename
        self.name = wheel_info.group("name").replace("_", "-")
        # we'll assume "_" means "-" due to wheel naming scheme
        # (https://github.com/pypa/pip/issues/1150)
        self.version = wheel_info.group("ver").replace("_", "-")
        self.build_tag = wheel_info.group("build")
        self.pyversions = wheel_info.group("pyver").split(".")
        self.abis = wheel_info.group("abi").split(".")
        self.plats = wheel_info.group("plat").split(".")

        # All the tag combinations from this file
        self.file_tags = {
            Tag(x, y, z) for x in self.pyversions for y in self.abis for z in self.plats
        }

    def get_formatted_file_tags(self) -> List[str]:
        """Return the wheel's tags as a sorted list of strings."""
        return sorted(str(tag) for tag in self.file_tags)

    def support_index_min(self, tags: List[Tag]) -> int:
        """Return the lowest index that one of the wheel's file_tag combinations
        achieves in the given list of supported tags.

        For example, if there are 8 supported tags and one of the file tags
        is first in the list, then return 0.

        :param tags: the PEP 425 tags to check the wheel against, in order
            with most preferred first.

        :raises ValueError: If none of the wheel's file tags match one of
            the supported tags.
        """
        return min(tags.index(tag) for tag in self.file_tags if tag in tags)

    def find_most_preferred_tag(
        self, tags: List[Tag], tag_to_priority: Dict[Tag, int]
    ) -> int:
        """Return the priority of the most preferred tag that one of the wheel's file
        tag combinations achieves in the given list of supported tags using the given
        tag_to_priority mapping, where lower priorities are more-preferred.

        This is used in place of support_index_min in some cases in order to avoid
        an expensive linear scan of a large list of tags.

        :param tags: the PEP 425 tags to check the wheel against.
        :param tag_to_priority: a mapping from tag to priority of that tag, where
            lower is more preferred.

        :raises ValueError: If none of the wheel's file tags match one of
            the supported tags.
        """
        return min(
            tag_to_priority[tag] for tag in self.file_tags if tag in tag_to_priority
        )

    def supported(self, tags: Iterable[Tag]) -> bool:
        """Return whether the wheel is compatible with one of the given tags.

        :param tags: the PEP 425 tags to check the wheel against.
        """
        return not self.file_tags.isdisjoint(tags)

# PIPREQPARSE: end from src/pip/_internal/models/wheel.py
################################################################################
