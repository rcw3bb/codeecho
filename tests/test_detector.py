"""
Tests for codeecho.detector.

:author: Ron Webb
:since: 1.0.0
"""

from codeecho.detector import (
    _is_nested,
    _jaccard,
    detect,
)  # pylint: disable=protected-access
from codeecho.models import Fragment


def _make_frag(
    fid: str,
    session_id: str,
    raw_hash: str,
    norm_hash: str,
    tokens: list[str] | None = None,
    file_path: str = "/f.py",
    start_line: int = 1,
    end_line: int = 5,
    fragment_type: str = "function",
) -> Fragment:
    frag = Fragment(
        fragment_id=fid,
        session_id=session_id,
        file_path=file_path,
        language="Python",
        fragment_type=fragment_type,
        start_line=start_line,
        end_line=end_line,
        token_count=len(tokens or []),
        raw_hash=raw_hash,
        normalized_hash=norm_hash,
        token_sequence=tokens or [],
    )
    return frag


def test_jaccard_identical():
    assert _jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_jaccard_disjoint():
    assert _jaccard(["a", "b"], ["c", "d"]) == 0.0


def test_jaccard_partial():
    score = _jaccard(["a", "b", "c"], ["b", "c", "d"])
    assert 0.0 < score < 1.0


def test_jaccard_empty():
    assert _jaccard([], []) == 0.0


def test_detect_type1(session_db, session_id):
    frags = [
        _make_frag("f1", session_id, "hash_x", "norm_x"),
        _make_frag("f2", session_id, "hash_x", "norm_x"),
        _make_frag("f3", session_id, "hash_y", "norm_y"),
    ]
    session_db.insert_many_fragments(frags)
    cnt1, cnt2, cnt3 = detect(session_db, session_id, {1}, threshold=0.8)
    assert cnt1 == 1  # f1 and f2 share hash_x
    assert cnt2 == 0
    assert cnt3 == 0
    groups = session_db.get_clone_groups(session_id)
    assert len(groups) == 1
    assert groups[0].clone_type == 1
    assert set(groups[0].member_fragment_ids) == {"f1", "f2"}


def test_detect_type2(session_db, session_id):
    frags = [
        _make_frag("f1", session_id, "raw_a", "norm_x"),
        _make_frag("f2", session_id, "raw_b", "norm_x"),  # different raw, same norm
        _make_frag("f3", session_id, "raw_c", "norm_c"),
    ]
    session_db.insert_many_fragments(frags)
    cnt1, cnt2, cnt3 = detect(session_db, session_id, {1, 2}, threshold=0.8)
    assert cnt1 == 0
    assert cnt2 == 1  # f1 and f2 share norm_x
    assert cnt3 == 0


def test_detect_type3(session_db, session_id):
    tokens_a = ["def", "foo", "(", "x", ")", ":", "return", "x", "+", "1"]
    tokens_b = [
        "def",
        "foo",
        "(",
        "x",
        ")",
        ":",
        "return",
        "x",
        "+",
        "2",
    ]  # 1 token differs
    frags = [
        _make_frag("f1", session_id, "raw_a", "norm_a", tokens_a, file_path="/a.py"),
        _make_frag("f2", session_id, "raw_b", "norm_b", tokens_b, file_path="/b.py"),
    ]
    session_db.insert_many_fragments(frags)
    cnt1, cnt2, cnt3 = detect(session_db, session_id, {3}, threshold=0.5)
    assert cnt3 >= 1  # The two similar functions should form a Type-3 group


def test_detect_no_duplicates(session_db, session_id):
    frags = [
        _make_frag("f1", session_id, "h1", "n1", ["a", "b"]),
        _make_frag("f2", session_id, "h2", "n2", ["c", "d"]),
    ]
    session_db.insert_many_fragments(frags)
    cnt1, cnt2, cnt3 = detect(session_db, session_id, {1, 2, 3}, threshold=0.8)
    assert cnt1 == 0
    assert cnt2 == 0
    assert cnt3 == 0


# ── _is_nested tests ──────────────────────────────────────────────────────────


