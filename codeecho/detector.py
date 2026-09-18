"""
Clone detection engine: Type-1 (exact), Type-2 (renamed identifiers), Type-3 (near-duplicate).

Detection strategy
------------------
* **Type-1** – fragments sharing the same ``raw_hash`` are exact clones.
* **Type-2** – fragments sharing the same ``normalized_hash`` (but different ``raw_hash``) are
  structural clones with renamed identifiers / literals.
* **Type-3** – remaining fragments compared pairwise using Jaccard similarity on their token
  sets; pairs above *threshold* are grouped with a union-find algorithm.

:author: Ron Webb
:since: 1.0.0
"""

import logging
import uuid
from collections import defaultdict

from .db import SessionDB
from .models import CloneGroup, Fragment

_logger = logging.getLogger("codeecho.detector")

_MAX_SIZE_RATIO: float = 1.3


# ── Union-Find ──────────────────────────────────────────────────────────────


class _UnionFind:
    """Lightweight union-find (disjoint-set) for merging Type-3 candidate pairs."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, node: str) -> str:
        """Return the representative of *node*'s set (with path compression).

        :since: 1.0.0
        """
        if node not in self._parent:
            self._parent[node] = node
        if self._parent[node] != node:
            self._parent[node] = self.find(self._parent[node])
        return self._parent[node]

    def union(self, node_a: str, node_b: str) -> None:
        """Merge the sets containing *node_a* and *node_b*.

        :since: 1.0.0
        """
        root_a, root_b = self.find(node_a), self.find(node_b)
        if root_a != root_b:
            self._parent[root_a] = root_b

    def groups(self, members: list[str]) -> dict[str, list[str]]:
        """Return a mapping ``{representative: [member_ids]}`` for *members*.

        :since: 1.0.0
        """
        result: dict[str, list[str]] = defaultdict(list)
        for item in members:
            result[self.find(item)].append(item)
        return {k: v for k, v in result.items() if len(v) >= 2}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _jaccard(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Return the Jaccard similarity between two token lists (treated as sets).

    :since: 1.0.0
    """
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _make_group(
    session_id: str,
    clone_type: int,
    fragment_ids: list[str],
    rep_hash: str | None = None,
    similarity: float | None = None,
) -> CloneGroup:
    return CloneGroup(
        group_id=str(uuid.uuid4()),
        session_id=session_id,
        clone_type=clone_type,
        representative_hash=rep_hash,
        similarity_score=similarity,
        member_fragment_ids=fragment_ids,
    )


# ── Detection passes ─────────────────────────────────────────────────────────


def _detect_type1(
    fragments: list[Fragment], session_id: str
) -> tuple[list[CloneGroup], set[str]]:
    """Group fragments by raw hash.  Return groups and the set of assigned fragment IDs.

    :since: 1.0.0
    """
    by_hash: dict[str, list[str]] = defaultdict(list)
    for frag in fragments:
        if frag.raw_hash:
            by_hash[frag.raw_hash].append(frag.fragment_id)

    groups: list[CloneGroup] = []
    assigned: set[str] = set()
    for raw_hash, ids in by_hash.items():
        if len(ids) >= 2:
            groups.append(_make_group(session_id, 1, ids, rep_hash=raw_hash))
            assigned.update(ids)
    _logger.debug("Type-1: %d clone groups found.", len(groups))
    return groups, assigned


def _detect_type2(
    fragments: list[Fragment], assigned: set[str], session_id: str
) -> tuple[list[CloneGroup], set[str]]:
    """Group unassigned fragments by normalised hash.

    :since: 1.0.0
    """
    by_norm: dict[str, list[str]] = defaultdict(list)
    for frag in fragments:
        if frag.fragment_id not in assigned and frag.normalized_hash:
            by_norm[frag.normalized_hash].append(frag.fragment_id)

    groups: list[CloneGroup] = []
    new_assigned: set[str] = set()
    for norm_hash, ids in by_norm.items():
        if len(ids) >= 2:
            groups.append(_make_group(session_id, 2, ids, rep_hash=norm_hash))
            new_assigned.update(ids)
    _logger.debug("Type-2: %d clone groups found.", len(groups))
    return groups, new_assigned


def _is_nested(frag_a: Fragment, frag_b: Fragment) -> bool:
    """Return True when *frag_a* and *frag_b* are from the same file and one contains the other.

    :since: 1.0.1
    """
    if frag_a.file_path != frag_b.file_path:
        return False
    a_contains_b = (
        frag_a.start_line <= frag_b.start_line and frag_a.end_line >= frag_b.end_line
    )
    b_contains_a = (
        frag_b.start_line <= frag_a.start_line and frag_b.end_line >= frag_a.end_line
    )
    return a_contains_b or b_contains_a


