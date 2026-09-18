import argparse
import ast
import os
import posixpath
import re
import string
import sys
import traceback
from collections import defaultdict
from typing import Any, Dict, Optional, Union
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import pathname2url, url2pathname

from pip_api._vendor import tomli
from pip_api._vendor.packaging import requirements, specifiers  # type: ignore
from pip_api.exceptions import PipError

parser = argparse.ArgumentParser()
parser.add_argument("req", nargs="*")
parser.add_argument("-r", "--requirement")
parser.add_argument("-e", "--editable")
# Consume index url params to avoid trying to treat them as packages.
parser.add_argument("-i", "--index-url")
parser.add_argument("--extra-index-url")
parser.add_argument("-f", "--find-links")
parser.add_argument("--hash", action="append", dest="hashes")
parser.add_argument("--trusted-host")

operators = specifiers.Specifier._operators.keys()

COMMENT_RE = re.compile(r"(^|\s)+#.*$")
VCS_SCHEMES = ["ssh", "git", "hg", "bzr", "sftp", "svn"]
WHEEL_EXTENSION = ".whl"
WHEEL_FILE_RE = re.compile(
    r"""^(?P<namever>(?P<name>.+?)-(?P<ver>.*?))
    ((-(?P<build>\d[^-]*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)
    \.whl|\.dist-info)$""",
    re.VERBOSE,
)
WINDOWS = sys.platform.startswith("win") or (sys.platform == "cli" and os.name == "nt")
# https://pip.pypa.io/en/stable/cli/pip_hash/
VALID_HASHES = {"sha256", "sha384", "sha512"}


class Link:
    def __init__(self, url):
        # url can be a UNC windows share
        if url.startswith("\\\\"):
            url = _path_to_url(url)

        self._parsed_url = urlsplit(url)
        # Store the url as a private attribute to prevent accidentally
        # trying to set a new value.
        self._url = url

    @property
    def url(self):
        return self._url

    @property
    def filename(self):
        path = self.path.rstrip("/")
        name = posixpath.basename(path)
        if not name:
            # Make sure we don't leak auth information if the netloc
            # includes a username and password.
            netloc, _ = _split_auth_from_netloc(self.netloc)
            return netloc

        name = unquote(name)
        assert name, f"URL {self._url!r} produced no filename"
        return name

    @property
    def file_path(self):
        return _url_to_path(self.url)

    @property
    def scheme(self):
        return self._parsed_url.scheme

    @property
    def netloc(self):
        return self._parsed_url.netloc

    @property
    def path(self):
        return unquote(self._parsed_url.path)

    def splitext(self):
        return _splitext(posixpath.basename(self.path.rstrip("/")))

    @property
    def ext(self):
        return self.splitext()[1]

    @property
    def show_url(self):
        return posixpath.basename(self._url.split("#", 1)[0].split("?", 1)[0])

    @property
    def is_wheel(self):
        return self.ext == WHEEL_EXTENSION

    @property
    def is_vcs(self):
        return self.scheme in VCS_SCHEMES


def _splitext(path):
    base, ext = posixpath.splitext(path)
    if base.lower().endswith(".tar"):
        ext = base[-4:] + ext
        base = base[:-4]
    return base, ext


def _split_auth_from_netloc(netloc):
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

    user = unquote(user)
    if pw is not None:
        pw = unquote(pw)

    return netloc, (user, pw)


def _url_to_path(url):
    assert url.startswith(
        "file:"
    ), f"You can only turn file: urls into filenames (not {url!r})"

    _, netloc, path, _, _ = urlsplit(url)

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

    path = url2pathname(netloc + path)

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


class Requirement(requirements.Requirement):
    def __init__(self, *args, **kwargs):
        self.hashes = kwargs.pop("hashes", None)
        self.editable = kwargs.pop("editable", False)
        self.filename = kwargs.pop("filename")
        self.lineno = kwargs.pop("lineno")

        super().__init__(*args, **kwargs)


