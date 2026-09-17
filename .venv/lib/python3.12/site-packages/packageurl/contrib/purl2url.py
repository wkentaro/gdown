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

from packageurl import PackageURL
from packageurl.contrib.route import NoRouteAvailable
from packageurl.contrib.route import Router

DEFAULT_MAVEN_REPOSITORY = "https://repo.maven.apache.org/maven2"


def get_repo_download_url_by_package_type(
    type, namespace, name, version, archive_extension="tar.gz"
):
    """
    Return the download URL for a hosted git repository given a package type
    or None.
    """
    if archive_extension not in ("zip", "tar.gz"):
        raise ValueError("Only zip and tar.gz extensions are supported")

    download_url_by_type = {
        "github": f"https://github.com/{namespace}/{name}/archive/{version}.{archive_extension}",
        "bitbucket": f"https://bitbucket.org/{namespace}/{name}/get/{version}.{archive_extension}",
        "gitlab": f"https://gitlab.com/{namespace}/{name}/-/archive/{version}/{name}-{version}.{archive_extension}",
    }
    return download_url_by_type.get(type)


repo_router = Router()
download_router = Router()


def _get_url_from_router(router, purl):
    if purl:
        try:
            return router.process(purl)
        except NoRouteAvailable:
            return


def get_repo_url(purl):
    """
    Return a repository URL inferred from the `purl` string.
    """
    return _get_url_from_router(repo_router, purl)


def get_download_url(purl):
    """
    Return a download URL inferred from the `purl` string.
    """
    download_url = _get_url_from_router(download_router, purl)
    if download_url:
        return download_url

    # Fallback on the `download_url` qualifier when available.
    purl_data = PackageURL.from_string(purl)
    return purl_data.qualifiers.get("download_url", None)


def get_inferred_urls(purl):
    """
    Return all inferred URLs (repo, download) from the `purl` string.
    """
    url_functions = (
        get_repo_url,
        get_download_url,
    )

    inferred_urls = []
    for url_func in url_functions:
        url = url_func(purl)
        if url:
            inferred_urls.append(url)

    return inferred_urls


# Backward compatibility
purl2url = get_repo_url
get_url = get_repo_url


@repo_router.route("pkg:cargo/.*")
def build_cargo_repo_url(purl):
    """
    Return a cargo repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://crates.io/crates/{name}/{version}"
    elif name:
        return f"https://crates.io/crates/{name}"


@repo_router.route("pkg:bitbucket/.*")
def build_bitbucket_repo_url(purl):
    """
    Return a bitbucket repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name

    if name and namespace:
        return f"https://bitbucket.org/{namespace}/{name}"


@repo_router.route("pkg:github/.*")
def build_github_repo_url(purl):
    """
    Return a github repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version
    qualifiers = purl_data.qualifiers

    if not (name and namespace):
        return

    repo_url = f"https://github.com/{namespace}/{name}"

    if version:
        version_prefix = qualifiers.get("version_prefix", "")
        repo_url = f"{repo_url}/tree/{version_prefix}{version}"

    return repo_url


@repo_router.route("pkg:gitlab/.*")
def build_gitlab_repo_url(purl):
    """
    Return a gitlab repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name

    if name and namespace:
        return f"https://gitlab.com/{namespace}/{name}"


@repo_router.route("pkg:(gem|rubygems)/.*")
def build_rubygems_repo_url(purl):
    """
    Return a rubygems repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://rubygems.org/gems/{name}/versions/{version}"
    elif name:
        return f"https://rubygems.org/gems/{name}"


@repo_router.route("pkg:cran/.*")
def build_cran_repo_url(purl):
    """
    Return a cran repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    return f"https://cran.r-project.org/src/contrib/{name}_{version}.tar.gz"


@repo_router.route("pkg:npm/.*")
def build_npm_repo_url(purl):
    """
    Return a npm repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version

    repo_url = "https://www.npmjs.com/package/"
    if namespace:
        repo_url += f"{namespace}/"

    repo_url += f"{name}"

    if version:
        repo_url += f"/v/{version}"

    return repo_url


@repo_router.route("pkg:pypi/.*")
def build_pypi_repo_url(purl):
    """
    Return a pypi repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = (purl_data.name or "").replace("_", "-")
    version = purl_data.version

    if name and version:
        return f"https://pypi.org/project/{name}/{version}/"
    elif name:
        return f"https://pypi.org/project/{name}/"


@repo_router.route("pkg:composer/.*")
def build_composer_repo_url(purl):
    """
    Return a composer repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version
    namespace = purl_data.namespace

    if name and version:
        return f"https://packagist.org/packages/{namespace}/{name}#{version}"
    elif name:
        return f"https://packagist.org/packages/{namespace}/{name}"


@repo_router.route("pkg:nuget/.*")
def build_nuget_repo_url(purl):
    """
    Return a nuget repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://www.nuget.org/packages/{name}/{version}"
    elif name:
        return f"https://www.nuget.org/packages/{name}"


