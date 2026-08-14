"""
Tests for codeecho.models.

:author: Ron Webb
:since: 1.0.0
"""

from codeecho.models import CloneGroup, Fragment, ScanResult


def test_fragment_defaults():
    frag = Fragment(
        fragment_id="f1",
        session_id="s1",
        file_path="/a/b.py",
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=10,
    )
    assert frag.token_count == 0
    assert frag.raw_hash is None
    assert frag.normalized_hash is None
    assert frag.token_sequence == []
    assert frag.normalized_tokens == []
    assert frag.source_text == ""


def test_clone_group_defaults():
    group = CloneGroup(group_id="g1", session_id="s1", clone_type=1)
    assert group.representative_hash is None
    assert group.similarity_score is None
    assert group.member_fragment_ids == []


def test_scan_result_fields():
    result = ScanResult(
        session_id="s1",
        version="1.0.0",
        scan_path=["/root"],
        files_scanned=5,
        fragments_extracted=20,
        type1_groups=1,
        type2_groups=2,
        type3_groups=3,
    )
    assert result.files_scanned == 5
    assert result.type1_groups + result.type2_groups + result.type3_groups == 6
