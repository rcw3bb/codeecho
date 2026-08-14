"""
Tests for codeecho.reporter.json_reporter.

:author: Ron Webb
:since: 1.0.0
"""

import json

from codeecho.models import CloneGroup, Fragment, ScanResult
from codeecho.reporter import json_reporter


def _seed_db(session_db, session_id):
    frag_a = Fragment(
        fragment_id="fa",
        session_id=session_id,
        file_path="/src/a.py",
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=5,
        token_count=10,
        raw_hash="hash_x",
        normalized_hash="norm_x",
        token_sequence=["def", "foo"],
        source_text="def foo():\n    pass\n",
    )
    frag_b = frag_a.__class__(
        fragment_id="fb",
        session_id=session_id,
        file_path="/src/b.py",
        language="Python",
        fragment_type="function",
        start_line=10,
        end_line=14,
        token_count=10,
        raw_hash="hash_x",
        normalized_hash="norm_x",
        token_sequence=["def", "foo"],
        source_text="def foo():\n    pass\n",
    )
    session_db.insert_many_fragments([frag_a, frag_b])
    group = CloneGroup(
        group_id="g1",
        session_id=session_id,
        clone_type=1,
        representative_hash="hash_x",
        member_fragment_ids=["fa", "fb"],
    )
    session_db.insert_clone_group(group)


def test_json_report_structure(session_db, session_id, tmp_path):
    _seed_db(session_db, session_id)
    result = ScanResult(
        session_id=session_id,
        version="1.0.0",
        scan_path=["/src"],
        files_scanned=2,
        fragments_extracted=2,
        type1_groups=1,
        type2_groups=0,
        type3_groups=0,
    )
    out = tmp_path / "report.json"
    json_reporter.write(session_db, result, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == "1.0.0"
    assert data["summary"]["files_scanned"] == 2
    assert data["summary"]["type1_groups"] == 1
    assert len(data["clone_groups"]) == 1
    group = data["clone_groups"][0]
    assert group["clone_type"] == 1
    assert len(group["members"]) == 2


def test_json_report_no_groups(session_db, session_id, tmp_path):
    result = ScanResult(
        session_id=session_id,
        version="1.0.0",
        scan_path=["/src"],
        files_scanned=0,
        fragments_extracted=0,
        type1_groups=0,
        type2_groups=0,
        type3_groups=0,
    )
    out = tmp_path / "empty.json"
    json_reporter.write(session_db, result, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["clone_groups"] == []
