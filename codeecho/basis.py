"""
Basis-file resolution and clone-group filtering for ``--basis`` scans.

A "basis" is a user-supplied subset of the scanned files that acts as the reference
source for duplicate detection: clone groups are filtered down to only those that
touch at least one basis file, and groups whose members are *all* basis files are
flagged as ``basis_internal`` (duplication found purely among the basis files).

:author: Ron Webb
:since: 1.2.0
"""

from pathlib import Path

from .models import CloneGroup, Fragment


def _matches_relative_suffix(file_path: Path, relative_target: Path) -> bool:
    """Return True when *file_path*'s trailing path segments equal *relative_target*.

    Comparison is case-insensitive so a bare filename like ``IInfuser.gs`` matches
    the file regardless of the casing baked into either path.

    :since: 1.2.0
    """
    rel_parts = relative_target.parts
    file_parts = file_path.parts
    if len(rel_parts) > len(file_parts):
        return False
    tail = file_parts[len(file_parts) - len(rel_parts) :]
    return tuple(p.casefold() for p in tail) == tuple(p.casefold() for p in rel_parts)


def resolve_basis_files(
    discovered: list[tuple[Path, str]], basis_targets: list[Path]
) -> frozenset[str]:
    """Return the resolved file paths from *discovered* that fall under *basis_targets*.

    An absolute basis target matches a discovered file that equals it exactly, or that
    lies inside it (when it's a directory). A relative basis target (e.g. a bare
    filename like ``IInfuser.gs``, or a partial path like ``sub/File.gs``) instead
    matches any discovered file whose trailing path segments equal it, wherever that
    file lives within the scanned tree.

    :param discovered: ``(path, language)`` pairs as returned by :func:`codeecho.scanner.scan`.
    :param basis_targets: Basis file/directory paths read from the ``--basis`` file;
        absolute entries are resolved, relative entries are kept as-is.
    :returns: Frozen set of matching file paths (as strings, matching :attr:`Fragment.file_path`).
    :since: 1.2.0
    """
    absolute_targets = [p for p in basis_targets if p.is_absolute()]
    relative_targets = [p for p in basis_targets if not p.is_absolute()]
    basis_dirs = [p for p in absolute_targets if p.is_dir()]
    basis_files = {p for p in absolute_targets if p.is_file()}

    matched: set[str] = set()
    for file_path, _ in discovered:
        if file_path in basis_files or any(
            file_path.is_relative_to(d) for d in basis_dirs
        ):
            matched.add(str(file_path))
        elif any(_matches_relative_suffix(file_path, rel) for rel in relative_targets):
            matched.add(str(file_path))
    return frozenset(matched)


def filter_groups_for_basis(
    groups_with_members: list[tuple[CloneGroup, list[Fragment]]],
    basis_files: frozenset[str],
) -> list[tuple[CloneGroup, list[Fragment], bool]]:
    """Keep only groups touching a basis file, flagging groups that are basis-only.

    :param groups_with_members: ``(group, members)`` pairs for every detected clone group.
    :param basis_files: Resolved basis file paths, as returned by :func:`resolve_basis_files`.
    :returns: ``(group, members, basis_internal)`` triples for groups with >=1 basis member.
    :since: 1.2.0
    """
    result: list[tuple[CloneGroup, list[Fragment], bool]] = []
    for group, members in groups_with_members:
        member_is_basis = [m.file_path in basis_files for m in members]
        if not any(member_is_basis):
            continue
        result.append((group, members, all(member_is_basis)))
    return result


def count_basis_groups_by_type(
    groups_with_members: list[tuple[CloneGroup, list[Fragment]]],
    basis_files: frozenset[str],
) -> dict[int, int]:
    """Count basis-touching clone groups per clone type (1, 2, 3).

    :param groups_with_members: ``(group, members)`` pairs for every detected clone group.
    :param basis_files: Resolved basis file paths, as returned by :func:`resolve_basis_files`.
    :returns: Mapping of clone type to the number of basis-touching groups of that type.
    :since: 1.2.0
    """
    counts: dict[int, int] = {1: 0, 2: 0, 3: 0}
    for group, _, _ in filter_groups_for_basis(groups_with_members, basis_files):
        counts[group.clone_type] = counts.get(group.clone_type, 0) + 1
    return counts
