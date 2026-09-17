# -*- coding: utf-8 -*-
#
# Copyright (c) the purl authors
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Visit https://github.com/package-url/packageurl-python for support and
# download.

import os
import re
from urllib.parse import unquote_plus
from urllib.parse import urlparse

from packageurl import PackageURL
from packageurl.contrib.route import NoRouteAvailable
from packageurl.contrib.route import Router

"""
This module helps build a PackageURL from an arbitrary URL.
This uses the a routing mechanism available in the route.py module.

In order to make it easy to use, it contains all the conversion functions
in this single Python script.
"""


purl_router = Router()


def url2purl(url):
    """
    Return a PackageURL inferred from the `url` string or None.
    """
    if url:
        try:
            return purl_router.process(url)
        except NoRouteAvailable:
            # If `url` does not fit in one of the existing routes,
            # we attempt to create a generic PackageURL for `url`
            return build_generic_purl(url)


get_purl = url2purl


def purl_from_pattern(type_, pattern, url, qualifiers=None):
    url = unquote_plus(url)
    compiled_pattern = re.compile(pattern, re.VERBOSE)
    match = compiled_pattern.match(url)

    if not match:
        return

    purl_data = {
        field: value for field, value in match.groupdict().items() if field in PackageURL._fields
    }

    qualifiers = qualifiers or {}
    # Include the `version_prefix` as a qualifier to infer valid URLs in purl2url
    version_prefix = match.groupdict().get("version_prefix")
    if version_prefix:
        qualifiers.update({"version_prefix": version_prefix})

    if qualifiers:
        if "qualifiers" in purl_data:
            purl_data["qualifiers"].update(qualifiers)
        else:
            purl_data["qualifiers"] = qualifiers

    return PackageURL(type_, **purl_data)


def register_pattern(type_, pattern, router=purl_router):
    """
    Register a pattern with its type.
    """

    def endpoint(url):
        return purl_from_pattern(type_, pattern, url)

    router.append(pattern, endpoint)


def get_path_segments(url):
    """
    Return a list of path segments from a `url` string.
    """
    path = unquote_plus(urlparse(url).path)
    segments = [seg for seg in path.split("/") if seg]
    return segments


def build_generic_purl(uri):
    """
    Return a PackageURL from `uri`, if `uri` is a parsable URL, or None

    `uri` is assumed to be a download URL, e.g. https://example.com/example.tar.gz
    """
    parsed_uri = urlparse(uri)
    if parsed_uri.scheme and parsed_uri.netloc and parsed_uri.path:
        # Get file name from `uri`
        uri_path_segments = get_path_segments(uri)
        if uri_path_segments:
            file_name = uri_path_segments[-1]
            return PackageURL(type="generic", name=file_name, qualifiers={"download_url": uri})


@purl_router.route(
    "https?://registry.npmjs.*/.*",
    "https?://registry.yarnpkg.com/.*",
    "https?://(www\\.)?npmjs.*/package.*",
    "https?://(www\\.)?yarnpkg.com/package.*",
)
def build_npm_purl(uri):
    # npm URLs are difficult to disambiguate with regex
    if "/package/" in uri:
        return build_npm_web_purl(uri)
    elif "/-/" in uri:
        return build_npm_download_purl(uri)
    else:
        return build_npm_api_purl(uri)


def build_npm_api_purl(uri):
    path = unquote_plus(urlparse(uri).path)
    segments = [seg for seg in path.split("/") if seg]

    if len(segments) < 2:
        return

    # /@esbuild/freebsd-arm64/0.21.5
    if len(segments) == 3:
        return PackageURL("npm", namespace=segments[0], name=segments[1], version=segments[2])

    # /@invisionag/eslint-config-ivx
    if segments[0].startswith("@"):
        return PackageURL("npm", namespace=segments[0], name=segments[1])

    # /angular/1.6.6
    return PackageURL("npm", name=segments[0], version=segments[1])


