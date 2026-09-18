import sys

from pip_api._vendor.packaging import version as packaging_version
from pip_api._vendor.packaging_legacy.version import LegacyVersion as Version

# Import this now because we need it below
from pip_api._version import version

PIP_VERSION: Version = packaging_version.parse(version())  # type: ignore
PYTHON_VERSION = sys.version_info

# Import these because they depend on the above
from pip_api._hash import hash
from pip_api._installed_distributions import installed_distributions

# Import these whenever, doesn't matter
from pip_api._parse_requirements import (
    Requirement,
    UnparsedRequirement,
    parse_requirements,
)
