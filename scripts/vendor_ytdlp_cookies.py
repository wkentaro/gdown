"""Regenerate gdown/_vendor/_ytdlp_cookies.py from a pinned yt-dlp release.

Copies only the symbols reachable from the roots below, so the vendored file
is a mechanical extraction: never edit it by hand, rerun this instead.
yt-dlp is released under the Unlicense (public domain).

Usage: uv run python scripts/vendor_ytdlp_cookies.py [TAG]
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import sys
import urllib.request
from typing import Final

TAG: Final = "2026.08.19"
# Relative-import module name -> path inside the yt-dlp repository.
MODULES: Final = {"cookies": "yt_dlp/cookies.py", "aes": "yt_dlp/aes.py"}
ROOTS: Final = ["extract_cookies_from_browser", "SUPPORTED_BROWSERS"]
SHIM_IMPORT: Final = "from ._ytdlp_shim import"
OUT: Final = (
    pathlib.Path(__file__).resolve().parents[1] / "gdown/_vendor/_ytdlp_cookies.py"
)


class Module:
    def __init__(self, *, name: str, source: str) -> None:
        self.name = name
        self.lines = source.splitlines(keepends=True)
        self.body = ast.parse(source).body
        self.defs: dict[str, ast.stmt] = {}
        # bound name -> (relative module or None, upstream name, import node)
        self.imports: dict[str, tuple[str | None, str, ast.stmt]] = {}
        for node in self.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                module = None
                if isinstance(node, ast.ImportFrom) and node.level > 0:
                    module = node.module
                for alias in node.names:
                    bound = (alias.asname or alias.name).split(".")[0]
                    self.imports[bound] = (module, alias.name, node)
            else:
                for bound in _names_bound_by(node=node):
                    self.defs[bound] = node


def _names_bound_by(*, node: ast.AST) -> list[str]:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return [node.name]
    if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)]
    if isinstance(node, ast.Import | ast.ImportFrom):
        return [(a.asname or a.name).split(".")[0] for a in node.names]
    names: list[str] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt):
            names.extend(_names_bound_by(node=child))
        elif isinstance(child, ast.ExceptHandler):
            for stmt in child.body:
                names.extend(_names_bound_by(node=stmt))
    return names


def _names_used_by(*, node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _source_of(*, module: Module, node: ast.stmt) -> str:
    start = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
    assert node.end_lineno is not None
    return "".join(module.lines[start - 1 : node.end_lineno])


def fetch_modules(*, tag: str) -> dict[str, Module]:
    modules = {}
    for name, path in MODULES.items():
        url = f"https://raw.githubusercontent.com/yt-dlp/yt-dlp/{tag}/{path}"
        with urllib.request.urlopen(url) as response:
            modules[name] = Module(name=name, source=response.read().decode())
    return modules


def collect_closure(
    *,
    modules: dict[str, Module],
) -> tuple[dict[str, list[ast.stmt]], set[str], set[str]]:
    kept: dict[str, list[ast.stmt]] = {name: [] for name in modules}
    seen: set[tuple[str, int]] = set()
    stdlib_imports: set[str] = set()
    shim_names: set[str] = set()
    pending = [("cookies", root) for root in ROOTS]
    while pending:
        module_name, symbol = pending.pop()
        module = modules[module_name]
        if symbol in module.defs:
            node = module.defs[symbol]
            if (module_name, id(node)) in seen:
                continue
            seen.add((module_name, id(node)))
            kept[module_name].append(node)
            pending.extend((module_name, used) for used in _names_used_by(node=node))
        elif symbol in module.imports:
            relative_module, upstream_name, node = module.imports[symbol]
            if relative_module is None:
                stdlib_imports.add(_source_of(module=module, node=node))
            elif relative_module in modules:
                pending.append((relative_module, upstream_name))
            else:
                shim_names.add(symbol)
    return kept, stdlib_imports, shim_names


def render(
    *,
    tag: str,
    modules: dict[str, Module],
    kept: dict[str, list[ast.stmt]],
    stdlib_imports: set[str],
    shim_names: set[str],
) -> str:
    bound: dict[str, str] = {}
    for module_name, nodes in kept.items():
        for node in nodes:
            for name in _names_bound_by(node=node):
                if bound.get(name, module_name) != module_name:
                    raise SystemExit(
                        f"{name} is defined in both {bound[name]} and {module_name}"
                    )
                bound[name] = module_name
    header = (
        f"# Generated by scripts/vendor_ytdlp_cookies.py from yt-dlp {tag}.\n"
        "# Do not edit; rerun the script to upgrade.\n"
        "# yt-dlp is public domain (Unlicense).\n"
        "# ruff: noqa\n"
        "# fmt: off\n"
    )
    shim = f"{SHIM_IMPORT} ({', '.join(sorted(shim_names))})\n"
    sections = []
    for module_name in MODULES:
        module = modules[module_name]
        nodes = sorted(kept[module_name], key=lambda n: n.lineno)
        sections.append(f"# ---- from yt_dlp/{module_name}.py ----\n")
        sections.extend(_source_of(module=module, node=node) for node in nodes)
    return (
        header
        + "\n"
        + "".join(sorted(stdlib_imports))
        + "\n"
        + shim
        + "\n\n"
        + "\n\n".join(sections)
    )


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else TAG
    modules = fetch_modules(tag=tag)
    kept, stdlib_imports, shim_names = collect_closure(modules=modules)
    OUT.write_text(
        render(
            tag=tag,
            modules=modules,
            kept=kept,
            stdlib_imports=stdlib_imports,
            shim_names=shim_names,
        )
    )
    print(f"wrote {OUT.relative_to(OUT.parents[2])}")
    shim = importlib.import_module("gdown._vendor._ytdlp_shim")
    missing = sorted(shim_names - set(dir(shim)))
    if missing:
        raise SystemExit(f"add to gdown/_vendor/_ytdlp_shim.py: {', '.join(missing)}")


if __name__ == "__main__":
    main()
