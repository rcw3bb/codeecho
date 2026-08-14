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

from codeecho.db import SessionDB
from codeecho.models import CloneGroup, Fragment, ScanResult

_logger = logging.getLogger("codeecho.reporter.json")


def _fragment_to_dict(frag: Fragment) -> dict[str, Any]:
    return {
        "fragment_id": frag.fragment_id,
        "file": frag.file_path,
        "language": frag.language,
        "fragment_type": frag.fragment_type,
        "start_line": frag.start_line,
        "end_line": frag.end_line,
        "token_count": frag.token_count,
        "source_text": frag.source_text,
    }


def _group_to_dict(group: CloneGroup, members: list[Fragment]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "group_id": group.group_id,
        "clone_type": group.clone_type,
        "representative_hash": group.representative_hash,
        "members": [_fragment_to_dict(f) for f in members],
    }
    if group.similarity_score is not None:
        result["similarity_score"] = round(group.similarity_score, 4)
    return result


def write(
    session_db: SessionDB,
    result: ScanResult,
    output_path: Path,
) -> Path:
    """Serialise all clone groups for *result.session_id* to *output_path*.

    :param session_db: Open :class:`~codeecho.db.SessionDB` context.
    :param result: Summary statistics from the scan.
    :param output_path: Destination JSON file path.
    :returns: The resolved path of the written file.
    """
    groups = session_db.get_clone_groups(result.session_id)
    groups_data: list[dict[str, Any]] = []
    for group in groups:
        members = session_db.get_fragments_for_group(group)
        groups_data.append(_group_to_dict(group, members))

    payload = {
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _logger.debug("JSON report written to %s", output_path)
    return output_path.resolve()
