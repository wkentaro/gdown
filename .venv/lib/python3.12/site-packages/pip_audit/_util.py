"""
Utility functions for `pip-audit`.
"""

import sys
from typing import NoReturn  # pragma: no cover

from packaging.version import Version


def assert_never(x: NoReturn) -> NoReturn:  # pragma: no cover
    """
    A hint to the typechecker that a branch can never occur.
    """
    raise AssertionError(f"unhandled type: {type(x).__name__}")


def python_version() -> Version:
    """
    Return a PEP-440-style version for the current Python interpreter.

    This is more rigorous than `platform.python_version`, which can include
    non-PEP-440-compatible data.
    """
    info = sys.version_info
    return Version(f"{info.major}.{info.minor}.{info.micro}")
