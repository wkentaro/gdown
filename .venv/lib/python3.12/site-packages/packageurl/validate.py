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

"""
Validate each type according to the PURL spec type definitions
"""


class BasePurlType:
    """
    Base class for all PURL type classes
    """

    type: str
    """The type string for this Package-URL type."""

    type_name: str
    """The name for this PURL type."""

    description: str
    """The description of this PURL type."""

    use_repository: bool = False
    """true if this PURL type use a public package repository."""

    default_repository_url: str
    """The default public repository URL for this PURL type"""

    namespace_requirement: str
    """"States if this namespace is required, optional, or prohibited."""

    allowed_qualifiers: dict = {"repository_url", "arch"}
    """Set of allowed qualifier keys for this PURL type."""

    namespace_case_sensitive: bool = True
    """true if namespace is case sensitive. If false, the canonical form must be lowercased."""

    name_case_sensitive: bool = True
    """true if name is case sensitive. If false, the canonical form must be lowercased."""

    version_case_sensitive: bool = True
    """true if version is case sensitive. If false, the canonical form must be lowercased."""

    purl_pattern: str
    """A regex pattern that matches valid purls of this type."""

    @classmethod
    def validate(cls, purl, strict=False):
        """
        Validate a PackageURL instance or string.
        Yields ValidationMessage and performs strict validation if strict=True
        """
        from packageurl import ValidationMessage
        from packageurl import ValidationSeverity

        if not purl:
            yield ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message="No purl provided",
            )
            return

        from packageurl import PackageURL

        if not isinstance(purl, PackageURL):
            try:
                purl = PackageURL.from_string(purl, normalize_purl=False)
            except Exception as e:
                yield ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid purl {purl!r} string: {e}",
                )
                return

        if not strict:
            purl = cls.normalize(purl)

        yield from cls._validate_namespace(purl)
        yield from cls._validate_name(purl)
        yield from cls._validate_version(purl)
        if strict:
            yield from cls._validate_qualifiers(purl)

        messages = cls.validate_using_type_rules(purl, strict=strict)
        if messages:
            yield from messages

    @classmethod
    def _validate_namespace(cls, purl):
        from packageurl import ValidationMessage
        from packageurl import ValidationSeverity

        if cls.namespace_requirement == "prohibited" and purl.namespace:
            yield ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message=f"Namespace is prohibited for purl type: {cls.type!r}",
            )

        elif cls.namespace_requirement == "required" and not purl.namespace:
            yield ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message=f"Namespace is required for purl type: {cls.type!r}",
            )

        # TODO: Check pending CPAN PR and decide if we want to upgrade the type definition schema
        if purl.type == "cpan":
            if purl.namespace and purl.namespace != purl.namespace.upper():
                yield ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    message=f"Namespace must be uppercase for purl type: {cls.type!r}",
                )
        elif (
            not cls.namespace_case_sensitive
            and purl.namespace
            and purl.namespace.lower() != purl.namespace
        ):
            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Namespace is not lowercased for purl type: {cls.type!r}",
            )

    @classmethod
    def _validate_name(cls, purl):
        if not cls.name_case_sensitive and purl.name and purl.name.lower() != purl.name:
            from packageurl import ValidationMessage
            from packageurl import ValidationSeverity

            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Name is not lowercased for purl type: {cls.type!r}",
            )

    @classmethod
    def _validate_version(cls, purl):
        if not cls.version_case_sensitive and purl.version and purl.version.lower() != purl.version:
            from packageurl import ValidationMessage
            from packageurl import ValidationSeverity

            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Version is not lowercased for purl type: {cls.type!r}",
            )

    @classmethod
    def normalize(cls, purl):
        from packageurl import PackageURL
        from packageurl import normalize

        type_norm, namespace_norm, name_norm, version_norm, qualifiers_norm, subpath_norm = (
            normalize(
                purl.type,
                purl.namespace,
                purl.name,
                purl.version,
                purl.qualifiers,
                purl.subpath,
                encode=False,
            )
        )

        return PackageURL(
            type=type_norm,
            namespace=namespace_norm,
            name=name_norm,
            version=version_norm,
            qualifiers=qualifiers_norm,
            subpath=subpath_norm,
        )

    @classmethod
    def validate_using_type_rules(cls, purl, strict=False):
        """
        Validate using any additional type specific rules.
        Yield validation messages.
        Subclasses can override this method to add type specific validation rules.
        """
        return iter([])

    @classmethod
    def _validate_qualifiers(cls, purl):
        if not purl.qualifiers:
            return

        purl_qualifiers_keys = set(purl.qualifiers.keys())
        allowed_qualifiers_set = cls.allowed_qualifiers

        disallowed = purl_qualifiers_keys - allowed_qualifiers_set

        if disallowed:
            from packageurl import ValidationMessage
            from packageurl import ValidationSeverity

            yield ValidationMessage(
                severity=ValidationSeverity.INFO,
                message=(
                    f"Invalid qualifiers found: {', '.join(sorted(disallowed))}. "
                    f"Allowed qualifiers are: {', '.join(sorted(allowed_qualifiers_set))}"
                ),
            )


