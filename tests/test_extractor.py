"""
Tests for codeecho.extractor.

:author: Ron Webb
:since: 1.0.0
"""

from pathlib import Path

from codeecho.extractor import extract_fragments
from codeecho.parser import parse


def test_extract_python_functions():
    src = (
        b"def foo(x):\n    y = x + 1\n    z = y * 2\n    return z\n\n"
        b"def bar(y):\n    a = y + 1\n    b = a * 2\n    return b\n"
    )
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
    src = b"class Greeter:\n    def hello(self):\n        greeting = 'hi'\n        return greeting\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=1
    )
    class_frags = [f for f in frags if f.fragment_type == "class"]
    assert len(class_frags) == 1
    assert "class Greeter" in class_frags[0].source_text


def test_extract_min_tokens_filter():
    src = b"def small():\n    x = 1\n    return x\n"
    tree = parse(src, "Python")
    assert tree is not None
    # With a min_tokens threshold higher than the function's line count, it should be excluded
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=10
    )
    func_frags = [f for f in frags if f.fragment_type == "function"]
    assert len(func_frags) == 0


def test_extract_default_min_tokens_excludes_tiny_fragment():
    """Fragments spanning fewer lines than the default min_tokens are discarded."""
    src = b"def tiny():\n    return 1\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(tree, src, Path("test.py"), "Python", "sess-1")
    func_frags = [f for f in frags if f.fragment_type == "function"]
    assert len(func_frags) == 0


def test_extract_fragment_line_numbers():
    src = (
        b"x = 1\n\ndef greet(name):\n    prefix = 'hi'\n"
        b"    greeting = f'{prefix} {name}'\n    return greeting\n"
    )
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
    src = b"def foo():\n    x = 1\n    y = 2\n    return x + y\n"
    tree = parse(src, "Python")
    assert tree is not None
    frags = extract_fragments(
        tree, src, Path("test.py"), "Python", "sess-1", min_tokens=1
    )
    assert frags
    for frag in frags:
        assert frag.raw_hash is None
        assert frag.normalized_hash is None


def test_extract_java_method():
    src = (
        b"class Foo {\n    public int add(int a, int b) {\n"
        b"        int sum = a + b;\n        return sum;\n    }\n}\n"
    )
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