def build_npm_download_purl(uri):
    path = unquote_plus(urlparse(uri).path)
    segments = [seg for seg in path.split("/") if seg and seg != "-"]
    len_segments = len(segments)

    # /@invisionag/eslint-config-ivx/-/eslint-config-ivx-0.0.2.tgz
    if len_segments == 3:
        namespace, name, filename = segments

    # /automatta/-/automatta-0.0.1.tgz
    elif len_segments == 2:
        namespace = None
        name, filename = segments

    else:
        return

    base_filename, ext = os.path.splitext(filename)
    version = base_filename.replace(name, "")
    if version.startswith("-"):
        version = version[1:]  # Removes the "-" prefix

    return PackageURL("npm", namespace, name, version)


def build_npm_web_purl(uri):
    path = unquote_plus(urlparse(uri).path)
    if path.startswith("/package/"):
        path = path[9:]

    segments = [seg for seg in path.split("/") if seg]
    len_segments = len(segments)
    namespace = version = None

    # @angular/cli/v/10.1.2
    if len_segments == 4:
        namespace = segments[0]
        name = segments[1]
        version = segments[3]

    # express/v/4.17.1
    elif len_segments == 3:
        namespace = None
        name = segments[0]
        version = segments[2]

    # @angular/cli
    elif len_segments == 2:
        namespace = segments[0]
        name = segments[1]

    # express
    elif len_segments == 1 and len(segments) > 0 and segments[0][0] != "@":
        name = segments[0]

    else:
        return

    return PackageURL("npm", namespace, name, version)


@purl_router.route(
    "https?://repo1.maven.org/maven2/.*",
    "https?://central.maven.org/maven2/.*",
    "maven-index://repo1.maven.org/.*",
)
def build_maven_purl(uri):
    path = unquote_plus(urlparse(uri).path)
    segments = [seg for seg in path.split("/") if seg and seg != "maven2"]

    if len(segments) < 3:
        return

    before_last_segment, last_segment = segments[-2:]
    has_filename = before_last_segment in last_segment

    filename = None
    if has_filename:
        filename = segments.pop()

    version = segments[-1]
    name = segments[-2]
    namespace = ".".join(segments[:-2])
    qualifiers = {}

    if filename:
        name_version = f"{name}-{version}"
        _, _, classifier_ext = filename.rpartition(name_version)
        classifier, _, extension = classifier_ext.partition(".")
        if not extension:
            return

        qualifiers["classifier"] = classifier.strip("-")

        valid_types = ("aar", "ear", "mar", "pom", "rar", "rpm", "sar", "tar.gz", "war", "zip")
        if extension in valid_types:
            qualifiers["type"] = extension

    return PackageURL("maven", namespace, name, version, qualifiers)


# https://rubygems.org/gems/i18n-js-3.0.11.gem
@purl_router.route("https?://rubygems.org/(downloads|gems)/.*")
def build_rubygems_purl(uri):
    # We use a more general route pattern instead of using `rubygems_pattern`
    # below by itself because we want to capture all rubygems download URLs,
    # even the ones that are not completely formed. This helps prevent url2purl
    # from attempting to create a generic PackageURL from an invalid rubygems
    # download URL.

    # https://rubygems.org/downloads/jwt-0.1.8.gem
    # https://rubygems.org/gems/i18n-js-3.0.11.gem
    rubygems_pattern = (
        r"^https?://rubygems.org/(downloads|gems)/(?P<name>.+)-(?P<version>.+)(\.gem)$"
    )
    return purl_from_pattern("gem", rubygems_pattern, uri)