class AlpmTypeDefinition(BasePurlType):
    type = "alpm"
    type_name = "Arch Linux package"
    description = """Arch Linux packages and other users of the libalpm/pacman package manager."""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url", "arch"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:alpm/.*"


class ApkTypeDefinition(BasePurlType):
    type = "apk"
    type_name = "APK-based packages"
    description = """Alpine Linux APK-based packages"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url", "arch"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:apk/.*"


class BitbucketTypeDefinition(BasePurlType):
    type = "bitbucket"
    type_name = "Bitbucket"
    description = """Bitbucket-based packages"""
    use_repository = True
    default_repository_url = "https://bitbucket.org"
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:bitbucket/.*"


class BitnamiTypeDefinition(BasePurlType):
    type = "bitnami"
    type_name = "Bitnami"
    description = """Bitnami-based packages"""
    use_repository = True
    default_repository_url = "https://downloads.bitnami.com/files/stacksmith"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"distro", "repository_url", "arch"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:bitnami/.*"


class CargoTypeDefinition(BasePurlType):
    type = "cargo"
    type_name = "Cargo"
    description = """Cargo packages for Rust"""
    use_repository = True
    default_repository_url = "https://crates.io/"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:cargo/.*"


class CocoapodsTypeDefinition(BasePurlType):
    type = "cocoapods"
    type_name = "CocoaPods"
    description = """CocoaPods pods"""
    use_repository = True
    default_repository_url = "https://cdn.cocoapods.org/"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:cocoapods/.*"


class ComposerTypeDefinition(BasePurlType):
    type = "composer"
    type_name = "Composer"
    description = """Composer PHP packages"""
    use_repository = True
    default_repository_url = "https://packagist.org"
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:composer/.*"


class ConanTypeDefinition(BasePurlType):
    type = "conan"
    type_name = "Conan C/C++ packages"
    description = """Conan C/C++ packages. The purl is designed to closely resemble the Conan-native <package-name>/<package-version>@<user>/<channel> syntax for package references as specified in https://docs.conan.io/en/1.46/cheatsheet.html#package-terminology"""
    use_repository = True
    default_repository_url = "https://center.conan.io"
    namespace_requirement = "optional"
    allowed_qualifiers = {"channel", "rrev", "user", "repository_url", "prev"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:conan/.*"


class CondaTypeDefinition(BasePurlType):
    type = "conda"
    type_name = "Conda"
    description = """conda is for Conda packages"""
    use_repository = True
    default_repository_url = "https://repo.anaconda.com"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"channel", "build", "subdir", "repository_url", "type"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:conda/.*"


class CpanTypeDefinition(BasePurlType):
    type = "cpan"
    type_name = "CPAN"
    description = """CPAN Perl packages"""
    use_repository = True
    default_repository_url = "https://www.cpan.org/"
    namespace_requirement = "optional"
    allowed_qualifiers = {"repository_url", "ext", "vcs_url", "download_url"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:cpan/.*"

    @classmethod
    def validate_using_type_rules(cls, purl, strict=False):
        from packageurl import ValidationMessage
        from packageurl import ValidationSeverity

        if purl.namespace and "::" in purl.name:
            yield ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message=f"Name must not contain '::' when Namespace is present for purl type: {cls.type!r}",
            )
        if not purl.namespace and "-" in purl.name:
            yield ValidationMessage(
                severity=ValidationSeverity.ERROR,
                message=f"Name must not contain '-' when Namespace is absent for purl type: {cls.type!r}",
            )
        messages = super().validate_using_type_rules(purl, strict)
        if messages:
            yield from messages


class CranTypeDefinition(BasePurlType):
    type = "cran"
    type_name = "CRAN"
    description = """CRAN R packages"""
    use_repository = True
    default_repository_url = "https://cran.r-project.org"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:cran/.*"


class DebTypeDefinition(BasePurlType):
    type = "deb"
    type_name = "Debian package"
    description = """Debian packages, Debian derivatives, and Ubuntu packages"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url", "arch"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:deb/.*"


class DockerTypeDefinition(BasePurlType):
    type = "docker"
    type_name = "Docker image"
    description = """for Docker images"""
    use_repository = True
    default_repository_url = "https://hub.docker.com"
    namespace_requirement = "optional"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:docker/.*"


class GemTypeDefinition(BasePurlType):
    type = "gem"
    type_name = "RubyGems"
    description = """RubyGems"""
    use_repository = True
    default_repository_url = "https://rubygems.org"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url", "platform"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:gem/.*"


class GenericTypeDefinition(BasePurlType):
    type = "generic"
    type_name = "Generic Package"
    description = """The generic type is for plain, generic packages that do not fit anywhere else such as for "upstream-from-distro" packages. In particular this is handy for a plain version control repository such as a bare git repo in combination with a vcs_url."""
    use_repository = False
    default_repository_url = ""
    namespace_requirement = "optional"
    allowed_qualifiers = {"checksum", "download_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:generic/.*"


class GithubTypeDefinition(BasePurlType):
    type = "github"
    type_name = "GitHub"
    description = """GitHub-based packages"""
    use_repository = True
    default_repository_url = "https://github.com"
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:github/.*"


class GolangTypeDefinition(BasePurlType):
    type = "golang"
    type_name = "Go package"
    description = """Go packages"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:golang/.*"


class HackageTypeDefinition(BasePurlType):
    type = "hackage"
    type_name = "Haskell package"
    description = """Haskell packages"""
    use_repository = True
    default_repository_url = "https://hackage.haskell.org"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:hackage/.*"

    @classmethod
    def validate_using_type_rules(cls, purl, strict=False):
        from packageurl import ValidationMessage
        from packageurl import ValidationSeverity

        if "_" in purl.name:
            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Name cannot contain underscores for purl type:{cls.type!r}",
            )
        messages = super().validate_using_type_rules(purl, strict)
        if messages:
            yield from messages