@repo_router.route("pkg:hackage/.*")
def build_hackage_repo_url(purl):
    """
    Return a hackage repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://hackage.haskell.org/package/{name}-{version}"
    elif name:
        return f"https://hackage.haskell.org/package/{name}"


@repo_router.route("pkg:golang/.*")
def build_golang_repo_url(purl):
    """
    Return a golang repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://pkg.go.dev/{namespace}/{name}@{version}"
    elif name:
        return f"https://pkg.go.dev/{namespace}/{name}"


@repo_router.route("pkg:cocoapods/.*")
def build_cocoapods_repo_url(purl):
    """
    Return a CocoaPods repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)
    name = purl_data.name
    return name and f"https://cocoapods.org/pods/{name}"


@repo_router.route("pkg:maven/.*")
def build_maven_repo_url(purl):
    """
    Return a Maven repo URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)
    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version
    qualifiers = purl_data.qualifiers

    base_url = qualifiers.get("repository_url", DEFAULT_MAVEN_REPOSITORY)

    if namespace and name and version:
        namespace = namespace.replace(".", "/")
        return f"{base_url}/{namespace}/{name}/{version}"


# Download URLs:


@download_router.route("pkg:cargo/.*")
def build_cargo_download_url(purl):
    """
    Return a cargo download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://crates.io/api/v1/crates/{name}/{version}/download"


@download_router.route("pkg:(gem|rubygems)/.*")
def build_rubygems_download_url(purl):
    """
    Return a rubygems download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://rubygems.org/downloads/{name}-{version}.gem"


@download_router.route("pkg:npm/.*")
def build_npm_download_url(purl):
    """
    Return a npm download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version

    base_url = "https://registry.npmjs.org"

    if namespace:
        base_url += f"/{namespace}"

    if name and version:
        return f"{base_url}/{name}/-/{name}-{version}.tgz"


@download_router.route("pkg:maven/.*")
def build_maven_download_url(purl):
    """
    Return a maven download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version
    qualifiers = purl_data.qualifiers

    base_url = qualifiers.get("repository_url", DEFAULT_MAVEN_REPOSITORY)
    maven_type = qualifiers.get("type", "jar")  # default to "jar"
    classifier = qualifiers.get("classifier")

    if namespace and name and version:
        namespace = namespace.replace(".", "/")
        classifier = f"-{classifier}" if classifier else ""
        return f"{base_url}/{namespace}/{name}/{version}/{name}-{version}{classifier}.{maven_type}"


@download_router.route("pkg:hackage/.*")
def build_hackage_download_url(purl):
    """
    Return a hackage download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://hackage.haskell.org/package/{name}-{version}/{name}-{version}.tar.gz"


@download_router.route("pkg:nuget/.*")
def build_nuget_download_url(purl):
    """
    Return a nuget download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://www.nuget.org/api/v2/package/{name}/{version}"


@download_router.route("pkg:gitlab/.*", "pkg:bitbucket/.*", "pkg:github/.*")
def build_repo_download_url(purl):
    """
    Return a gitlab download URL from the `purl` string.
    """
    return get_repo_download_url(purl)


@download_router.route("pkg:hex/.*")
def build_hex_download_url(purl):
    """
    Return a hex download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://repo.hex.pm/tarballs/{name}-{version}.tar"


@download_router.route("pkg:golang/.*")
def build_golang_download_url(purl):
    """
    Return a golang download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version

    if not name:
        return

    # TODO: https://github.com/package-url/packageurl-python/issues/197
    if namespace:
        name = f"{namespace}/{name}"

    ename = escape_golang_path(name)
    eversion = escape_golang_path(version)

    if not eversion.startswith("v"):
        eversion = "v" + eversion

    if name and version:
        return f"https://proxy.golang.org/{ename}/@v/{eversion}.zip"


@download_router.route("pkg:pub/.*")
def build_pub_download_url(purl):
    """
    Return a pub download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"https://pub.dev/api/archives/{name}-{version}.tar.gz"


@download_router.route("pkg:swift/.*")
def build_swift_download_url(purl):
    """
    Return a Swift Package download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    name = purl_data.name
    version = purl_data.version
    namespace = purl_data.namespace

    if not (namespace or name or version):
        return

    return f"https://{namespace}/{name}/archive/{version}.zip"


