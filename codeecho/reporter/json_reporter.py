"""
JSON reporter: serialises clone detection results from the session database to a JSON file.

:author: Ron Webb
:since: 1.0.0
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import basis as basis_module
from ..db import SessionDB
from ..models import CloneGroup, Fragment, ScanResult

_logger = logging.getLogger("codeecho.reporter.json")


def _fragment_to_dict(
    frag: Fragment, basis_files: frozenset[str] | None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "fragment_id": frag.fragment_id,
        "file": frag.file_path,
        "language": frag.language,
        "fragment_type": frag.fragment_type,
        "start_line": frag.start_line,
        "end_line": frag.end_line,
        "token_count": frag.token_count,
        "source_text": frag.source_text,
    }
    if basis_files is not None:
        result["is_basis"] = frag.file_path in basis_files
    return result


def _group_to_dict(
    group: CloneGroup,
    members: list[Fragment],
    basis_files: frozenset[str] | None,
    basis_internal: bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "group_id": group.group_id,
        "clone_type": group.clone_type,
        "representative_hash": group.representative_hash,
        "members": [_fragment_to_dict(f, basis_files) for f in members],
    }
    if group.similarity_score is not None:
        result["similarity_score"] = round(group.similarity_score, 4)
    if basis_internal is not None:
        result["basis_internal"] = basis_internal
    return result


def write(
    session_db: SessionDB,
    result: ScanResult,
    output_path: Path,
    basis_files: frozenset[str] | None = None,
) -> Path:
    """Serialise all clone groups for *result.session_id* to *output_path*.

    When *basis_files* is given, only groups touching at least one basis file are
    included, each member gains an ``is_basis`` flag, each group gains a
    ``basis_internal`` flag (True when every member is a basis file), and the
    summary gains per-type basis group counts (``basis_type1_groups``, etc.).

    :param session_db: Open :class:`~codeecho.db.SessionDB` context.
    :param result: Summary statistics from the scan.
    :param output_path: Destination JSON file path.
    :param basis_files: Resolved ``--basis`` file paths, or ``None`` when unused.
    :returns: The resolved path of the written file.
    :since: 1.0.0
    """
    groups = session_db.get_clone_groups(result.session_id)
    groups_with_members = [(g, session_db.get_fragments_for_group(g)) for g in groups]

    groups_data: list[dict[str, Any]] = []
    if basis_files is not None:
        for group, members, basis_internal in basis_module.filter_groups_for_basis(
            groups_with_members, basis_files
        ):
            groups_data.append(
                _group_to_dict(group, members, basis_files, basis_internal)
            )
    else:
        for group, members in groups_with_members:
            groups_data.append(_group_to_dict(group, members, None))

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": result.version,
        "session_id": result.session_id,
        "scan_path": result.scan_path,
        "summary": {
            "files_scanned": result.files_scanned,
            "fragments_extracted": result.fragments_extracted,
            "type1_groups": result.type1_groups,
            "type2_groups": result.type2_groups,
            "type3_groups": result.type3_groups,
        },
        "clone_groups": groups_data,
    }
    if result.basis_paths:
        payload["basis_paths"] = result.basis_paths
        payload["summary"]["basis_type1_groups"] = result.basis_type1_groups
        payload["summary"]["basis_type2_groups"] = result.basis_type2_groups
        payload["summary"]["basis_type3_groups"] = result.basis_type3_groups

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _logger.debug("JSON report written to %s", output_path)
    return output_path.resolve()