# https://cran.r-project.org/src/contrib/jsonlite_1.8.8.tar.gz
# https://packagemanager.rstudio.com/cran/2022-06-23/src/contrib/curl_4.3.2.tar.gz"
@purl_router.route(
    "https?://cran.r-project.org/.*",
    "https?://packagemanager.rstudio.com/cran/.*",
)
def build_cran_purl(uri):
    cran_pattern = r"^https?://(cran\.r-project\.org|packagemanager\.rstudio\.com/cran)/.*?src/contrib/(?P<name>.+)_(?P<version>.+)\.tar.gz$"
    qualifiers = {}
    if "//cran.r-project.org/" not in uri:
        qualifiers["download_url"] = uri
    return purl_from_pattern("cran", cran_pattern, uri, qualifiers)


# https://pypi.org/packages/source/a/anyjson/anyjson-0.3.3.tar.gz
# https://pypi.python.org/packages/source/a/anyjson/anyjson-0.3.3.tar.gz
# https://pypi.python.org/packages/2.6/t/threadpool/threadpool-1.2.7-py2.6.egg
# https://pypi.python.org/packages/any/s/setuptools/setuptools-0.6c11-1.src.rpm
# https://files.pythonhosted.org/packages/84/d8/451842a5496844bb5c7634b231a2e4caf0d867d2e25f09b840d3b07f3d4b/multi_key_dict-2.0.win32.exe
pypi_pattern = r"(?P<name>(\w\.?)+(-\w+)*)-(?P<version>.+)\.(zip|tar.gz|tar.bz2|tgz|egg|rpm|exe)$"

# This pattern can be found in the following locations:
# - wheel.wheelfile.WHEEL_INFO_RE
# - distlib.wheel.FILENAME_RE
# - setuptools.wheel.WHEEL_NAME
# - pip._internal.wheel.Wheel.wheel_file_re
wheel_file_re = re.compile(
    r"^(?P<namever>(?P<name>.+?)-(?P<version>.*?))"
    r"((-(?P<build>\d[^-]*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)"
    r"\.whl)$",
    re.VERBOSE,
)


@purl_router.route(
    "https?://pypi.org/(packages|project)/.+",
    "https?://.+python.+org/(packages|project)/.*",
)
def build_pypi_purl(uri):
    path = unquote_plus(urlparse(uri).path)
    segments = path.split("/")
    last_segment = segments[-1]

    # /wheel-0.29.0-py2.py3-none-any.whl
    if last_segment.endswith(".whl"):
        match = wheel_file_re.match(last_segment)
        if match:
            return PackageURL(
                "pypi",
                name=match.group("name"),
                version=match.group("version"),
            )

    if segments[1] == "project":
        return PackageURL(
            "pypi",
            name=segments[2],
            version=segments[3] if len(segments) > 3 else None,
        )

    return purl_from_pattern("pypi", pypi_pattern, last_segment)


# https://packagist.org/packages/webmozart/assert#1.9.1
@purl_router.route("https?://packagist.org/packages/.*")
def build_composer_purl(uri):
    # We use a more general route pattern instead of using `composer_pattern`
    # below by itself because we want to capture all packagist download URLs,
    # even the ones that are not completely formed. This helps prevent url2purl
    # from attempting to create a generic PackageURL from an invalid packagist
    # download URL.

    # https://packagist.org/packages/ralouphie/getallheaders
    # https://packagist.org/packages/symfony/process#v7.0.0-BETA3
    composer_pattern = r"^https?://packagist\.org/packages/(?P<namespace>[^/]+)/(?P<name>[^\#]+?)(\#(?P<version>.+))?$"
    return purl_from_pattern("composer", composer_pattern, uri)


# http://nuget.org/packages/EntityFramework/4.2.0.0
# https://www.nuget.org/api/v2/package/Newtonsoft.Json/11.0.1
nuget_www_pattern = r"^https?://.*nuget.org/(api/v2/)?packages?/(?P<name>.+)/(?P<version>.+)$"

register_pattern("nuget", nuget_www_pattern)


# https://api.nuget.org/v3-flatcontainer/newtonsoft.json/10.0.1/newtonsoft.json.10.0.1.nupkg
nuget_api_pattern = (
    r"^https?://api.nuget.org/v3-flatcontainer/"
    r"(?P<name>.+)/"
    r"(?P<version>.+)/"
    r".*(nupkg)$"  # ends with "nupkg"
)

