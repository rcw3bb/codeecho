"""
Token extraction and Type-2 normalisation for code fragments.

Tokens are extracted from the raw fragment source text using a language-aware
regex-based tokeniser.  This avoids direct tree-sitter AST node traversal,
which is unstable across tree-sitter 0.26+ Python bindings.

Identifiers and literals are replaced with sequential placeholders
(``ID_0``, ``ID_1``, ``LIT_0``, …) so that two fragments with the same structure
but different variable names still produce the same normalised token sequence.

:author: Ron Webb
:since: 1.0.0
"""

import re
import logging
from dataclasses import dataclass, field

from tree_sitter import Node

_logger = logging.getLogger("codeecho.normalizer")


@dataclass
class NormalisationProfile:
    """Language-specific sets of identifier and literal node types."""

    identifier_types: frozenset[str] = field(default_factory=frozenset)
    literal_types: frozenset[str] = field(default_factory=frozenset)


_PROFILES: dict[str, NormalisationProfile] = {
    "Python": NormalisationProfile(
        identifier_types=frozenset({"identifier", "type_identifier"}),
        literal_types=frozenset(
            {"string", "integer", "float", "true", "false", "none"}
        ),
    ),
    "JavaScript": NormalisationProfile(
        identifier_types=frozenset(
            {"identifier", "property_identifier", "shorthand_property_identifier"}
        ),
        literal_types=frozenset(
            {"string", "number", "true", "false", "null", "template_string"}
        ),
    ),
    "TypeScript": NormalisationProfile(
        identifier_types=frozenset(
            {
                "identifier",
                "property_identifier",
                "type_identifier",
                "shorthand_property_identifier",
            }
        ),
        literal_types=frozenset(
            {"string", "number", "true", "false", "null", "template_string"}
        ),
    ),
    "Java": NormalisationProfile(
        identifier_types=frozenset({"identifier", "type_identifier"}),
        literal_types=frozenset(
            {
                "string_literal",
                "decimal_integer_literal",
                "decimal_floating_point_literal",
                "true",
                "false",
                "null_literal",
            }
        ),
    ),
    "Gosu": NormalisationProfile(
        identifier_types=frozenset({"identifier", "type_identifier"}),
        literal_types=frozenset(
            {
                "string_literal",
                "decimal_integer_literal",
                "decimal_floating_point_literal",
                "true",
                "false",
                "null_literal",
            }
        ),
    ),
    "Go": NormalisationProfile(
        identifier_types=frozenset(
            {"identifier", "type_identifier", "field_identifier"}
        ),
        literal_types=frozenset(
            {
                "interpreted_string_literal",
                "raw_string_literal",
                "int_literal",
                "float_literal",
                "true",
                "false",
                "nil",
            }
        ),
    ),
}

_FALLBACK_PROFILE: NormalisationProfile = NormalisationProfile()


# ── Regex-based tokeniser ───────────────────────────────────────────────────
# Matches identifiers/keywords, number literals, quoted strings, and single
# non-whitespace characters (operators, punctuation).
_TOKEN_RE: re.Pattern = re.compile(
    r'"(?:[^"\\]|\\.)*"'  # double-quoted string
    r"|'(?:[^'\\]|\\.)*'"  # single-quoted string
    r"|`(?:[^`\\]|\\.)*`"  # backtick string (JS/Go)
    r"|//[^\n]*"  # single-line comment
    r"|/\*.*?\*/"  # multi-line comment (non-greedy)
    r"|[0-9]+(?:\.[0-9]+)?"  # integer or float literal
    r"|[a-zA-Z_$][a-zA-Z0-9_$]*"  # identifier / keyword
    r"|[^\s]",  # any other single non-whitespace char
    re.DOTALL,
)