class UnparsedRequirement(object):
    def __init__(self, name, msg, filename, lineno):
        self.name = name
        self.msg = msg
        self.exception = msg
        self.filename = filename
        self.lineno = lineno

    def __str__(self):
        return self.msg


def _read_file(filename):
    with open(filename) as f:
        return f.readlines()


def _check_invalid_requirement(req):
    if os.path.sep in req:
        add_msg = "It looks like a path."
        if os.path.exists(req):
            add_msg += " It does exist."
        else:
            add_msg += " File '%s' does not exist." % (req)
    elif "=" in req and not any(op in req for op in operators):
        add_msg = "= is not a valid operator. Did you mean == ?"
    else:
        add_msg = traceback.format_exc()
    raise PipError("Invalid requirement: '%s'\n%s" % (req, add_msg))


def _strip_extras(path):
    m = re.match(r"^(.+)(\[[^\]]+\])$", path)
    extras = None
    if m:
        path_no_extras = m.group(1)
        extras = m.group(2)
    else:
        path_no_extras = path

    return path_no_extras, extras


def _egg_fragment(url):
    _egg_fragment_re = re.compile(r"[#&]egg=([^&]*)")
    match = _egg_fragment_re.search(url)
    if not match:
        return None
    return match.group(1)


def _path_to_url(path):
    path = os.path.normpath(os.path.abspath(path))
    url = urljoin("file:", pathname2url(path))
    return url


def _parse_local_package_name(path):
    # Determine the package name from a local directory
    pyproject_toml = os.path.join(path, "pyproject.toml")
    setup_py = os.path.join(path, "setup.py")
    has_pyproject = os.path.isfile(pyproject_toml)
    has_setup = os.path.isfile(setup_py)

    if not has_pyproject and not has_setup:
        raise PipError(
            f"{path} does not appear to be a Python project: "
            f"neither 'setup.py' nor 'pyproject.toml' found."
        )

    # Prefer the name in `pyproject.toml`
    if has_pyproject:
        with open(pyproject_toml, encoding="utf-8") as f:
            pp_toml = tomli.loads(f.read())
            name = pp_toml.get("project", {}).get("name")
            if name is not None:
                return name

    # Fall back on tokenizing setup.py and walk the syntax tree to find the
    # package name
    try:
        with open(os.path.join(path, "setup.py")) as f:
            tree = ast.parse(f.read())
        setup_kwargs = [
            expr.value.keywords
            for expr in tree.body
            if isinstance(expr, ast.Expr)
            and isinstance(expr.value, ast.Call)
            and expr.value.func.id == "setup"
        ][0]
        value = [kw.value for kw in setup_kwargs if kw.arg == "name"][0]
        return value.s
    except (IndexError, AttributeError, IOError, OSError):
        raise PipError(
            "Directory %r is not installable. "
            "Could not parse package name from 'setup.py'." % path
        )


def _parse_editable(editable_req):
    url = editable_req

    # If a file path is specified with extras, strip off the extras.
    url_no_extras, extras = _strip_extras(url)
    original_url = url_no_extras

    if os.path.isdir(original_url):
        pyproject_path = os.path.join(original_url, "pyproject.toml")
        setup_path = os.path.join(original_url, "setup.py")
        if not any(os.path.exists(p) for p in (pyproject_path, setup_path)):
            raise PipError(
                "Directory %r is not installable. No 'setup.py' or 'pyproject.toml' found."
                % original_url
            )
        # Treating it as code that has already been checked out
        url_no_extras = _path_to_url(url_no_extras)

    if url_no_extras.lower().startswith("file:"):
        # NOTE: url_no_extras may contain escaped characters here, meaning that
        # it may no longer be a literal package path. So we pass original_url.
        return _parse_local_package_name(original_url), url_no_extras

    if "+" not in url:
        raise PipError(
            "%s should either be a path to a local project or a VCS url "
            "beginning with svn+, git+, hg+, or bzr+" % editable_req
        )

    package_name = _egg_fragment(url)
    if not package_name:
        raise PipError(
            "Could not detect requirement name for '%s', please specify one "
            "with #egg=your_package_name" % editable_req
        )

    return package_name, url