register_pattern("nuget", nuget_api_pattern)


# https://sourceforge.net/projects/turbovnc/files/3.1/turbovnc-3.1.tar.gz/download
# https://sourceforge.net/projects/scribus/files/scribus/1.6.0/scribus-1.6.0.tar.gz/download
# https://sourceforge.net/projects/ventoy/files/v1.0.96/Ventoy%201.0.96%20release%20source%20code.tar.gz/download
# https://sourceforge.net/projects/geoserver/files/GeoServer/2.23.4/geoserver-2.23.4-war.zip/download
sourceforge_download_pattern = (
    r"^https?://.*sourceforge.net/projects/"
    r"(?P<name>.+)/"
    r"files/"
    r"(?i:(?P=name)/)?"  # optional case-insensitive name segment repeated
    r"v?(?P<version>[0-9\.]+)/"  # version restricted to digits and dots
    r"(?i:(?P=name)).*(?P=version).*"  # case-insensitive matching for {name}-{version}
    r"(/download)$"  # ending with "/download"
)

register_pattern("sourceforge", sourceforge_download_pattern)


# https://sourceforge.net/projects/spacesniffer/files/spacesniffer_1_3_0_2.zip/download
sourceforge_download_pattern_bis = (
    r"^https?://.*sourceforge.net/projects/"
    r"(?P<name>.+)/"
    r"files/"
    r"(?i:(?P=name))_*(?P<version>[0-9_]+).*"
    r"(/download)$"  # ending with "/download"
)

register_pattern("sourceforge", sourceforge_download_pattern_bis)


@purl_router.route("https?://.*sourceforge.net/project/.*")
def build_sourceforge_purl(uri):
    # We use a more general route pattern instead of using `sourceforge_pattern`
    # below by itself because we want to capture all sourceforge download URLs,
    # even the ones that do not fit `sourceforge_pattern`. This helps prevent
    # url2purl from attempting to create a generic PackageURL from a sourceforge
    # URL that we can't handle.

    # http://master.dl.sourceforge.net/project/libpng/zlib/1.2.3/zlib-1.2.3.tar.bz2
    sourceforge_pattern = (
        r"^https?://.*sourceforge.net/projects?/"
        r"(?P<namespace>([^/]+))/"  # do not allow more "/" segments
        r"(OldFiles/)?"
        r"(?P<name>.+)/"
        r"(?P<version>[v0-9\.]+)/"  # version restricted to digits and dots
        r"(?P=name).*(?P=version).*"  # {name}-{version} repeated in the filename
        r"[^/]$"  # not ending with "/"
    )

    sourceforge_purl = purl_from_pattern("sourceforge", sourceforge_pattern, uri)

    if not sourceforge_purl:
        # Get the project name from `uri` and use that as the Package name
        # http://master.dl.sourceforge.net/project/aloyscore/aloyscore/0.1a1%2520stable/0.1a1_stable_AloysCore.zip
        split_uri = uri.split("/project/")

        # http://master.dl.sourceforge.net, aloyscore/aloyscore/0.1a1%2520stable/0.1a1_stable_AloysCore.zip
        if len(split_uri) >= 2:
            # aloyscore/aloyscore/0.1a1%2520stable/0.1a1_stable_AloysCore.zip
            remaining_uri_path = split_uri[1]
            # aloyscore, aloyscore, 0.1a1%2520stable, 0.1a1_stable_AloysCore.zip
            remaining_uri_path_segments = remaining_uri_path.split("/")
            if remaining_uri_path_segments:
                project_name = remaining_uri_path_segments[0]  # aloyscore
                sourceforge_purl = PackageURL(
                    type="sourceforge", name=project_name, qualifiers={"download_url": uri}
                )
    return sourceforge_purl


