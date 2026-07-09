"""
Fragment extractor: uses Tree-sitter queries to locate functions, classes, and file blocks.

For each matched AST node, the extractor builds a :class:`~codeecho.models.Fragment` with
raw and normalised token sequences, source text, and line numbers.

:author: Ron Webb
:since: 1.0.0
"""

import logging
import uuid
from bisect import bisect_left
from pathlib import Path

from tree_sitter import Language, Query, QueryCursor, Tree

from . import normalizer
from .models import Fragment
from .parser import get_language

_logger = logging.getLogger("codeecho.extractor")

# ── Per-language fragment queries ──────────────────────────────────────────────
# Patterns are keyed by (language_name, fragment_type).
# Multiple node types are expressed as alternation: [(a) (b)] @fragment
_QUERIES: dict[tuple[str, str], str] = {
    ("Python", "function"): "(function_definition) @fragment",
    ("Python", "class"): "(class_definition) @fragment",
    ("Python", "file"): "(module) @fragment",
    (
        "JavaScript",
        "function",
    ): "[(function_declaration) (function_expression) (arrow_function)] @fragment",
    ("JavaScript", "class"): "(class_declaration) @fragment",
    ("JavaScript", "file"): "(program) @fragment",
    (
        "TypeScript",
        "function",
    ): "[(function_declaration) (function_expression) (arrow_function)] @fragment",
    ("TypeScript", "class"): "(class_declaration) @fragment",
    ("TypeScript", "file"): "(program) @fragment",
    ("Java", "function"): "[(method_declaration) (constructor_declaration)] @fragment",
    ("Java", "class"): "(class_declaration) @fragment",
    ("Java", "file"): "(program) @fragment",
    ("Gosu", "function"): "[(method_declaration) (constructor_declaration)] @fragment",
    ("Gosu", "class"): "(class_declaration) @fragment",
    ("Gosu", "file"): "(program) @fragment",
    ("Go", "function"): "[(function_declaration) (method_declaration)] @fragment",
    ("Go", "class"): "(type_declaration) @fragment",
    ("Go", "file"): "(source_file) @fragment",
}

# NOTE: Query objects are NOT cached — tree-sitter 0.26 Query instances carry internal
# cursor state that becomes stale when reused across different Tree objects.
_FRAGMENT_TYPES: tuple[str, ...] = ("function", "class", "file")


def _get_query(language_name: str, fragment_type: str, lang: Language) -> Query | None:
    """Return a fresh :class:`tree_sitter.Query` for *language_name* / *fragment_type*."""
    pattern = _QUERIES.get((language_name, fragment_type))
    if pattern is None:
        return None
    try:
        return Query(lang, pattern)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _logger.warning(
            "Failed to compile query %s/%s: %s", language_name, fragment_type, exc
        )
        return None


def extract_fragments(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    tree: Tree,
    source_bytes: bytes,
    file_path: Path,
    language_name: str,
    session_id: str,
    min_tokens: int = 10,
) -> list[Fragment]:
    """Extract all fragment types from *tree* and return a list of populated :class:`Fragment` objects.

    :param tree: Parsed tree-sitter tree for the file.
    :param source_bytes: Raw UTF-8 source bytes of the file.
    :param file_path: Absolute path of the source file.
    :param language_name: Language name (e.g. ``"Python"``).
    :param session_id: UUID of the current scan session.
    :param min_tokens: Fragments with fewer raw tokens are discarded.
    :returns: List of fully-populated :class:`Fragment` objects.
    """
    lang = get_language(language_name)
    if lang is None:
        return []

    fragments: list[Fragment] = []
    # Pre-compute sorted list of newline byte offsets for O(log n) line lookups.
    newline_offsets: list[int] = [
        i for i, b in enumerate(source_bytes) if b == ord(b"\n")
    ]
    for ftype in _FRAGMENT_TYPES:
        query = _get_query(language_name, ftype, lang)
        if query is None:
            continue
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        # Eagerly extract ONLY byte ranges from nodes before cursor is freed.
        # Do NOT access node.start_point / node.end_point — tree-sitter 0.26
        # returns corrupted row values for some captured nodes.
        node_ranges: list[tuple[int, int]] = [
            (n.start_byte, n.end_byte) for n in captures.get("fragment", [])
        ]
        del cursor, captures  # free tree-sitter objects before processing
        for start_b, end_b in node_ranges:
            src_text = source_bytes[start_b:end_b].decode("utf-8", errors="replace")
            raw_tokens, norm_tokens = normalizer.tokenise_and_normalise(
                src_text, language_name
            )
            if len(raw_tokens) < min_tokens:
                continue
            start_ln = bisect_left(newline_offsets, start_b) + 1
            end_ln = bisect_left(newline_offsets, end_b) + 1
            fragments.append(
                Fragment(
                    fragment_id=str(uuid.uuid4()),
                    session_id=session_id,
                    file_path=str(file_path),
                    language=language_name,
                    fragment_type=ftype,
                    start_line=start_ln,
                    end_line=end_ln,
                    token_count=len(raw_tokens),
                    token_sequence=raw_tokens,
                    normalized_tokens=norm_tokens,
                    source_text=src_text,
                )
            )

    _logger.debug("Extracted %d fragments from %s", len(fragments), file_path.name)
    return fragments