def _filterfalse(predicate, iterable):
    if predicate is None:
        predicate = bool
    for x in iterable:
        if not predicate(x):
            yield x


def _skip_regex(lines_enum, options):
    skip_regex = options.skip_requirements_regex if options else None
    if skip_regex:
        pattern = re.compile(skip_regex)
        lines_enum = _filterfalse(lambda e: pattern.search(e[1]), lines_enum)
    return lines_enum


def _ignore_comments(lines_enum):
    """
    Strips comments and filter empty lines.
    """
    for line_number, line in lines_enum:
        line = COMMENT_RE.sub("", line)
        line = line.strip()
        if line:
            yield line_number, line


def _get_url_scheme(url):
    if ":" not in url:
        return None
    return url.split(":", 1)[0].lower()


def _is_url(name):
    scheme = _get_url_scheme(name)
    if scheme is None:
        return False
    return scheme in ["http", "https", "file", "ftp"] + VCS_SCHEMES


def _looks_like_path(name):
    if os.path.sep in name:
        return True
    if os.path.altsep is not None and os.path.altsep in name:
        return True
    if name.startswith("."):
        return True
    return False


def _is_installable_dir(path):
    if not os.path.isdir(path):
        return False
    if os.path.isfile(os.path.join(path, "pyproject.toml")):
        return True
    if os.path.isfile(os.path.join(path, "setup.py")):
        return True
    return False


def _is_archive_file(name):
    ext = _splitext(name)[1].lower()
    if ext in (
        # ZIP extensions
        ".zip",
        WHEEL_EXTENSION,
        # BZ2 extensions
        ".tar.bz2",
        ".tbz",
        # TAR extensions
        ".tar.gz",
        ".tgz",
        ".tar",
        # XZ extensions
        ".tar.xz",
        ".txz",
        ".tlz",
        ".tar.lz",
        ".tar.lzma",
    ):
        return True
    return False


def _get_url_from_path(path, name):
    if _looks_like_path(name) and os.path.isdir(path):
        if _is_installable_dir(path):
            return _path_to_url(path)
        # TODO: The is_installable_dir test here might not be necessary
        #       now that it is done in load_pyproject_toml too.
        raise PipError(
            f"Directory {name!r} is not installable. Neither 'setup.py' "
            "nor 'pyproject.toml' found."
        )
    if not _is_archive_file(path):
        return None
    if os.path.isfile(path):
        return _path_to_url(path)
    urlreq_parts = name.split("@", 1)
    if len(urlreq_parts) >= 2 and not _looks_like_path(urlreq_parts[0]):
        # If the path contains '@' and the part before it does not look
        # like a path, try to treat it as a PEP 440 URL req instead.
        return None
    return _path_to_url(path)


def _parse_requirement_url(req_str):
    original_req_str = req_str

    # Some requirements lines begin with a `git+` or similar to indicate the VCS. If this is the
    # case, remove this before proceeding any further.
    for v in VCS_SCHEMES:
        if req_str.startswith(v + "+"):
            req_str = req_str[len(v) + 1 :]
            break

    # Strip out the marker temporarily while we parse out any potential URLs
    marker_sep = "; " if _is_url(req_str) else ";"
    marker_str = None
    link = None
    if ";" in req_str:
        req_str, marker_str = req_str.split(marker_sep, 1)

    if _is_url(req_str):
        link = Link(req_str)
    else:
        path = os.path.normpath(os.path.abspath(req_str))
        p, _ = _strip_extras(path)
        url = _get_url_from_path(p, req_str)
        if url is not None:
            link = Link(url)

    # it's a local file, dir, or url
    if link is not None:
        # Handle relative file URLs
        if link.scheme == "file" and re.search(r"\.\./", link.url):
            link = Link(_path_to_url(os.path.normpath(os.path.abspath(link.path))))
        # wheel file
        if link.is_wheel:
            wheel_info = WHEEL_FILE_RE.match(link.filename)
            if wheel_info is None:
                raise PipError(f"Invalid wheel name: {link.filename}")
            wheel_name = wheel_info.group("name").replace("_", "-")
            wheel_version = wheel_info.group("ver").replace("_", "-")
            req_str = f"{wheel_name}=={wheel_version}"
        else:
            # set the req to the egg fragment.  when it's not there, this
            # will become an 'unnamed' requirement
            req_str = _egg_fragment(link.url)
            if req_str is None:
                raise PipError(f"Missing egg fragment in URL: {original_req_str}")
            req_str = f"{req_str}@{link.url}"

    # Reassemble the requirement string with the original marker
    if marker_str is not None:
        req_str = f"{req_str}{marker_sep}{marker_str}"

    return req_str


