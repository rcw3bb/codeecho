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
    root: Path,
    exclude_patterns: tuple[str, ...] = (),
    ignore_file: IgnoreFile | None = None,
) -> list[tuple[Path, str]]:
    """Walk *root* recursively and return ``(path, language)`` pairs for supported files.

    :param root: Root directory to scan.
    :param exclude_patterns: Glob patterns (fnmatch-style) whose matching paths are skipped.
    :param ignore_file: Optional gitignore-style :class:`~braincraft.IgnoreFile`; matched paths are skipped.
    :returns: List of ``(absolute_path, language_name)`` tuples.
    """
    results: list[tuple[Path, str]] = []
    root = root.resolve()
    _logger.debug("Scanning root: %s", root)

    for entry in _walk(root, exclude_patterns, ignore_file):
        suffix = entry.suffix.lower()
        if language := EXTENSION_TO_LANGUAGE.get(suffix):
            results.append((entry, language))

    _logger.info("Found %d source files under %s", len(results), root)
    return results


def _walk(
    root: Path,
    exclude_patterns: tuple[str, ...],
    ignore_file: IgnoreFile | None,
) -> list[Path]:
    """Recursively yield file paths, skipping excluded directories and glob-matched files."""
    found: list[Path] = []
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
                found.extend(_walk(child, exclude_patterns, ignore_file))
            elif child.is_file():
                if _matches_any(child, exclude_patterns):
                    continue
                if ignore_file is not None and ignore_file.is_ignored(child):
                    _logger.debug("Ignored (ignore file): %s", child)
                    continue
                found.append(child)
    except PermissionError as exc:
        _logger.warning("Permission denied reading %s: %s", root, exc)
    return found


def _matches_any(path: Path, patterns: tuple[str, ...]) -> bool:
    """Return True if *path* matches any of the given fnmatch-style *patterns*."""
    path_str = str(path)
    return any(fnmatch.fnmatch(path_str, p) for p in patterns)