# https://crates.io/api/v1/crates/rand/0.7.2/download
cargo_pattern = r"^https?://crates.io/api/v1/crates/(?P<name>.+)/(?P<version>.+)(\/download)$"

register_pattern("cargo", cargo_pattern)


# https://raw.githubusercontent.com/volatilityfoundation/dwarf2json/master/LICENSE.txt
github_raw_content_pattern = (
    r"https?://raw.githubusercontent.com/(?P<namespace>[^/]+)/(?P<name>[^/]+)/"
    r"(?P<version>[^/]+)/(?P<subpath>.*)$"
)

register_pattern("github", github_raw_content_pattern)


@purl_router.route("https?://api.github\\.com/repos/.*")
def build_github_api_purl(url):
    """
    Return a PackageURL object from GitHub API `url`.
    For example:
    https://api.github.com/repos/nexB/scancode-toolkit/commits/40593af0df6c8378d2b180324b97cb439fa11d66
    https://api.github.com/repos/nexB/scancode-toolkit/
    and returns a `PackageURL` object
    """
    segments = get_path_segments(url)

    if not (len(segments) >= 3):
        return
    namespace = segments[1]
    name = segments[2]
    version = None

    # https://api.github.com/repos/nexB/scancode-toolkit/
    if len(segments) == 4 and segments[3] != "commits":
        version = segments[3]

    # https://api.github.com/repos/nexB/scancode-toolkit/commits/40593af0df6c8378d2b180324b97cb439fa11d66
    if len(segments) == 5 and segments[3] == "commits":
        version = segments[4]

    return PackageURL(type="github", namespace=namespace, name=name, version=version)


# https://codeload.github.com/nexB/scancode-toolkit/tar.gz/v3.1.1
# https://codeload.github.com/berngp/grails-rest/zip/release/0.7
github_codeload_pattern = (
    r"https?://codeload.github.com/(?P<namespace>.+)/(?P<name>.+)/"
    r"(zip|tar.gz|tar.bz2|tgz)/(.*/)*"
    r"(?P<version>.+)$"
)

register_pattern("github", github_codeload_pattern)


@purl_router.route("https?://github\\.com/.*")
def build_github_purl(url):
    """
    Return a PackageURL object from GitHub `url`.
    """

    # https://github.com/apache/nifi/archive/refs/tags/rel/nifi-2.0.0-M3.tar.gz
    archive_tags_pattern = (
        r"https?://github.com/(?P<namespace>.+)/(?P<name>.+)"
        r"/archive/refs/tags/"
        r"(?P<version>.+).(zip|tar.gz|tar.bz2|.tgz)"
    )

    # https://github.com/nexB/scancode-toolkit/archive/v3.1.1.zip
    archive_pattern = (
        r"https?://github.com/(?P<namespace>.+)/(?P<name>.+)"
        r"/archive/(.*/)*"
        r"((?P=name)(-|_|@))?"
        r"(?P<version>.+).(zip|tar.gz|tar.bz2|.tgz)"
    )

    # https://github.com/downloads/mozilla/rhino/rhino1_7R4.zip
    download_pattern = (
        r"https?://github.com/downloads/(?P<namespace>.+)/(?P<name>.+)/"
        r"((?P=name)(-|@)?)?"
        r"(?P<version>.+).(zip|tar.gz|tar.bz2|.tgz)"
    )

    # https://github.com/pypa/get-virtualenv/raw/20.0.31/public/virtualenv.pyz
    raw_pattern = (
        r"https?://github.com/(?P<namespace>.+)/(?P<name>.+)"
        r"/raw/(?P<version>[^/]+)/(?P<subpath>.*)$"
    )

    # https://github.com/fanf2/unifdef/blob/master/unifdef.c
    blob_pattern = (
        r"https?://github.com/(?P<namespace>.+)/(?P<name>.+)"
        r"/blob/(?P<version>[^/]+)/(?P<subpath>.*)$"
    )

    releases_download_pattern = (
        r"https?://github.com/(?P<namespace>.+)/(?P<name>.+)"
        r"/releases/download/(?P<version>[^/]+)/.*$"
    )

    # https://github.com/pombredanne/schematics.git
    git_pattern = r"https?://github.com/(?P<namespace>.+)/(?P<name>.+).(git)"

    # https://github.com/<namespace>/<name>/commit/<sha>
    commit_pattern = (
        r"https?://github.com/"
        r"(?P<namespace>[^/]+)/(?P<name>[^/]+)/commit/(?P<version>[0-9a-fA-F]{7,40})/?$"
    )

    patterns = (
        commit_pattern,
        archive_tags_pattern,
        archive_pattern,
        raw_pattern,
        blob_pattern,
        releases_download_pattern,
        download_pattern,
        git_pattern,
    )

    for pattern in patterns:
        matches = re.search(pattern, url)
        qualifiers = {}
        if matches:
            if pattern == releases_download_pattern:
                qualifiers["download_url"] = url
            return purl_from_pattern(
                type_="github", pattern=pattern, url=url, qualifiers=qualifiers
            )

    segments = get_path_segments(url)
    if not len(segments) >= 2:
        return

    namespace = segments[0]
    name = segments[1]
    version = None
    subpath = None

    # https://github.com/TG1999/fetchcode/master
    if len(segments) >= 3 and segments[2] != "tree":
        version = segments[2]
        subpath = "/".join(segments[3:])

    # https://github.com/TG1999/fetchcode/tree/master
    if len(segments) >= 4 and segments[2] == "tree":
        version = segments[3]
        subpath = "/".join(segments[4:])

    return PackageURL(
        type="github",
        namespace=namespace,
        name=name,
        version=version,
        subpath=subpath,
    )


