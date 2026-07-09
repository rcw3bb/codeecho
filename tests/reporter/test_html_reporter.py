"""
Tests for codeecho.reporter.html_reporter.

:author: Ron Webb
:since: 1.0.0
"""

from codeecho.models import CloneGroup, Fragment, ScanResult
from codeecho.reporter import html_reporter


def _seed_db(session_db, session_id):
    frag = Fragment(
        fragment_id="fa",
        session_id=session_id,
        file_path="/src/a.py",
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=5,
        token_count=8,
        raw_hash="hash_x",
        normalized_hash="norm_x",
        token_sequence=["def", "foo"],
        source_text="def foo():\n    pass\n",
    )
    frag_b = Fragment(
        fragment_id="fb",
        session_id=session_id,
        file_path="/src/b.py",
        language="Python",
        fragment_type="function",
        start_line=10,
        end_line=14,
        token_count=8,
        raw_hash="hash_x",
        normalized_hash="norm_x",
        token_sequence=["def", "foo"],
        source_text="def foo():\n    pass\n",
    )
    session_db.insert_many_fragments([frag, frag_b])
    group = CloneGroup(
        group_id="g1",
        session_id=session_id,
        clone_type=1,
        representative_hash="hash_x",
        member_fragment_ids=["fa", "fb"],
    )
    session_db.insert_clone_group(group)


def test_html_report_created(session_db, session_id, tmp_path):
    _seed_db(session_db, session_id)
    result = ScanResult(
        session_id=session_id,
        scan_path="/src",
        files_scanned=2,
        fragments_extracted=2,
        type1_groups=1,
        type2_groups=0,
        type3_groups=0,
    )
    out = tmp_path / "report.html"
    html_reporter.write(session_db, result, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "CodeEcho" in content
    assert "Type-1" in content


def test_html_contains_source(session_db, session_id, tmp_path):
    _seed_db(session_db, session_id)
    result = ScanResult(
        session_id=session_id,
        scan_path="/src",
        files_scanned=2,
        fragments_extracted=2,
        type1_groups=1,
        type2_groups=0,
        type3_groups=0,
    )
    out = tmp_path / "report.html"
    html_reporter.write(session_db, result, out)
    content = out.read_text(encoding="utf-8")
    assert "def foo" in content or "def foo" in content
