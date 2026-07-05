"""
Tests for codeecho.db (SessionDB).

:author: Ron Webb
:since: 1.0.0
"""

from codeecho.db import SessionDB
from codeecho.models import CloneGroup, Fragment


def _make_fragment(
    fragment_id: str, session_id: str, raw_hash: str = "abc"
) -> Fragment:
    return Fragment(
        fragment_id=fragment_id,
        session_id=session_id,
        file_path="/test/file.py",
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=5,
        token_count=10,
        raw_hash=raw_hash,
        normalized_hash="norm_" + raw_hash,
        token_sequence=["def", "foo", "(", ")", ":"],
        source_text="def foo():\n    pass\n",
    )


def test_create_and_delete_session(tmp_path):
    db_path = tmp_path / "test.db"
    session_id = "sess-001"
    with SessionDB(db_path=db_path) as sdb:
        sdb.create_session(session_id, "/root", {"types": "all"})
        frag = _make_fragment("f1", session_id)
        sdb.insert_many_fragments([frag])
        assert sdb.count_fragments(session_id) == 1
        sdb.delete_session(session_id)
        assert sdb.count_fragments(session_id) == 0


def test_insert_and_retrieve_fragments(session_db, session_id):
    frags = [_make_fragment(f"f{i}", session_id, raw_hash=f"hash{i}") for i in range(3)]
    session_db.insert_many_fragments(frags)
    retrieved = session_db.get_fragments(session_id)
    assert len(retrieved) == 3
    ids = {f.fragment_id for f in retrieved}
    assert ids == {"f0", "f1", "f2"}


def test_get_fragment_by_id(session_db, session_id):
    frag = _make_fragment("frag-x", session_id)
    session_db.insert_many_fragments([frag])
    found = session_db.get_fragment_by_id("frag-x")
    assert found is not None
    assert found.fragment_id == "frag-x"
    assert found.language == "Python"


def test_get_fragment_by_id_missing(session_db):
    assert session_db.get_fragment_by_id("nonexistent") is None


def test_insert_and_retrieve_clone_group(session_db, session_id):
    frag_a = _make_fragment("fa", session_id, "hash_a")
    frag_b = _make_fragment("fb", session_id, "hash_a")
    session_db.insert_many_fragments([frag_a, frag_b])

    group = CloneGroup(
        group_id="g1",
        session_id=session_id,
        clone_type=1,
        representative_hash="hash_a",
        member_fragment_ids=["fa", "fb"],
    )
    session_db.insert_clone_group(group)
    groups = session_db.get_clone_groups(session_id)
    assert len(groups) == 1
    assert groups[0].clone_type == 1
    assert set(groups[0].member_fragment_ids) == {"fa", "fb"}


def test_cascade_delete(tmp_path):
    db_path = tmp_path / "cascade.db"
    sid = "sess-cascade"
    with SessionDB(db_path=db_path) as sdb:
        sdb.create_session(sid, "/root", {})
        frags = [_make_fragment(f"f{i}", sid, f"h{i}") for i in range(2)]
        sdb.insert_many_fragments(frags)
        grp = CloneGroup(
            group_id="g1",
            session_id=sid,
            clone_type=1,
            member_fragment_ids=["f0", "f1"],
        )
        sdb.insert_clone_group(grp)
        # Delete session — cascade should remove fragments and groups
        sdb.delete_session(sid)
        assert sdb.count_fragments(sid) == 0
        assert sdb.get_clone_groups(sid) == []
