"""
Tree-sitter parser wrapper providing one cached :class:`tree_sitter.Parser` per language.

:author: Ron Webb
:since: 1.0.0
"""

import logging
from functools import lru_cache

from tree_sitter import Language, Parser, Tree

_logger = logging.getLogger("codeecho.parser")


def _build_language(  # pylint: disable=too-many-return-statements
    language_name: str,
) -> Language | None:
    """Instantiate and return the tree-sitter :class:`Language` for *language_name*.

    :since: 1.0.0
    """
    match language_name:
        case "Python":
            import tree_sitter_python as m  # pylint: disable=import-outside-toplevel

            return Language(m.language())
        case "JavaScript":
            import tree_sitter_javascript as m  # pylint: disable=import-outside-toplevel

            return Language(m.language())
        case "TypeScript" | "TSX":
            import tree_sitter_typescript as m  # pylint: disable=import-outside-toplevel

            return Language(m.language_typescript())
        case "Java":
            import tree_sitter_java as m  # pylint: disable=import-outside-toplevel

            return Language(m.language())
        case "Gosu":
            import tree_sitter_gosu as m  # pylint: disable=import-outside-toplevel

            return Language(m.language())
        case "Go":
            import tree_sitter_go as m  # pylint: disable=import-outside-toplevel

            return Language(m.language())
        case _:
            return None


@lru_cache(maxsize=None)
def get_language(language_name: str) -> Language | None:
    """Return a cached :class:`tree_sitter.Language` for *language_name*, or ``None`` on failure.

    :since: 1.0.0
    """
    try:
        lang = _build_language(language_name)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _logger.warning("Failed to load grammar for %s: %s", language_name, exc)
        return None
    if lang is None:
        _logger.warning("No tree-sitter grammar for language: %s", language_name)
    return lang


@lru_cache(maxsize=None)
def get_parser(language_name: str) -> Parser | None:
    """Return a cached :class:`tree_sitter.Parser` for *language_name*, or ``None`` on failure.

    .. note::
        The returned parser is NOT used directly for parsing; call :func:`parse` instead,
        which creates a fresh :class:`~tree_sitter.Parser` instance per call to avoid
        internal state corruption across files in tree-sitter 0.26+.

    :since: 1.0.0
    """
    lang = get_language(language_name)
    if lang is None:
        return None
    return Parser(lang)


def parse(source_bytes: bytes, language_name: str) -> Tree | None:
    """Parse *source_bytes* with the grammar for *language_name*.

    A new :class:`~tree_sitter.Parser` is created for each call so that the
    internal state of the C extension cannot carry over between files.

    :param source_bytes: UTF-8-encoded source code.
    :param language_name: Name as returned by :data:`codeecho.scanner.EXTENSION_TO_LANGUAGE`.
    :returns: Parsed :class:`tree_sitter.Tree`, or ``None`` if the grammar is unavailable.
    :since: 1.0.0
    """
    lang = get_language(language_name)
    if lang is None:
        _logger.warning("Skipping parse — no grammar for %s", language_name)
        return None
    fresh_parser = Parser(lang)
    tree = fresh_parser.parse(source_bytes)
    if tree.root_node.has_error:
        _logger.debug("Parse errors detected in %s source.", language_name)
    return tree
