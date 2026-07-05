"""
Tests for codeecho.extractor.

:author: Ron Webb
:since: 1.0.0
"""

from pathlib import Path

from codeecho.extractor import extract_fragments
from codeecho.parser import parse


def test_extract_python_functions():
    src = b"def foo(x):\n    return x + 1\n\ndef bar(y):\n    return y * 2\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=1
    )
    func_frags = [f for f in frags if f.fragment_type == "function"]
    assert len(func_frags) == 2
    names = {f.source_text.split("(")[0].strip() for f in func_frags}
    assert "def foo" in names
    assert "def bar" in names


def test_extract_python_class():
    src = b"class Greeter:\n    def hello(self):\n        return 'hi'\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=1
    )
    class_frags = [f for f in frags if f.fragment_type == "class"]
    assert len(class_frags) == 1
    assert "class Greeter" in class_frags[0].source_text


def test_extract_min_tokens_filter():
    src = b"def tiny():\n    pass\n"
    tree = parse(src, "Python")
    assert tree is not None
    # With a high min_tokens threshold, the tiny function should be excluded
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=100
    )
    func_frags = [f for f in frags if f.fragment_type == "function"]
    assert len(func_frags) == 0


def test_extract_fragment_line_numbers():
    src = b"x = 1\n\ndef greet(name):\n    return name\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=1
    )
    func_frags = [f for f in frags if f.fragment_type == "function"]
    assert len(func_frags) == 1
    assert func_frags[0].start_line == 3


def test_extract_hashes_not_set():
    """Extractor does not set hashes; fingerprint module is responsible."""
    src = b"def foo():\n    pass\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=1
    )
    for frag in frags:
        assert frag.raw_hash is None
        assert frag.normalized_hash is None


def test_extract_java_method():
    src = b"class Foo { public int add(int a, int b) { return a + b; } }"
    tree = parse(src, "Java")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("Foo.java"), "Java", "sess-1", min_tokens=1
    )
    func_frags = [f for f in frags if f.fragment_type == "function"]
    assert len(func_frags) == 1


def test_extract_unsupported_language(tmp_path):
    src = b"some code"
    # parse returns None for unsupported languages, but test extractor directly
    from codeecho.parser import (
        parse as ts_parse,
    )  # pylint: disable=import-outside-toplevel

    tree = ts_parse(src, "COBOL")
    assert tree is None
