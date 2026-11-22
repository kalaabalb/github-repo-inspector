"""Parse declared dependencies from common manifest files.

Everything here is static text parsing: nothing is installed, resolved or run.
Parsers are tolerant. A malformed manifest yields no dependencies rather than an
error, so one bad file never breaks a report.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable, Mapping
from pathlib import PurePosixPath

from app.schemas.analysis import Dependency

MAX_DEPENDENCIES_PER_FILE = 200
MAX_DEPENDENCIES_TOTAL = 500

_DEV_GROUP_NAMES = {"dev", "test", "tests", "lint", "docs", "typing", "ci", "build"}


def parse_dependencies(contents: Mapping[str, str]) -> list[Dependency]:
    """Parse every recognised manifest in ``contents`` (path -> text)."""
    found: list[Dependency] = []
    seen: set[tuple[str, str, str]] = set()
    for path in sorted(contents):
        parser = _parser_for(path)
        if parser is None:
            continue
        try:
            parsed = parser(contents[path], path)
        except Exception:  # noqa: BLE001 - malformed manifests must never fail a report
            continue
        for dependency in parsed[:MAX_DEPENDENCIES_PER_FILE]:
            key = (dependency.ecosystem, dependency.name, dependency.source)
            if key in seen:
                continue
            seen.add(key)
            found.append(dependency)
            if len(found) >= MAX_DEPENDENCIES_TOTAL:
                return found
    return found


def _parser_for(path: str) -> Callable[[str, str], list[Dependency]] | None:
    name = PurePosixPath(path).name.lower()
    if name == "package.json":
        return _parse_package_json
    if name == "pubspec.yaml":
        return _parse_pubspec
    if name == "pyproject.toml":
        return _parse_pyproject
    if name == "cargo.toml":
        return _parse_cargo
    if name == "go.mod":
        return _parse_go_mod
    if name == "composer.json":
        return _parse_composer
    if name.startswith("requirements") and name.endswith(".txt"):
        return _parse_requirements
    return None


def _dep(name: str, version: str | None, ecosystem: str, kind: str, source: str) -> Dependency:
    cleaned = (version or "").strip() or None
    return Dependency(name=name, version=cleaned, ecosystem=ecosystem, kind=kind, source=source)  # type: ignore[arg-type]


# --- Python -----------------------------------------------------------------

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


def _parse_pep508(requirement: str) -> tuple[str, str | None] | None:
    requirement = requirement.split(";", 1)[0].split("#", 1)[0].strip()
    if not requirement or requirement.startswith(("-", ".", "/")):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", requirement):  # a bare URL, not a package
        return None
    match = _REQ_NAME.match(requirement)
    if not match:
        return None
    name = match.group(1).lower()
    rest = match.group(3).strip()
    if rest.startswith("@"):  # direct reference, no version
        return name, None
    return name, rest or None


def _parse_requirements(text: str, source: str) -> list[Dependency]:
    kind = "dev" if re.search(r"dev|test", PurePosixPath(source).name.lower()) else "runtime"
    result = []
    for line in text.splitlines():
        parsed = _parse_pep508(line)
        if parsed:
            result.append(_dep(parsed[0], parsed[1], "PyPI", kind, source))
    return result


def _group_kind(group: str) -> str:
    return "dev" if group.lower() in _DEV_GROUP_NAMES else "optional"


def _parse_pyproject(text: str, source: str) -> list[Dependency]:
    data = tomllib.loads(text)
    result: list[Dependency] = []

    def add_requirements(items: object, kind: str) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, str):
                parsed = _parse_pep508(item)
                if parsed:
                    result.append(_dep(parsed[0], parsed[1], "PyPI", kind, source))

    project = data.get("project", {})
    add_requirements(project.get("dependencies"), "runtime")
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group, items in optional.items():
            add_requirements(items, _group_kind(group))
    groups = data.get("dependency-groups", {})
    if isinstance(groups, dict):
        for group, items in groups.items():
            add_requirements(items, "dev" if group.lower() in _DEV_GROUP_NAMES else "optional")

    poetry = data.get("tool", {}).get("poetry", {})

    def add_poetry(table: object, kind: str) -> None:
        if not isinstance(table, dict):
            return
        for name, spec in table.items():
            if name.lower() == "python":
                continue
            version = spec if isinstance(spec, str) else (spec.get("version") if isinstance(spec, dict) else None)
            result.append(_dep(name.lower(), version if isinstance(version, str) else None, "PyPI", kind, source))

    add_poetry(poetry.get("dependencies"), "runtime")
    add_poetry(poetry.get("dev-dependencies"), "dev")
    poetry_groups = poetry.get("group", {})
    if isinstance(poetry_groups, dict):
        for group, table in poetry_groups.items():
            if isinstance(table, dict):
                add_poetry(table.get("dependencies"), "dev" if group.lower() in _DEV_GROUP_NAMES else "optional")
    return result


# --- JavaScript -------------------------------------------------------------

def _parse_package_json(text: str, source: str) -> list[Dependency]:
    data = json.loads(text)
    if not isinstance(data, dict):
        return []
    result = []
    for key, kind in (
        ("dependencies", "runtime"),
        ("devDependencies", "dev"),
        ("peerDependencies", "optional"),
        ("optionalDependencies", "optional"),
    ):
        table = data.get(key)
        if isinstance(table, dict):
            for name, version in table.items():
                result.append(_dep(str(name), version if isinstance(version, str) else None, "npm", kind, source))
    return result


def _parse_composer(text: str, source: str) -> list[Dependency]:
    data = json.loads(text)
    if not isinstance(data, dict):
        return []
    result = []
    for key, kind in (("require", "runtime"), ("require-dev", "dev")):
        table = data.get(key)
        if isinstance(table, dict):
            for name, version in table.items():
                if name == "php" or str(name).startswith("ext-"):
                    continue
                result.append(_dep(str(name), version if isinstance(version, str) else None, "Packagist", kind, source))
    return result


# --- Dart / Flutter ---------------------------------------------------------

def _parse_pubspec(text: str, source: str) -> list[Dependency]:
    """Read the ``dependencies`` and ``dev_dependencies`` blocks without a YAML library."""
    sections = {"dependencies": "runtime", "dev_dependencies": "dev"}
    result: list[Dependency] = []
    current: str | None = None
    last_index: int | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0:
            key = stripped.rstrip(":").strip() if stripped.endswith(":") else None
            current = key if key in sections else None
            last_index = None
            continue
        if current is None:
            continue
        if indent <= 2:
            name, _, value = stripped.partition(":")
            name, value = name.strip(), value.strip().strip("'\"")
            if not name:
                continue
            result.append(_dep(name, value or None, "pub", sections[current], source))
            last_index = len(result) - 1
        elif last_index is not None:
            nested_key, _, nested_value = stripped.partition(":")
            nested_key, nested_value = nested_key.strip(), nested_value.strip().strip("'\"")
            previous = result[last_index]
            if previous.version is None and nested_key in {"sdk", "path", "git", "version", "url"} and nested_value:
                label = nested_value if nested_key == "version" else f"{nested_key}: {nested_value}"
                result[last_index] = previous.model_copy(update={"version": label})
    return result


# --- Rust / Go --------------------------------------------------------------

def _parse_cargo(text: str, source: str) -> list[Dependency]:
    data = tomllib.loads(text)
    result = []
    for key, kind in (
        ("dependencies", "runtime"),
        ("dev-dependencies", "dev"),
        ("build-dependencies", "dev"),
    ):
        table = data.get(key)
        if isinstance(table, dict):
            for name, spec in table.items():
                version = spec if isinstance(spec, str) else (spec.get("version") if isinstance(spec, dict) else None)
                result.append(_dep(str(name), version if isinstance(version, str) else None, "crates.io", kind, source))
    return result


def _parse_go_mod(text: str, source: str) -> list[Dependency]:
    result = []
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        entry = None
        if in_block:
            entry = line
        elif line.startswith("require ") and "(" not in line:
            entry = line[len("require "):].strip()
        if not entry or entry.startswith("//"):
            continue
        indirect = "// indirect" in entry
        parts = entry.split("//", 1)[0].split()
        if len(parts) >= 2 and not indirect:
            result.append(_dep(parts[0], parts[1], "Go", "runtime", source))
    return result