def _compare_pair(
    frag_a: Fragment,
    frag_b: Fragment,
    threshold: float,
    union_find: "_UnionFind",
    pair_scores: dict[tuple[str, str], float],
) -> None:
    """Compare a single fragment pair and register a union if similarity >= threshold.

    :since: 1.0.0
    """
    if _is_nested(frag_a, frag_b):
        return
    count_a, count_b = frag_a.token_count, frag_b.token_count
    if (
        count_a == 0
        or count_b == 0
        or count_b / count_a > _MAX_SIZE_RATIO
        or count_a / count_b > _MAX_SIZE_RATIO
    ):
        return
    score = _jaccard(frag_a.token_sequence, frag_b.token_sequence)
    if score >= threshold:
        union_find.union(frag_a.fragment_id, frag_b.fragment_id)
        pair_scores[(frag_a.fragment_id, frag_b.fragment_id)] = score


def _remove_nested_members(
    member_ids: list[str], id_to_frag: dict[str, Fragment]
) -> list[str]:
    """Remove outer container fragments from a group that contain a nested same-file member.

    When a group contains two fragments from the same file where one's line range is fully
    contained within the other's, the outer (larger) fragment is removed — it is redundant
    because the inner fragment is the more specific code unit.

    :since: 1.0.1
    """
    to_remove: set[str] = set()
    ids = list(member_ids)
    for idx in range(len(ids)):  # pylint: disable=consider-using-enumerate
        for jdx in range(idx + 1, len(ids)):
            frag_a = id_to_frag[ids[idx]]
            frag_b = id_to_frag[ids[jdx]]
            if _is_nested(frag_a, frag_b):
                size_a = frag_a.end_line - frag_a.start_line
                size_b = frag_b.end_line - frag_b.start_line
                # Keep the more specific (smaller) fragment; drop the outer container
                to_remove.add(
                    frag_a.fragment_id if size_a >= size_b else frag_b.fragment_id
                )
    return [fid for fid in ids if fid not in to_remove]


def _detect_type3(
    fragments: list[Fragment],
    assigned: set[str],
    session_id: str,
    threshold: float,
) -> list[CloneGroup]:
    """Pairwise Jaccard comparison for remaining fragments; clusters via union-find.

    :since: 1.0.0
    """
    candidates = [
        f for f in fragments if f.fragment_id not in assigned and f.token_count > 0
    ]
    id_to_frag = {f.fragment_id: f for f in candidates}
    union_find = _UnionFind()
    pair_scores: dict[tuple[str, str], float] = {}

    for idx_a in range(len(candidates)):  # pylint: disable=consider-using-enumerate
        for idx_b in range(idx_a + 1, len(candidates)):
            _compare_pair(
                candidates[idx_a], candidates[idx_b], threshold, union_find, pair_scores
            )

    raw_groups = union_find.groups([f.fragment_id for f in candidates])
    groups: list[CloneGroup] = []
    for member_ids in raw_groups.values():
        filtered_ids = _remove_nested_members(member_ids, id_to_frag)
        if len(filtered_ids) < 2:
            continue
        # Use the minimum pairwise similarity as a conservative group score
        sim = _group_min_similarity(filtered_ids, pair_scores)
        groups.append(_make_group(session_id, 3, filtered_ids, similarity=sim))

    _logger.debug("Type-3: %d clone groups found.", len(groups))
    return groups


def _group_min_similarity(
    member_ids: list[str], pair_scores: dict[tuple[str, str], float]
) -> float | None:
    """Return the minimum pairwise similarity score among *member_ids*.

    :since: 1.0.0
    """
    scores: list[float] = []
    for idx in range(len(member_ids)):  # pylint: disable=consider-using-enumerate
        for jdx in range(idx + 1, len(member_ids)):
            pair = (member_ids[idx], member_ids[jdx])
            score = pair_scores.get(pair)
            if score is None:
                score = pair_scores.get((pair[1], pair[0]))
            if score is not None:
                scores.append(score)
    return min(scores) if scores else None


# ── Public API ───────────────────────────────────────────────────────────────


def detect(
    session_db: SessionDB,
    session_id: str,
    detect_types: set[int],
    threshold: float,
) -> tuple[int, int, int]:
    """Run all requested detection passes and persist results to *db*.

    Args:
        session_db: Open :class:`~codeecho.db.SessionDB` context.
        session_id: Current scan session UUID.
        detect_types: Set of clone types to detect (any subset of ``{1, 2, 3}``).
        threshold: Jaccard similarity threshold for Type-3 detection.

    Returns:
        ``(type1_count, type2_count, type3_count)`` group counts.

    :since: 1.0.0
    """
    fragments = session_db.get_fragments(session_id)
    _logger.debug("Detecting clones in %d fragments.", len(fragments))

    assigned: set[str] = set()
    cnt1 = cnt2 = cnt3 = 0

    if 1 in detect_types:
        groups1, assigned1 = _detect_type1(fragments, session_id)
        for group in groups1:
            session_db.insert_clone_group(group)
        assigned.update(assigned1)
        cnt1 = len(groups1)

    if 2 in detect_types:
        groups2, assigned2 = _detect_type2(fragments, assigned, session_id)
        for group in groups2:
            session_db.insert_clone_group(group)
        assigned.update(assigned2)
        cnt2 = len(groups2)

    if 3 in detect_types:
        groups3 = _detect_type3(fragments, assigned, session_id, threshold)
        for group in groups3:
            session_db.insert_clone_group(group)
        cnt3 = len(groups3)

    return cnt1, cnt2, cnt3
