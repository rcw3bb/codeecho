"""
SQLite session database for storing intermediate clone detection results.

Each scan run creates a session row; all fragments and clone groups are foreign-keyed
to it so a single DELETE cascades all data.  Call :meth:`SessionDB.delete_session`
after the reports have been written.

:author: Ron Webb
:since: 1.0.0
"""

import json
import logging
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType

from codeecho.models import CloneGroup, Fragment

_logger = logging.getLogger("codeecho.db")

_DEFAULT_DB_PATH: Path = Path(tempfile.gettempdir()) / "codeecho.db"

_SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS sessions (
    id   TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    scan_path    TEXT NOT NULL,
    config_json  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fragments (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    file_path        TEXT NOT NULL,
    language         TEXT NOT NULL,
    fragment_type    TEXT NOT NULL,
    start_line       INTEGER NOT NULL,
    end_line         INTEGER NOT NULL,
    token_count      INTEGER NOT NULL DEFAULT 0,
    raw_hash         TEXT,
    normalized_hash  TEXT,
    token_sequence   TEXT NOT NULL DEFAULT '[]',
    source_text      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS clone_groups (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    clone_type          INTEGER NOT NULL,
    representative_hash TEXT,
    similarity_score    REAL
);

CREATE TABLE IF NOT EXISTS clone_group_members (
    group_id    TEXT NOT NULL REFERENCES clone_groups(id) ON DELETE CASCADE,
    fragment_id TEXT NOT NULL REFERENCES fragments(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, fragment_id)
);
"""


def _row_to_fragment(row: sqlite3.Row) -> Fragment:
    return Fragment(
        fragment_id=row["id"],
        session_id=row["session_id"],
        file_path=row["file_path"],
        language=row["language"],
        fragment_type=row["fragment_type"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        token_count=row["token_count"],
        raw_hash=row["raw_hash"],
        normalized_hash=row["normalized_hash"],
        token_sequence=json.loads(row["token_sequence"]),
        source_text=row["source_text"],
    )


class SessionDB:
    """Context manager owning a SQLite connection for one scan session.

    Usage::

        with SessionDB() as db:
            db.create_session(session_id, path, config)
            db.insert_many_fragments(fragments)
            ...
            db.delete_session(session_id)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._path: Path = db_path or _DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "SessionDB":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.execute("PRAGMA foreign_keys = ON")
        _logger.debug("Opened session DB at %s", self._path)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _conn_required(self) -> sqlite3.Connection:  # pylint: disable=invalid-name
        if self._conn is None:
            raise RuntimeError("SessionDB is not open; use it as a context manager.")
        return self._conn

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, scan_path: str, config: dict) -> None:
        """Insert a new scan session record."""
        self._conn_required.execute(
            "INSERT INTO sessions (id, created_at, scan_path, config_json) VALUES (?, ?, ?, ?)",
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                scan_path,
                json.dumps(config),
            ),
        )
        self._conn_required.commit()

    def delete_session(self, session_id: str) -> None:
        """Delete the session and all its fragments/groups via CASCADE."""
        self._conn_required.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn_required.commit()
        _logger.info("Session %s deleted from database.", session_id)

    # ------------------------------------------------------------------
    # Fragments
    # ------------------------------------------------------------------

    def insert_many_fragments(self, fragments: list[Fragment]) -> None:
        """Bulk-insert a list of fully-populated Fragment objects."""
        self._conn_required.executemany(
            """
            INSERT INTO fragments
                (id, session_id, file_path, language, fragment_type,
                 start_line, end_line, token_count, raw_hash, normalized_hash,
                 token_sequence, source_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f.fragment_id,
                    f.session_id,
                    f.file_path,
                    f.language,
                    f.fragment_type,
                    f.start_line,
                    f.end_line,
                    f.token_count,
                    f.raw_hash,
                    f.normalized_hash,
                    json.dumps(f.token_sequence),
                    f.source_text,
                )
                for f in fragments
            ],
        )
        self._conn_required.commit()

    def get_fragments(self, session_id: str) -> list[Fragment]:
        """Return all fragments for a session."""
        rows = self._conn_required.execute(
            "SELECT * FROM fragments WHERE session_id = ?", (session_id,)
        ).fetchall()
        return [_row_to_fragment(r) for r in rows]

    def get_fragment_by_id(self, fragment_id: str) -> Fragment | None:
        """Return a single Fragment by its ID, or None if not found."""
        row = self._conn_required.execute(
            "SELECT * FROM fragments WHERE id = ?", (fragment_id,)
        ).fetchone()
        return _row_to_fragment(row) if row else None

    def get_fragments_by_ids(self, fragment_ids: list[str]) -> list[Fragment]:
        """Fetch multiple fragments by ID in one query."""
        if not fragment_ids:
            return []
        placeholders = ",".join("?" * len(fragment_ids))
        rows = self._conn_required.execute(
            f"SELECT * FROM fragments WHERE id IN ({placeholders})", fragment_ids
        ).fetchall()
        return [_row_to_fragment(r) for r in rows]

    def count_fragments(self, session_id: str) -> int:
        """Return the number of fragments stored for a session."""
        row = self._conn_required.execute(
            "SELECT COUNT(*) AS cnt FROM fragments WHERE session_id = ?", (session_id,)
        ).fetchone()
        return int(row["cnt"]) if row else 0

    # ------------------------------------------------------------------
    # Clone groups
    # ------------------------------------------------------------------

    def insert_clone_group(self, group: CloneGroup) -> None:
        """Persist a CloneGroup and its member associations."""
        self._conn_required.execute(
            "INSERT INTO clone_groups (id, session_id, clone_type, representative_hash, similarity_score) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                group.group_id,
                group.session_id,
                group.clone_type,
                group.representative_hash,
                group.similarity_score,
            ),
        )
        self._conn_required.executemany(
            "INSERT INTO clone_group_members (group_id, fragment_id) VALUES (?, ?)",
            [(group.group_id, fid) for fid in group.member_fragment_ids],
        )
        self._conn_required.commit()

    def get_clone_groups(self, session_id: str) -> list[CloneGroup]:
        """Return all clone groups with member fragment IDs for a session."""
        rows = self._conn_required.execute(
            "SELECT * FROM clone_groups WHERE session_id = ? ORDER BY clone_type",
            (session_id,),
        ).fetchall()
        groups: list[CloneGroup] = []
        for row in rows:
            members = self._conn_required.execute(
                "SELECT fragment_id FROM clone_group_members WHERE group_id = ?",
                (row["id"],),
            ).fetchall()
            groups.append(
                CloneGroup(
                    group_id=row["id"],
                    session_id=row["session_id"],
                    clone_type=row["clone_type"],
                    representative_hash=row["representative_hash"],
                    similarity_score=row["similarity_score"],
                    member_fragment_ids=[m["fragment_id"] for m in members],
                )
            )
        return groups

    def get_fragments_for_group(self, group: CloneGroup) -> list[Fragment]:
        """Fetch Fragment objects belonging to a CloneGroup."""
        return self.get_fragments_by_ids(group.member_fragment_ids)