# Per-language keyword sets used to distinguish identifiers from keywords
_KEYWORDS: dict[str, frozenset[str]] = {
    "Python": frozenset(
        {
            "False",
            "None",
            "True",
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        }
    ),
    "JavaScript": frozenset(
        {
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "default",
            "delete",
            "do",
            "else",
            "export",
            "extends",
            "false",
            "finally",
            "for",
            "function",
            "if",
            "import",
            "in",
            "instanceof",
            "let",
            "new",
            "null",
            "return",
            "static",
            "super",
            "switch",
            "this",
            "throw",
            "true",
            "try",
            "typeof",
            "undefined",
            "var",
            "void",
            "while",
            "with",
            "yield",
        }
    ),
    "TypeScript": frozenset(
        {
            "abstract",
            "any",
            "as",
            "asserts",
            "async",
            "await",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "declare",
            "default",
            "delete",
            "do",
            "else",
            "enum",
            "export",
            "extends",
            "false",
            "finally",
            "for",
            "from",
            "function",
            "if",
            "implements",
            "import",
            "in",
            "infer",
            "instanceof",
            "interface",
            "is",
            "keyof",
            "let",
            "module",
            "namespace",
            "never",
            "new",
            "null",
            "of",
            "override",
            "private",
            "protected",
            "public",
            "readonly",
            "return",
            "satisfies",
            "static",
            "super",
            "switch",
            "this",
            "throw",
            "true",
            "try",
            "type",
            "typeof",
            "undefined",
            "unique",
            "unknown",
            "var",
            "void",
            "while",
            "with",
            "yield",
        }
    ),
    "Java": frozenset(
        {
            "abstract",
            "assert",
            "boolean",
            "break",
            "byte",
            "case",
            "catch",
            "char",
            "class",
            "const",
            "continue",
            "default",
            "do",
            "double",
            "else",
            "enum",
            "extends",
            "final",
            "finally",
            "float",
            "for",
            "goto",
            "if",
            "implements",
            "import",
            "instanceof",
            "int",
            "interface",
            "long",
            "native",
            "new",
            "null",
            "package",
            "private",
            "protected",
            "public",
            "return",
            "short",
            "static",
            "strictfp",
            "super",
            "switch",
            "synchronized",
            "this",
            "throw",
            "throws",
            "transient",
            "true",
            "try",
            "var",
            "void",
            "volatile",
            "while",
        }
    ),
    "Gosu": frozenset(
        {
            "abstract",
            "as",
            "assert",
            "block",
            "break",
            "case",
            "catch",
            "class",
            "classpath",
            "continue",
            "default",
            "do",
            "else",
            "enum",
            "erases",
            "eval",
            "exists",
            "extends",
            "false",
            "final",
            "finally",
            "for",
            "foreach",
            "function",
            "hiding",
            "if",
            "implements",
            "import",
            "in",
            "index",
            "interface",
            "new",
            "null",
            "override",
            "package",
            "property",
            "protected",
            "public",
            "readonly",
            "return",
            "static",
            "super",
            "switch",
            "this",
            "throw",
            "throws",
            "transient",
            "true",
            "try",
            "unless",
            "using",
            "var",
            "void",
            "where",
            "while",
        }
    ),
    "Go": frozenset(
        {
            "break",
            "case",
            "chan",
            "const",
            "continue",
            "default",
            "defer",
            "else",
            "fallthrough",
            "false",
            "for",
            "func",
            "go",
            "goto",
            "if",
            "import",
            "interface",
            "map",
            "nil",
            "package",
            "range",
            "return",
            "select",
            "struct",
            "switch",
            "true",
            "type",
            "var",
        }
    ),
}

# Patterns that indicate the token is a string/number literal
_STRING_RE: re.Pattern = re.compile(r'^["\'\`]|^[0-9]')


def get_profile(language_name: str) -> NormalisationProfile:
    """Return the :class:`NormalisationProfile` for *language_name*, falling back to empty sets."""
    return _PROFILES.get(language_name, _FALLBACK_PROFILE)


def _tokenise_text(text: str) -> list[str]:
    """Split *text* into a list of raw tokens using :data:`_TOKEN_RE`."""
    return _TOKEN_RE.findall(text)


def tokenise_and_normalise(
    text: str, language_name: str
) -> tuple[list[str], list[str]]:
    """Return ``(raw_tokens, normalised_tokens)`` for a fragment source *text* string.

    :param text: Raw fragment source text (UTF-8 decoded).
    :param language_name: Language whose keyword set governs normalisation.
    :returns: Raw token list and normalised token list where identifiers become
              ``ID_N`` and literals become ``LIT_N``.
    """
    raw_tokens = _tokenise_text(text)
    keywords = _KEYWORDS.get(language_name, frozenset())
    return raw_tokens, _normalise(raw_tokens, keywords)


def extract_tokens(node: Node, source_bytes: bytes) -> list[str]:
    """Return a flat list of raw tokens for the source text covered by *node*.

    Uses a regex-based tokeniser on the raw source slice — no tree traversal.
    """
    text = source_bytes[node.start_byte : node.end_byte].decode(
        "utf-8", errors="replace"
    )
    return _tokenise_text(text)


def extract_and_normalise(
    node: Node, source_bytes: bytes, language_name: str
) -> tuple[list[str], list[str]]:
    """Return ``(raw_tokens, normalised_tokens)`` for the source covered by *node*.

    :param node: Tree-sitter node; only its byte range is used (no child traversal).
    :param source_bytes: Full source bytes of the file.
    :param language_name: Language whose keyword set governs normalisation.
    :returns: Raw token list and normalised token list where identifiers become
              ``ID_N`` and literals become ``LIT_N``.
    """
    text = source_bytes[node.start_byte : node.end_byte].decode(
        "utf-8", errors="replace"
    )
    return tokenise_and_normalise(text, language_name)


def _normalise(raw_tokens: list[str], keywords: frozenset[str]) -> list[str]:
    """Build a normalised token list from *raw_tokens* using *keywords* for classification."""
    norm_tokens: list[str] = []
    id_map: dict[str, str] = {}
    lit_count = 0

    for token in raw_tokens:
        if _is_comment(token):
            continue  # skip comments
        if _is_identifier(token) and token not in keywords:
            placeholder = id_map.setdefault(token, f"ID_{len(id_map)}")
            norm_tokens.append(placeholder)
        elif _STRING_RE.match(token):
            norm_tokens.append(f"LIT_{lit_count}")
            lit_count += 1
        else:
            norm_tokens.append(token)

    return norm_tokens


def _is_identifier(token: str) -> bool:
    """Return True if *token* looks like an identifier (letter/underscore start)."""
    return bool(token) and (token[0].isalpha() or token[0] == "_")


def _is_comment(token: str) -> bool:
    """Return True if *token* is a single-line or multi-line comment."""
    return token.startswith("//") or (token.startswith("/*") and token.endswith("*/"))