class HexTypeDefinition(BasePurlType):
    type = "hex"
    type_name = "Hex"
    description = """Hex packages"""
    use_repository = True
    default_repository_url = "https://repo.hex.pm"
    namespace_requirement = "optional"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:hex/.*"


class HuggingfaceTypeDefinition(BasePurlType):
    type = "huggingface"
    type_name = "HuggingFace models"
    description = """Hugging Face ML models"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = True
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:huggingface/.*"


class LuarocksTypeDefinition(BasePurlType):
    type = "luarocks"
    type_name = "LuaRocks"
    description = """Lua packages installed with LuaRocks"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "optional"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:luarocks/.*"


class MavenTypeDefinition(BasePurlType):
    type = "maven"
    type_name = "Maven"
    description = """PURL type for Maven JARs and related artifacts."""
    use_repository = True
    default_repository_url = "https://repo.maven.apache.org/maven2/"
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url", "type", "classifier"}
    namespace_case_sensitive = True
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:maven/.*"


class MlflowTypeDefinition(BasePurlType):
    type = "mlflow"
    type_name = ""
    description = """MLflow ML models (Azure ML, Databricks, etc.)"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url", "run_id", "model_uuid"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:mlflow/.*"


class NpmTypeDefinition(BasePurlType):
    type = "npm"
    type_name = "Node NPM packages"
    description = """PURL type for npm packages."""
    use_repository = True
    default_repository_url = "https://registry.npmjs.org/"
    namespace_requirement = "optional"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:npm/.*"


class NugetTypeDefinition(BasePurlType):
    type = "nuget"
    type_name = "NuGet"
    description = """NuGet .NET packages"""
    use_repository = True
    default_repository_url = "https://www.nuget.org"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:nuget/.*"


class OciTypeDefinition(BasePurlType):
    type = "oci"
    type_name = "OCI image"
    description = """For artifacts stored in registries that conform to the OCI Distribution Specification https://github.com/opencontainers/distribution-spec including container images built by Docker and others"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url", "tag", "arch"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:oci/.*"


