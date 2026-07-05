"""
Tests for codeecho.detector.

:author: Ron Webb
:since: 1.0.0
"""

from codeecho.detector import _jaccard, detect  # pylint: disable=protected-access
from codeecho.models import Fragment


def _make_frag(
    fid: str,
    session_id: str,
    raw_hash: str,
    norm_hash: str,
    tokens: list[str] | None = None,
) -> Fragment:
    frag = Fragment(
        fragment_id=fid,
        session_id=session_id,
        file_path="/f.py",
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=5,
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
        _make_frag("f1", session_id, "raw_a", "norm_a", tokens_a),
        _make_frag("f2", session_id, "raw_b", "norm_b", tokens_b),
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
