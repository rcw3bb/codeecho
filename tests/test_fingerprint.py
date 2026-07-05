"""
Tests for codeecho.fingerprint.

:author: Ron Webb
:since: 1.0.0
"""

from codeecho.fingerprint import hash_all, hash_fragment
from codeecho.models import Fragment


def _make_fragment(
    fragment_id: str, raw_tokens: list[str], norm_tokens: list[str]
) -> Fragment:
    frag = Fragment(
        fragment_id=fragment_id,
        session_id="s1",
        file_path="/f.py",
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=5,
    )
    frag.token_sequence = raw_tokens
    frag.normalized_tokens = norm_tokens
    return frag


def test_hash_fragment_sets_hashes():
    frag = _make_fragment(
        "f1", ["def", "foo", ":", "pass"], ["def", "ID_0", ":", "pass"]
    )
    hash_fragment(frag)
    assert frag.raw_hash is not None
    assert frag.normalized_hash is not None
    assert len(frag.raw_hash) == 64  # SHA-256 hex
    assert frag.token_count == 4


def test_same_raw_tokens_same_hash():
    frag_a = _make_fragment("a", ["def", "foo"], ["def", "ID_0"])
    frag_b = _make_fragment("b", ["def", "foo"], ["def", "ID_0"])
    hash_fragment(frag_a)
    hash_fragment(frag_b)
    assert frag_a.raw_hash == frag_b.raw_hash


def test_different_raw_tokens_different_hash():
    frag_a = _make_fragment("a", ["def", "foo"], ["def", "ID_0"])
    frag_b = _make_fragment("b", ["def", "bar"], ["def", "ID_0"])
    hash_fragment(frag_a)
    hash_fragment(frag_b)
    assert frag_a.raw_hash != frag_b.raw_hash


def test_normalised_hash_same_for_renamed():
    """Same structure, different names → same normalized hash."""
    frag_a = _make_fragment(
        "a", ["def", "foo", "(", "x", ")"], ["def", "ID_0", "(", "ID_1", ")"]
    )
    frag_b = _make_fragment(
        "b", ["def", "bar", "(", "y", ")"], ["def", "ID_0", "(", "ID_1", ")"]
    )
    hash_fragment(frag_a)
    hash_fragment(frag_b)
    assert frag_a.normalized_hash == frag_b.normalized_hash
    assert frag_a.raw_hash != frag_b.raw_hash


def test_hash_all():
    frags = [
        _make_fragment("f1", ["a", "b"], ["a", "b"]),
        _make_fragment("f2", ["c", "d"], ["c", "d"]),
    ]
    hash_all(frags)
    for frag in frags:
        assert frag.raw_hash is not None
        assert frag.normalized_hash is not None
