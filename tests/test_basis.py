"""
Tests for codeecho.basis.

:author: Ron Webb
:since: 1.2.0
"""

from pathlib import Path

from codeecho.basis import (
    count_basis_groups_by_type,
    filter_groups_for_basis,
    resolve_basis_files,
)
from codeecho.models import CloneGroup, Fragment


def _frag(fragment_id: str, file_path: str) -> Fragment:
    return Fragment(
        fragment_id=fragment_id,
        session_id="s1",
        file_path=file_path,
        language="Python",
        fragment_type="function",
        start_line=1,
        end_line=5,
        token_count=10,
    )


# ---------------------------------------------------------------------------
# resolve_basis_files
# ---------------------------------------------------------------------------


def test_resolve_basis_files_matches_exact_file(tmp_path):
    """A discovered file matching a basis file target is included."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.touch()
    b.touch()
    discovered = [(a, "Python"), (b, "Python")]
    result = resolve_basis_files(discovered, [a])
    assert result == frozenset({str(a)})


def test_resolve_basis_files_matches_directory_containment(tmp_path):
    """A discovered file under a basis directory target is included."""
    basis_dir = tmp_path / "reference"
    basis_dir.mkdir()
    nested = basis_dir / "sub" / "c.py"
    nested.parent.mkdir(parents=True)
    outside = tmp_path / "other" / "d.py"
    outside.parent.mkdir(parents=True)
    discovered = [(nested, "Python"), (outside, "Python")]
    result = resolve_basis_files(discovered, [basis_dir])
    assert result == frozenset({str(nested)})


def test_resolve_basis_files_no_overlap_returns_empty(tmp_path):
    """No basis target matches any discovered file -> empty result."""
    a = tmp_path / "a.py"
    unrelated = tmp_path / "unrelated.py"
    discovered = [(a, "Python")]
    result = resolve_basis_files(discovered, [unrelated])
    assert result == frozenset()


def test_resolve_basis_files_relative_bare_filename_matches_anywhere(tmp_path):
    """A relative bare filename entry matches a file with that name anywhere in the scan."""
    nested = tmp_path / "some" / "deep" / "IInfuser.gs"
    nested.parent.mkdir(parents=True)
    other = tmp_path / "Other.gs"
    discovered = [(nested, "Gosu"), (other, "Gosu")]
    result = resolve_basis_files(discovered, [Path("IInfuser.gs")])
    assert result == frozenset({str(nested)})


def test_resolve_basis_files_relative_bare_filename_is_case_insensitive(tmp_path):
    """Relative filename matching ignores case differences."""
    nested = tmp_path / "src" / "IInfuser.gs"
    nested.parent.mkdir(parents=True)
    discovered = [(nested, "Gosu")]
    result = resolve_basis_files(discovered, [Path("iinfuser.GS")])
    assert result == frozenset({str(nested)})


def test_resolve_basis_files_relative_partial_path_matches_suffix(tmp_path):
    """A relative multi-segment entry matches only files with that trailing path."""
    match = tmp_path / "module" / "sub" / "File.gs"
    match.parent.mkdir(parents=True)
    no_match = tmp_path / "other" / "File.gs"
    no_match.parent.mkdir(parents=True)
    discovered = [(match, "Gosu"), (no_match, "Gosu")]
    result = resolve_basis_files(discovered, [Path("sub/File.gs")])
    assert result == frozenset({str(match)})


def test_resolve_basis_files_relative_entry_no_match_returns_empty(tmp_path):
    """A relative entry that matches no discovered file yields an empty result."""
    a = tmp_path / "a.py"
    discovered = [(a, "Python")]
    result = resolve_basis_files(discovered, [Path("missing.py")])
    assert result == frozenset()


# ---------------------------------------------------------------------------
# filter_groups_for_basis
# ---------------------------------------------------------------------------


def test_filter_groups_for_basis_drops_non_basis_groups():
    """Groups with no basis-file member are dropped entirely."""
    group = CloneGroup(group_id="g1", session_id="s1", clone_type=1)
    members = [_frag("f1", "/src/a.py"), _frag("f2", "/src/b.py")]
    result = filter_groups_for_basis([(group, members)], frozenset({"/basis/x.py"}))
    assert result == []


def test_filter_groups_for_basis_flags_mixed_group_as_not_internal():
    """A group with a basis member and a non-basis member is kept, basis_internal=False."""
    group = CloneGroup(group_id="g1", session_id="s1", clone_type=1)
    members = [_frag("f1", "/basis/a.py"), _frag("f2", "/src/b.py")]
    result = filter_groups_for_basis([(group, members)], frozenset({"/basis/a.py"}))
    assert len(result) == 1
    _, kept_members, basis_internal = result[0]
    assert kept_members == members
    assert basis_internal is False


def test_filter_groups_for_basis_flags_all_basis_group_as_internal():
    """A group whose members are all basis files is flagged basis_internal=True."""
    group = CloneGroup(group_id="g1", session_id="s1", clone_type=1)
    members = [_frag("f1", "/basis/a.py"), _frag("f2", "/basis/b.py")]
    basis_files = frozenset({"/basis/a.py", "/basis/b.py"})
    result = filter_groups_for_basis([(group, members)], basis_files)
    assert len(result) == 1
    _, _, basis_internal = result[0]
    assert basis_internal is True


# ---------------------------------------------------------------------------
# count_basis_groups_by_type
# ---------------------------------------------------------------------------


def test_count_basis_groups_by_type_counts_only_basis_touching_groups():
    """Only groups touching a basis file are counted, bucketed by clone_type."""
    basis_files = frozenset({"/basis/a.py"})
    g1 = CloneGroup(group_id="g1", session_id="s1", clone_type=1)
    g1_members = [_frag("f1", "/basis/a.py"), _frag("f2", "/src/b.py")]
    g2 = CloneGroup(group_id="g2", session_id="s1", clone_type=2)
    g2_members = [_frag("f3", "/basis/a.py"), _frag("f4", "/src/c.py")]
    g3 = CloneGroup(group_id="g3", session_id="s1", clone_type=1)
    g3_members = [_frag("f5", "/src/d.py"), _frag("f6", "/src/e.py")]
    counts = count_basis_groups_by_type(
        [(g1, g1_members), (g2, g2_members), (g3, g3_members)], basis_files
    )
    assert counts == {1: 1, 2: 1, 3: 0}


def test_count_basis_groups_by_type_empty_when_no_matches():
    """No basis-touching groups yields zero counts for every type."""
    group = CloneGroup(group_id="g1", session_id="s1", clone_type=3)
    members = [_frag("f1", "/src/a.py"), _frag("f2", "/src/b.py")]
    counts = count_basis_groups_by_type([(group, members)], frozenset({"/basis/x.py"}))
    assert counts == {1: 0, 2: 0, 3: 0}
