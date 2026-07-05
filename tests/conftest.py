"""
Shared pytest fixtures for codeecho tests.

:author: Ron Webb
:since: 1.0.0
"""

import pytest

from codeecho.db import SessionDB


@pytest.fixture
def session_db(tmp_path):
    """Open a fresh :class:`SessionDB` backed by a temp file."""
    db_path = tmp_path / "test_sessions.db"
    with SessionDB(db_path=db_path) as sdb:
        yield sdb


@pytest.fixture
def session_id(session_db):
    """Create a session in *session_db* and return its UUID string."""
    sid = "test-session-001"
    session_db.create_session(sid, "/test/path", {"types": "all"})
    return sid