# https://bitbucket.org/<namespace>/<name>/commits/<sha>
bitbucket_commit_pattern = (
    r"https?://bitbucket.org/"
    r"(?P<namespace>[^/]+)/(?P<name>[^/]+)/commits/(?P<version>[0-9a-fA-F]{7,64})/?$"
)


@purl_router.route("https?://bitbucket\\.org/.*")
def build_bitbucket_purl(url):
    """
    Return a PackageURL object from BitBucket `url`.
    For example:
    https://bitbucket.org/TG1999/first_repo/src/master or
    https://bitbucket.org/TG1999/first_repo/src or
    https://bitbucket.org/TG1999/first_repo/src/master/new_folder
    https://bitbucket.org/TG1999/first_repo/commits/16a60c4a74ef477cd8c16ca82442eaab2fbe8c86
    """
    commit_matche = re.search(bitbucket_commit_pattern, url)
    if commit_matche:
        return PackageURL(
            type="bitbucket",
            namespace=commit_matche.group("namespace"),
            name=commit_matche.group("name"),
            version=commit_matche.group("version"),
            qualifiers={},
            subpath="",
        )

    segments = get_path_segments(url)

    if not len(segments) >= 2:
        return
    namespace = segments[0]
    name = segments[1]

    bitbucket_download_pattern = (
        r"https?://bitbucket.org/"
        r"(?P<namespace>.+)/(?P<name>.+)/downloads/"
        r"(?P<version>.+).(zip|tar.gz|tar.bz2|.tgz|exe|msi)"
    )
    matches = re.search(bitbucket_download_pattern, url)

    qualifiers = {}
    if matches:
        qualifiers["download_url"] = url
        return PackageURL(type="bitbucket", namespace=namespace, name=name, qualifiers=qualifiers)

    version = None
    subpath = None

    # https://bitbucket.org/TG1999/first_repo/new_folder/
    if len(segments) >= 3 and segments[2] != "src":
        version = segments[2]
        subpath = "/".join(segments[3:])

    # https://bitbucket.org/TG1999/first_repo/src/master/new_folder/
    if len(segments) >= 4 and segments[2] == "src":
        version = segments[3]
        subpath = "/".join(segments[4:])

    return PackageURL(
        type="bitbucket",
        namespace=namespace,
        name=name,
        version=version,
        subpath=subpath,
    )