def parse_requirements(
    filename: os.PathLike,
    options: Optional[Any] = None,
    include_invalid: bool = False,
    strict_hashes: bool = False,
) -> Dict[str, Union[Requirement, UnparsedRequirement]]:
    to_parse = {filename}
    parsed = set()
    name_to_req = {}

    while to_parse:
        filename = to_parse.pop()
        dirname = os.path.dirname(filename)
        parsed.add(filename)

        # Combine multi-line commands
        lines = "".join(_read_file(filename)).replace("\\\n", "").splitlines()
        lines_enum = enumerate(lines, 1)
        lines_enum = _ignore_comments(lines_enum)
        lines_enum = _skip_regex(lines_enum, options)

        for lineno, line in lines_enum:
            req: Optional[Union[Requirement, UnparsedRequirement]] = None
            known, _ = parser.parse_known_args(line.strip().split())

            hashes_by_kind = defaultdict(list)
            if known.hashes:
                for hsh in known.hashes:
                    kind, hsh = hsh.split(":", 1)
                    if kind not in VALID_HASHES:
                        raise PipError(
                            "Invalid --hash kind %s, expected one of %s"
                            % (kind, VALID_HASHES)
                        )
                    hashes_by_kind[kind].append(hsh)

            if known.req:
                req_str = str().join(known.req)
                try:
                    parsed_req_str = _parse_requirement_url(req_str)
                except PipError as e:
                    if include_invalid:
                        req = UnparsedRequirement(req_str, str(e), filename, lineno)
                    else:
                        raise

                try:  # Try to parse this as a requirement specification
                    if req is None:
                        req = Requirement(
                            parsed_req_str,
                            hashes=dict(hashes_by_kind),
                            filename=filename,
                            lineno=lineno,
                        )
                except requirements.InvalidRequirement:
                    try:
                        _check_invalid_requirement(req_str)
                    except PipError as e:
                        if include_invalid:
                            req = UnparsedRequirement(req_str, str(e), filename, lineno)
                        else:
                            raise

            elif known.requirement:
                full_path = os.path.join(dirname, known.requirement)
                if full_path not in parsed:
                    to_parse.add(full_path)
            elif known.editable:
                name, url = _parse_editable(known.editable)
                req = Requirement(
                    "%s @ %s" % (name, url),
                    filename=filename,
                    lineno=lineno,
                    editable=True,
                )
            else:
                pass  # This is an invalid requirement

            # If we've found a requirement, add it
            if req:
                if not isinstance(req, UnparsedRequirement):
                    req.comes_from = "-r {} (line {})".format(filename, lineno)  # type: ignore
                    if req.marker is not None and not req.marker.evaluate():
                        continue

                if req.name not in name_to_req:
                    name_to_req[req.name.lower()] = req
                else:
                    raise PipError(
                        "Double requirement given: %s (already in %s, name=%r)"
                        % (req, name_to_req[req.name], req.name)
                    )

    if strict_hashes:
        missing_hashes = [req for req in name_to_req.values() if not req.hashes]
        if len(missing_hashes) > 0:
            raise PipError(
                "Missing hashes for requirement in %s, line %s"
                % (missing_hashes[0].filename, missing_hashes[0].lineno)
            )

    return name_to_req
