"""
Tests for codeecho.normalizer.

:author: Ron Webb
:since: 1.0.0
"""

import pytest

from codeecho.normalizer import extract_and_normalise, extract_tokens, get_profile
from codeecho.parser import get_language, parse


@pytest.mark.parametrize("lang", ["Python", "JavaScript", "Java", "Go"])
def test_get_profile_known(lang):
    profile = get_profile(lang)
    assert len(profile.identifier_types) > 0


def test_get_profile_unknown_returns_empty():
    profile = get_profile("COBOL")
    assert profile.identifier_types == frozenset()
    assert profile.literal_types == frozenset()


def test_extract_tokens_python():
    src = b"def foo():\n    return 1\n"
    tree = parse(src, "Python")
    assert tree is not None
    func_node = tree.root_node.children[0]
    tokens = extract_tokens(func_node, src)
    assert "def" in tokens
    assert "foo" in tokens
    assert "return" in tokens


def test_normalise_replaces_identifiers():
    src = b"def greet(name):\n    return name\n"
    tree = parse(src, "Python")
    assert tree is not None
    func_node = tree.root_node.children[0]
    raw, norm = extract_and_normalise(func_node, src, "Python")
    # Raw tokens should contain actual names
    assert "greet" in raw
    assert "name" in raw
    # Normalised tokens must NOT contain the actual identifier names
    assert "greet" not in norm
    assert "name" not in norm
    # Placeholders must be present
    assert any(t.startswith("ID_") for t in norm)


def test_normalise_same_structure_different_names():
    """Two functions with identical structure but different names → same normalised sequence."""
    src_a = b"def foo(x):\n    return x + 1\n"
    src_b = b"def bar(y):\n    return y + 1\n"
    tree_a = parse(src_a, "Python")
    tree_b = parse(src_b, "Python")
    assert tree_a is not None and tree_b is not None
    node_a = tree_a.root_node.children[0]
    node_b = tree_b.root_node.children[0]
    _, norm_a = extract_and_normalise(node_a, src_a, "Python")
    _, norm_b = extract_and_normalise(node_b, src_b, "Python")
    assert norm_a == norm_b


def test_normalise_different_structure():
    """Functions with different bodies → different normalised sequences."""
    src_a = b"def foo(x):\n    return x + 1\n"
    src_b = b"def foo(x):\n    x = x * 2\n    return x\n"
    tree_a = parse(src_a, "Python")
    tree_b = parse(src_b, "Python")
    assert tree_a is not None and tree_b is not None
    node_a = tree_a.root_node.children[0]
    node_b = tree_b.root_node.children[0]
    _, norm_a = extract_and_normalise(node_a, src_a, "Python")
    _, norm_b = extract_and_normalise(node_b, src_b, "Python")
    assert norm_a != norm_b


def test_normalise_literal_replaced():
    src = b"def foo():\n    x = 42\n    return x\n"
    tree = parse(src, "Python")
    assert tree is not None
    func_node = tree.root_node.children[0]
    _, norm = extract_and_normalise(func_node, src, "Python")
    assert "42" not in norm
    assert any(t.startswith("LIT_") for t in norm)
