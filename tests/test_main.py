"""
Tests for codeecho.__main__ CLI entry point.

:author: Ron Webb
:since: 1.0.0
"""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from codeecho.__main__ import main

# ---------------------------------------------------------------------------
# --db-dir option
# ---------------------------------------------------------------------------


def test_db_dir_default_creates_db_in_default_location(tmp_path):
    """Without --db-dir the DB is created inside ~/.codeecho (patched to tmp_path)."""
    default_dir = tmp_path / "default_db"
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    runner = CliRunner()
    with (
        patch("codeecho.__main__.scanner.scan", return_value=[]),
        patch("codeecho.db._DEFAULT_DIR", default_dir),
    ):
        result = runner.invoke(main, [str(scan_dir)])
    assert result.exit_code == 0
    assert (default_dir / "codeecho.db").exists()


def test_db_dir_custom_creates_db_in_given_directory(tmp_path):
    """Passing --db-dir puts codeecho.db inside the specified directory."""
    db_dir = tmp_path / "dbstore"
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]):
        result = runner.invoke(main, [str(scan_dir), "--db-dir", str(db_dir)])
    assert result.exit_code == 0
    assert (db_dir / "codeecho.db").exists()


def test_db_dir_creates_missing_directory(tmp_path):
    """--db-dir creates the target directory automatically if it does not exist."""
    db_dir = tmp_path / "nested" / "db"
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]):
        runner.invoke(main, [str(scan_dir), "--db-dir", str(db_dir)])
    assert db_dir.is_dir()
    assert (db_dir / "codeecho.db").exists()


def test_db_dir_is_distinct_from_output_dir(tmp_path):
    """--db-dir and --output-dir are independent; each path is respected."""
    db_dir = tmp_path / "db"
    out_dir = tmp_path / "out"
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]):
        result = runner.invoke(
            main,
            [str(scan_dir), "--db-dir", str(db_dir), "--output-dir", str(out_dir)],
        )
    assert result.exit_code == 0
    assert (db_dir / "codeecho.db").exists()
    # No files scanned → no report written, but the directory may be created
    assert not (out_dir / "codeecho-output.json").exists()


# ---------------------------------------------------------------------------
# multi-path argument
# ---------------------------------------------------------------------------


def test_no_path_provided_exits_with_error():
    """Invoking without any PATH argument exits with a usage error."""
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code != 0


def test_single_file_path_is_accepted(tmp_path):
    """A single file path (not a directory) is accepted as a valid scan target."""
    f = tmp_path / "main.py"
    f.write_text("pass", encoding="utf-8")
    db_dir = tmp_path / "db"
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]):
        result = runner.invoke(main, [str(f), "--db-dir", str(db_dir)])
    assert result.exit_code == 0


def test_multiple_paths_are_accepted(tmp_path):
    """Two directory paths can both be specified as scan targets."""
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    db_dir = tmp_path / "db"
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]):
        result = runner.invoke(main, [str(dir_a), str(dir_b), "--db-dir", str(db_dir)])
    assert result.exit_code == 0
