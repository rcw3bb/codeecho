"""
Tests for codeecho.parser.

:author: Ron Webb
:since: 1.0.0
"""

import pytest

from codeecho.parser import get_language, get_parser, parse


@pytest.mark.parametrize(
    "lang", ["Python", "JavaScript", "TypeScript", "Java", "Go", "Gosu"]
)
def test_get_language_known(lang):
    assert get_language(lang) is not None


def test_get_language_gosu_is_distinct_from_java():
    gosu_lang = get_language("Gosu")
    java_lang = get_language("Java")
    assert gosu_lang is not None
    assert java_lang is not None
    assert gosu_lang is not java_lang


def test_get_language_unknown():
    assert get_language("COBOL") is None


def test_get_parser_known():
    assert get_parser("Python") is not None


def test_parse_python():
    src = b"def greet(name):\n    return f'Hello, {name}'\n"
    tree = parse(src, "Python")
    assert tree is not None
    assert tree.root_node.type == "module"


def test_parse_javascript():
    src = b"function add(a, b) { return a + b; }\n"
    tree = parse(src, "JavaScript")
    assert tree is not None


def test_parse_java():
    src = b"class Foo { public int bar(int x) { return x + 1; } }\n"
    tree = parse(src, "Java")
    assert tree is not None


def test_parse_unknown_language():
    assert parse(b"some code", "COBOL") is None