@download_router.route("pkg:luarocks/.*")
def build_luarocks_download_url(purl):
    """
    Return a LuaRocks download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)

    qualifiers = purl_data.qualifiers or {}

    repository_url = qualifiers.get("repository_url", "https://luarocks.org")

    name = purl_data.name
    version = purl_data.version

    if name and version:
        return f"{repository_url}/{name}-{version}.src.rock"


@download_router.route("pkg:conda/.*")
def build_conda_download_url(purl):
    """
    Resolve a Conda PURL to a real downloadable URL

    Supported qualifiers:
      - channel: e.g., main, conda-forge (required for deterministic base)
      - subdir: e.g., linux-64, osx-arm64, win-64, noarch
      - build:  exact build string (optional but recommended)
      - type:   'conda' or 'tar.bz2' (preference; fallback to whichever exists)
    """
    p = PackageURL.from_string(purl)
    if not p.name or not p.version:
        return None

    q = p.qualifiers or {}
    name = p.name
    version = p.version
    build = q.get("build")
    channel = q.get("channel") or "main"
    subdir = q.get("subdir") or "noarch"
    req_type = q.get("type")

    def _conda_base_for_channel(channel: str) -> str:
        """
        Map a conda channel to its base URL.
        - 'main' / 'defaults' -> repo.anaconda.com
        - any other channel    -> conda.anaconda.org/<channel>
        """
        ch = (channel or "").lower()
        if ch in ("main", "defaults"):
            return "https://repo.anaconda.com/pkgs/main"
        return f"https://conda.anaconda.org/{ch}"

    base = _conda_base_for_channel(channel)

    package_identifier = (
        f"{name}-{version}-{build}.{req_type}" if build else f"{name}-{version}.{req_type}"
    )

    download_url = f"{base}/{subdir}/{package_identifier}"
    return download_url


@download_router.route("pkg:alpm/.*")
def build_alpm_download_url(purl_str):
    purl = PackageURL.from_string(purl_str)
    name = purl.name
    version = purl.version
    arch = purl.qualifiers.get("arch", "any")

    if not name or not version:
        return None

    first_letter = name[0]
    url = f"https://archive.archlinux.org/packages/{first_letter}/{name}/{name}-{version}-{arch}.pkg.tar.zst"
    return url


def normalize_version(version: str) -> str:
    """
    Remove the epoch (if any) from a Debian version.
    E.g., "1:2.4.47-2" becomes "2.4.47-2"
    """
    if ":" in version:
        _, v = version.split(":", 1)
        return v
    return version


@download_router.route("pkg:deb/.*")
def build_deb_download_url(purl_str: str) -> str:
    """
    Construct a download URL for a Debian or Ubuntu package PURL.
    Supports optional 'repository_url' in qualifiers.
    """
    p = PackageURL.from_string(purl_str)

    name = p.name
    version = p.version
    namespace = p.namespace
    qualifiers = p.qualifiers or {}
    arch = qualifiers.get("arch")
    repository_url = qualifiers.get("repository_url")

    if not name or not version:
        raise ValueError("Both name and version must be present in deb purl")

    if not arch:
        arch = "source"

    if repository_url:
        base_url = repository_url.rstrip("/")
    else:
        if namespace == "debian":
            base_url = "https://deb.debian.org/debian"
        elif namespace == "ubuntu":
            base_url = "http://archive.ubuntu.com/ubuntu"
        else:
            raise NotImplementedError(f"Unsupported distro namespace: {namespace}")

    norm_version = normalize_version(version)

    if arch == "source":
        filename = f"{name}_{norm_version}.dsc"
    else:
        filename = f"{name}_{norm_version}_{arch}.deb"

    pool_path = f"/pool/main/{name[0].lower()}/{name}"

    return f"{base_url}{pool_path}/{filename}"


@download_router.route("pkg:apk/.*")
def build_apk_download_url(purl):
    """
    Return a download URL for a fully qualified Alpine Linux package PURL.

    Example:
    pkg:apk/acct@6.6.4-r0?arch=x86&alpine_version=v3.11&repo=main
    """
    purl = PackageURL.from_string(purl)
    name = purl.name
    version = purl.version
    arch = purl.qualifiers.get("arch")
    repo = purl.qualifiers.get("repo")
    alpine_version = purl.qualifiers.get("alpine_version")

    if not name or not version or not arch or not repo or not alpine_version:
        raise ValueError(
            "All qualifiers (arch, repo, alpine_version) and name/version must be present in apk purl"
        )

    return (
        f"https://dl-cdn.alpinelinux.org/alpine/{alpine_version}/{repo}/{arch}/{name}-{version}.apk"
    )


def get_repo_download_url(purl):
    """
    Return ``download_url`` if present in ``purl`` qualifiers or
    if ``namespace``, ``name`` and ``version`` are present in ``purl``
    else return None.
    """
    purl_data = PackageURL.from_string(purl)

    namespace = purl_data.namespace
    type = purl_data.type
    name = purl_data.name
    version = purl_data.version
    qualifiers = purl_data.qualifiers

    download_url = qualifiers.get("download_url")
    if download_url:
        return download_url

    if not (namespace and name and version):
        return

    version_prefix = qualifiers.get("version_prefix", "")
    version = f"{version_prefix}{version}"

    return get_repo_download_url_by_package_type(
        type=type, namespace=namespace, name=name, version=version
    )


# TODO: https://github.com/package-url/packageurl-python/issues/196
def escape_golang_path(path: str) -> str:
    """
    Return an case-encoded module path or version name.

    This is done by replacing every uppercase letter with an exclamation mark followed by the
    corresponding lower-case letter, in order to avoid ambiguity when serving from case-insensitive
    file systems.

    See https://golang.org/ref/mod#goproxy-protocol.
    """
    escaped_path = ""
    for c in path:
        if c >= "A" and c <= "Z":
            # replace uppercase with !lowercase
            escaped_path += "!" + chr(ord(c) + ord("a") - ord("A"))
        else:
            escaped_path += c
    return escaped_path