def _nested_frag(fid: str, file_path: str, start: int, end: int) -> Fragment:
    return Fragment(
        fragment_id=fid,
        session_id="s",
        file_path=file_path,
        language="Java",
        fragment_type="function",
        start_line=start,
        end_line=end,
        token_count=1,
    )


def test_is_nested_parent_contains_child():
    parent = _nested_frag("p", "/Main.java", 40, 45)
    child = _nested_frag("c", "/Main.java", 41, 44)
    assert _is_nested(parent, child) is True
    assert _is_nested(child, parent) is True


def test_is_nested_same_range():
    a = _nested_frag("a", "/Main.java", 10, 20)
    b = _nested_frag("b", "/Main.java", 10, 20)
    assert _is_nested(a, b) is True


def test_is_nested_different_files():
    a = _nested_frag("a", "/A.java", 1, 10)
    b = _nested_frag("b", "/B.java", 1, 10)
    assert _is_nested(a, b) is False


def test_is_nested_overlapping_not_contained():
    a = _nested_frag("a", "/Main.java", 1, 10)
    b = _nested_frag("b", "/Main.java", 8, 15)
    assert _is_nested(a, b) is False


def test_detect_type3_skips_nested_fragments(session_db, session_id):
    """A method nested inside a class in the same file must not form a Type-3 group."""
    shared_tokens = [
        "public",
        "class",
        "Main",
        "{",
        "public",
        "static",
        "void",
        "main",
        "}",
        "}",
    ]
    frags = [
        _make_frag(
            "cls",
            session_id,
            "raw_cls",
            "norm_cls",
            tokens=shared_tokens,
            file_path="/Main.java",
            start_line=40,
            end_line=45,
            fragment_type="class",
        ),
        _make_frag(
            "fn",
            session_id,
            "raw_fn",
            "norm_fn",
            tokens=shared_tokens[3:9],  # subset — simulates nested method
            file_path="/Main.java",
            start_line=41,
            end_line=44,
            fragment_type="function",
        ),
    ]
    session_db.insert_many_fragments(frags)
    _, _, cnt3 = detect(session_db, session_id, {3}, threshold=0.5)
    assert cnt3 == 0  # nested pair must be excluded


def test_detect_type3_removes_container_via_transitivity(session_db, session_id):
    """A 'file' fragment containing a 'class' from the same file must be dropped from a group
    even when both independently reach similarity threshold with a fragment from another file.
    """
    shared_tokens = [
        "class",
        "ShapeFactory",
        "{",
        "IShape",
        "createShape",
        "circle",
        "rectangle",
        "}",
    ]
    frags = [
        # Similar class in a different file — the "real" clone
        _make_frag(
            "other_cls",
            session_id,
            "raw_o",
            "norm_o",
            tokens=shared_tokens,
            file_path="/factory2/Main.java",
            start_line=25,
            end_line=38,
            fragment_type="class",
        ),
        # 'file' fragment containing the class below (outer/container)
        _make_frag(
            "sf_file",
            session_id,
            "raw_f",
            "norm_f",
            tokens=["package", "xyz"] + shared_tokens,
            file_path="/factory/ShapeFactory.java",
            start_line=1,
            end_line=17,
            fragment_type="file",
        ),
        # 'class' fragment nested inside sf_file (inner/specific)
        _make_frag(
            "sf_cls",
            session_id,
            "raw_c",
            "norm_c",
            tokens=shared_tokens,
            file_path="/factory/ShapeFactory.java",
            start_line=3,
            end_line=16,
            fragment_type="class",
        ),
    ]
    session_db.insert_many_fragments(frags)
    _, _, cnt3 = detect(session_db, session_id, {3}, threshold=0.5)
    groups = session_db.get_clone_groups(session_id)
    assert cnt3 == 1
    # The group must contain the inner class, not the outer file fragment
    assert len(groups[0].member_fragment_ids) == 2
    assert "sf_file" not in groups[0].member_fragment_ids
    assert "sf_cls" in groups[0].member_fragment_ids
    assert "other_cls" in groups[0].member_fragment_ids
