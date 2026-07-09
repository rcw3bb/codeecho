"""
Data models for the codeecho duplicate detection pipeline.

:author: Ron Webb
:since: 1.0.0
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Fragment:  # pylint: disable=too-many-instance-attributes
    """Represents a code fragment (function, class, or file block) extracted from a source file."""

    fragment_id: str
    session_id: str
    file_path: str
    language: str
    fragment_type: str
    start_line: int
    end_line: int
    token_count: int = 0
    raw_hash: str | None = None
    normalized_hash: str | None = None
    token_sequence: list[str] = field(default_factory=list, repr=False)
    normalized_tokens: list[str] = field(default_factory=list, repr=False)
    source_text: str = ""


@dataclass
class CloneGroup:
    """Represents a cluster of code fragments that are clones of each other."""

    group_id: str
    session_id: str
    clone_type: int
    representative_hash: str | None = None
    similarity_score: float | None = None
    member_fragment_ids: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Summary statistics for a completed duplicate detection scan."""

    session_id: str
    scan_path: str
    files_scanned: int
    fragments_extracted: int
    type1_groups: int
    type2_groups: int
    type3_groups: int