@purl_router.route("https?://gitlab\\.com/(?!.*/archive/).*")
def build_gitlab_purl(url):
    """
    Return a PackageURL object from Gitlab `url`.
    For example:
    https://gitlab.com/TG1999/firebase/-/tree/1a122122/views
    https://gitlab.com/TG1999/firebase/-/tree
    https://gitlab.com/TG1999/firebase/-/master
    https://gitlab.com/tg1999/Firebase/-/tree/master
    https://gitlab.com/tg1999/Firebase/-/commit/bf04e5f289885cf2f20a92b387bcc6df33e30809
    """
    # https://gitlab.com/<ns>/<name>/-/commit/<sha>
    commit_pattern = (
        r"https?://gitlab.com/"
        r"(?P<namespace>[^/]+)/(?P<name>[^/]+)/-/commit/"
        r"(?P<version>[0-9a-fA-F]{7,64})/?$"
    )

    commit_matche = re.search(commit_pattern, url)
    if commit_matche:
        return PackageURL(
            type="gitlab",
            namespace=commit_matche.group("namespace"),
            name=commit_matche.group("name"),
            version=commit_matche.group("version"),
            qualifiers={},
            subpath="",
        )

    segments = get_path_segments(url)

    if not len(segments) >= 2:
        return
    namespace = segments[0]
    name = segments[1]
    version = None
    subpath = None

    # https://gitlab.com/TG1999/firebase/master
    if (len(segments) >= 3) and segments[2] != "-" and segments[2] != "tree":
        version = segments[2]
        subpath = "/".join(segments[3:])

    # https://gitlab.com/TG1999/firebase/-/tree/master
    if len(segments) >= 5 and (segments[2] == "-" and segments[3] == "tree"):
        version = segments[4]
        subpath = "/".join(segments[5:])

    return PackageURL(
        type="gitlab",
        namespace=namespace,
        name=name,
        version=version,
        subpath=subpath,
    )


# https://gitlab.com/hoppr/hoppr/-/archive/v1.11.1-dev.2/hoppr-v1.11.1-dev.2.tar.gz
gitlab_archive_pattern = (
    r"^https?://gitlab.com/"
    r"(?P<namespace>.+)/(?P<name>.+)/-/archive/(?P<version>.+)/"
    r"(?P=name)-(?P=version).*"
    r"[^/]$"
)

register_pattern("gitlab", gitlab_archive_pattern)


# https://hackage.haskell.org/package/cli-extras-0.2.0.0/cli-extras-0.2.0.0.tar.gz
hackage_download_pattern = (
    r"^https?://hackage.haskell.org/package/"
    r"(?P<name>.+)-(?P<version>.+)/"
    r"(?P=name)-(?P=version).*"
    r"[^/]$"
)

register_pattern("hackage", hackage_download_pattern)


# https://hackage.haskell.org/package/cli-extras-0.2.0.0/
hackage_project_pattern = r"^https?://hackage.haskell.org/package/(?P<name>.+)-(?P<version>[^/]+)/"

register_pattern("hackage", hackage_project_pattern)


@purl_router.route(
    "https?://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/.*"
)
def build_generic_google_code_archive_purl(uri):
    # https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com
    # /android-notifier/android-notifier-desktop-0.5.1-1.i386.rpm
    _, remaining_uri = uri.split(
        "https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/"
    )
    if remaining_uri:  # android-notifier/android-notifier-desktop-0.5.1-1.i386.rpm
        split_remaining_uri = remaining_uri.split("/")
        # android-notifier, android-notifier-desktop-0.5.1-1.i386.rpm
        if split_remaining_uri:
            name = split_remaining_uri[0]  # android-notifier
            return PackageURL(
                type="generic",
                namespace="code.google.com",
                name=name,
                qualifiers={"download_url": uri},
            )
