"""
File-system scanner that discovers source files for clone detection.

:author: Ron Webb
:since: 1.0.0
"""

import fnmatch
import logging
from pathlib import Path

from braincraft import IgnoreFile

_logger = logging.getLogger("codeecho.scanner")

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".gs": "Gosu",
    ".gsx": "Gosu",
}

_DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        "target",
        "out",
        ".tox",
        ".pytest_cache",
        "htmlcov",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def scan(
    paths: tuple[Path, ...],
    exclude_patterns: tuple[str, ...] = (),
    ignore_file: IgnoreFile | None = None,
) -> list[tuple[Path, str]]:
    """Walk *paths* and return ``(path, language)`` pairs for supported source files.

    Each entry in *paths* may be a file or a directory.  Directories are walked
    recursively; files are checked for a supported extension and included directly.
    Duplicate resolved paths across multiple entries are silently deduplicated.

    :param paths: One or more file or directory paths to scan.
    :param exclude_patterns: Glob patterns (fnmatch-style) whose matching paths are skipped.
    :param ignore_file: Optional gitignore-style :class:`~braincraft.IgnoreFile`; matched paths are skipped.
    :returns: List of ``(absolute_path, language_name)`` tuples.
    """
    results: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    for path in paths:
        path = path.resolve()
        _logger.debug("Scanning: %s", path)
        if path.is_file():
            if path in seen or _matches_any(path, exclude_patterns):
                continue
            seen.add(path)
            if ignore_file is not None and ignore_file.is_ignored(path):
                _logger.debug("Ignored (ignore file): %s", path)
                continue
            if language := EXTENSION_TO_LANGUAGE.get(path.suffix.lower()):
                results.append((path, language))
        elif path.is_dir():
            for entry in _walk(path, exclude_patterns, ignore_file):
                if entry not in seen:
                    seen.add(entry)
                    if language := EXTENSION_TO_LANGUAGE.get(entry.suffix.lower()):
                        results.append((entry, language))

    _logger.debug("Found %d source files across %d path(s)", len(results), len(paths))
    return results


def _walk(
    root: Path,
    exclude_patterns: tuple[str, ...],
    ignore_file: IgnoreFile | None,
):
    """Recursively collect file paths, skipping excluded directories and glob-matched files."""
    try:
        for child in sorted(root.iterdir()):
            if child.is_dir():
                if child.name in _DEFAULT_EXCLUDE_DIRS:
                    continue
                if _matches_any(child, exclude_patterns):
                    continue
                if ignore_file is not None and ignore_file.is_ignored(child):
                    _logger.debug("Ignored (ignore file): %s", child)
                    continue
                yield from _walk(child, exclude_patterns, ignore_file)
            elif child.is_file():
                if _matches_any(child, exclude_patterns):
                    continue
                if ignore_file is not None and ignore_file.is_ignored(child):
                    _logger.debug("Ignored (ignore file): %s", child)
                    continue
                yield child
    except PermissionError as exc:
        _logger.warning("Permission denied reading %s: %s", root, exc)


def _matches_any(path: Path, patterns: tuple[str, ...]) -> bool:
    """Return True if *path* matches any of the given fnmatch-style *patterns*."""
    path_str = str(path)
    return any(fnmatch.fnmatch(path_str, p) for p in patterns)
