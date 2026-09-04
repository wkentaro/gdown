"""Stand-ins for the yt-dlp internals that the vendored cookie module imports.

Each name mirrors the upstream call shape closely enough for the extracted
code; nothing here is used by gdown directly.
"""

# Signatures follow upstream, so the house annotation rules do not apply here.
# ruff: noqa: ANN401, B006

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any
from typing import Final

try:
    import sqlite3
except ImportError:  # Python built without sqlite support
    sqlite3 = None  # ty: ignore[invalid-assignment]


def _probe_secretstorage() -> tuple[Any, str | None]:
    try:
        import secretstorage  # noqa: PLC0415  # ty: ignore[unresolved-import]
    except ImportError:
        return None, (
            "as the `secretstorage` module is not installed. "
            "Please install by running `python3 -m pip install secretstorage`"
        )
    except Exception as err:  # noqa: BLE001
        return None, f"as the `secretstorage` module could not be initialized. {err}"
    return secretstorage, None


secretstorage, _SECRETSTORAGE_UNAVAILABLE_REASON = _probe_secretstorage()


class Cryptodome:
    # Without pycryptodomex the vendored AES takes its pure-Python path.
    AES: Final = None


class DownloadError(Exception):
    pass


class Popen(subprocess.Popen):  # type: ignore[type-arg]
    @classmethod
    def run(
        cls, *args: Any, timeout: float | None = None, **kwargs: Any
    ) -> tuple[Any, Any, int | None]:
        text = kwargs.get("text") or kwargs.get("universal_newlines")
        if text:
            kwargs.setdefault("encoding", "utf-8")
            kwargs.setdefault("errors", "replace")
        with cls(*args, **kwargs) as proc:
            stdout, stderr = proc.communicate(timeout=timeout)
        default = "" if text else b""
        return stdout or default, stderr or default, proc.returncode


class _YDLLogger:
    def __init__(self, *, ydl: object = None) -> None:
        self._ydl = ydl

    def debug(self, message: str, /) -> None:
        pass

    def info(self, message: str, /) -> None:
        pass

    def warning(self, message: str, /, *, once: bool = False) -> None:
        pass

    def error(self, message: str, /, *, is_error: bool = True) -> None:
        pass


class MultilinePrinter:
    def __init__(
        self,
        stream: object = None,
        /,
        *,
        lines: int = 1,
        preserve_output: bool = True,
    ) -> None:
        pass

    def __enter__(self) -> MultilinePrinter:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def print_at_line(self, text: str, pos: int, /) -> None:
        pass


class QuietMultilinePrinter(MultilinePrinter):
    pass


def compat_ord(c: int | bytes | str, /) -> int:
    return c if isinstance(c, int) else ord(c)


def error_to_str(err: BaseException, /) -> str:
    return f"{type(err).__name__}: {err}"


def is_path_like(f: object, /) -> bool:
    return isinstance(f, str | bytes | os.PathLike)


def str_or_none(v: object, /, *, default: str | None = None) -> str | None:
    return default if v is None else str(v)


def try_call(
    *funcs: Any,
    expected_type: type | None = None,
    args: list[Any] = [],
    kwargs: dict[str, Any] = {},
) -> Any:
    for f in funcs:
        try:
            val = f(*args, **kwargs)
        except (
            AttributeError,
            KeyError,
            TypeError,
            IndexError,
            ValueError,
            ZeroDivisionError,
        ):
            pass
        else:
            if expected_type is None or isinstance(val, expected_type):
                return val
    return None


def write_string(s: str, /, *, out: Any = None, encoding: str | None = None) -> None:  # noqa: ARG001
    out = out or sys.stderr
    if out:
        out.write(s)
        out.flush()


# The cookie jar's URL helpers are never called by gdown, so no normalization.
def normalize_url(url: str, /) -> str:
    return url


def sanitize_url(url: str, /) -> str:
    return url