class PubTypeDefinition(BasePurlType):
    type = "pub"
    type_name = "Pub"
    description = """Dart and Flutter pub packages"""
    use_repository = True
    default_repository_url = "https://pub.dartlang.org"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:pub/.*"

    @classmethod
    def validate_using_type_rules(cls, purl, strict=False):
        from packageurl import ValidationMessage
        from packageurl import ValidationSeverity

        if not all(c.isalnum() or c == "_" for c in purl.name):
            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Name contains invalid characters but should only contain letters, digits, or underscores for purl type: {cls.type!r}",
            )

        if " " in purl.name:
            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Name contains spaces but should use underscores instead for purl type: {cls.type!r}",
            )
        messages = super().validate_using_type_rules(purl, strict)
        if messages:
            yield from messages


class PypiTypeDefinition(BasePurlType):
    type = "pypi"
    type_name = "PyPI"
    description = """Python packages"""
    use_repository = True
    default_repository_url = "https://pypi.org"
    namespace_requirement = "prohibited"
    allowed_qualifiers = {"file_name", "repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:pypi/.*"

    @classmethod
    def validate_using_type_rules(cls, purl, strict=False):
        from packageurl import ValidationMessage
        from packageurl import ValidationSeverity

        if "_" in purl.name:
            yield ValidationMessage(
                severity=ValidationSeverity.WARNING,
                message=f"Name cannot contain underscores for purl type:{cls.type!r}",
            )
        messages = super().validate_using_type_rules(purl, strict)
        if messages:
            yield from messages


class QpkgTypeDefinition(BasePurlType):
    type = "qpkg"
    type_name = "QNX package"
    description = """QNX packages"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = False
    name_case_sensitive = False
    version_case_sensitive = True
    purl_pattern = "pkg:qpkg/.*"


class RpmTypeDefinition(BasePurlType):
    type = "rpm"
    type_name = "RPM"
    description = """RPM packages"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url", "arch", "epoch"}
    namespace_case_sensitive = False
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:rpm/.*"


class SwidTypeDefinition(BasePurlType):
    type = "swid"
    type_name = "Software Identification (SWID) Tag"
    description = """PURL type for ISO-IEC 19770-2 Software Identification (SWID) tags."""
    use_repository = False
    default_repository_url = ""
    namespace_requirement = "optional"
    allowed_qualifiers = {"tag_creator_name", "tag_creator_regid", "tag_version", "tag_id", "patch"}
    namespace_case_sensitive = True
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:swid/.*"


class SwiftTypeDefinition(BasePurlType):
    type = "swift"
    type_name = "Swift packages"
    description = """Swift packages"""
    use_repository = True
    default_repository_url = ""
    namespace_requirement = "required"
    allowed_qualifiers = {"repository_url"}
    namespace_case_sensitive = True
    name_case_sensitive = True
    version_case_sensitive = True
    purl_pattern = "pkg:swift/.*"


DEFINITIONS_BY_TYPE = {
    "alpm": AlpmTypeDefinition,
    "apk": ApkTypeDefinition,
    "bitbucket": BitbucketTypeDefinition,
    "bitnami": BitnamiTypeDefinition,
    "cargo": CargoTypeDefinition,
    "cocoapods": CocoapodsTypeDefinition,
    "composer": ComposerTypeDefinition,
    "conan": ConanTypeDefinition,
    "conda": CondaTypeDefinition,
    "cpan": CpanTypeDefinition,
    "cran": CranTypeDefinition,
    "deb": DebTypeDefinition,
    "docker": DockerTypeDefinition,
    "gem": GemTypeDefinition,
    "generic": GenericTypeDefinition,
    "github": GithubTypeDefinition,
    "golang": GolangTypeDefinition,
    "hackage": HackageTypeDefinition,
    "hex": HexTypeDefinition,
    "huggingface": HuggingfaceTypeDefinition,
    "luarocks": LuarocksTypeDefinition,
    "maven": MavenTypeDefinition,
    "mlflow": MlflowTypeDefinition,
    "npm": NpmTypeDefinition,
    "nuget": NugetTypeDefinition,
    "oci": OciTypeDefinition,
    "pub": PubTypeDefinition,
    "pypi": PypiTypeDefinition,
    "qpkg": QpkgTypeDefinition,
    "rpm": RpmTypeDefinition,
    "swid": SwidTypeDefinition,
    "swift": SwiftTypeDefinition,
}
