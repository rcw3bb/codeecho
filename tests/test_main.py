"""
Tests for codeecho.__main__ CLI entry point.

:author: Ron Webb
:since: 1.0.0
"""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from codeecho.__main__ import _build_ignore, _load_ignore_file, main

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


# ---------------------------------------------------------------------------
# --target-list option
# ---------------------------------------------------------------------------


def test_target_list_reads_paths_from_file(tmp_path):
    """--target-list reads one path per line, skipping blanks and comments."""
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    list_file = tmp_path / "targets.txt"
    list_file.write_text(f"{dir_a}\n\n# comment\n{dir_b}\n", encoding="utf-8")
    db_dir = tmp_path / "db"
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]) as mock_scan:
        result = runner.invoke(
            main, [str(list_file), "--target-list", "--db-dir", str(db_dir)]
        )
    assert result.exit_code == 0
    scanned_paths = mock_scan.call_args[0][0]
    assert dir_a.resolve() in scanned_paths
    assert dir_b.resolve() in scanned_paths


def test_target_list_rejects_multiple_paths(tmp_path):
    """--target-list requires exactly one PATH argument."""
    f1 = tmp_path / "list1.txt"
    f2 = tmp_path / "list2.txt"
    f1.write_text("x\n", encoding="utf-8")
    f2.write_text("y\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, [str(f1), str(f2), "--target-list"])
    assert result.exit_code != 0
    assert "single existing file" in result.output


def test_target_list_rejects_directory_path(tmp_path):
    """--target-list requires PATH to be a file, not a directory."""
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, [str(scan_dir), "--target-list"])
    assert result.exit_code != 0
    assert "single existing file" in result.output


def test_target_list_empty_file_exits_with_error(tmp_path):
    """--target-list on a file with no real entries exits with a usage error."""
    list_file = tmp_path / "targets.txt"
    list_file.write_text("# just a comment\n\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, [str(list_file), "--target-list"])
    assert result.exit_code != 0
    assert "no target paths" in result.output


# ---------------------------------------------------------------------------
# --basis option
# ---------------------------------------------------------------------------


def test_basis_targets_merged_into_scan(tmp_path):
    """--basis paths not already in PATH are added to the scan automatically."""
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    basis_dir = tmp_path / "reference"
    basis_dir.mkdir()
    basis_list = tmp_path / "basis.txt"
    basis_list.write_text(f"{basis_dir}\n", encoding="utf-8")
    db_dir = tmp_path / "db"
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]) as mock_scan:
        result = runner.invoke(
            main, [str(scan_dir), "--basis", str(basis_list), "--db-dir", str(db_dir)]
        )
    assert result.exit_code == 0
    scanned_paths = mock_scan.call_args[0][0]
    assert scan_dir.resolve() in scanned_paths
    assert basis_dir.resolve() in scanned_paths


def test_basis_empty_file_exits_with_error(tmp_path):
    """--basis file with no real entries exits with a usage error."""
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    basis_list = tmp_path / "basis.txt"
    basis_list.write_text("# just a comment\n\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, [str(scan_dir), "--basis", str(basis_list)])
    assert result.exit_code != 0
    assert "no target paths" in result.output


def test_basis_rejects_missing_file(tmp_path):
    """--basis requires the given path to exist."""
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main, [str(scan_dir), "--basis", str(tmp_path / "missing.txt")]
    )
    assert result.exit_code != 0


def test_basis_relative_entry_not_merged_into_scan(tmp_path):
    """A relative --basis entry (e.g. a bare filename) is not treated as a scan root."""
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    basis_list = tmp_path / "basis.txt"
    basis_list.write_text("SomeFile.gs\n", encoding="utf-8")
    db_dir = tmp_path / "db"
    runner = CliRunner()
    with patch("codeecho.__main__.scanner.scan", return_value=[]) as mock_scan:
        result = runner.invoke(
            main, [str(scan_dir), "--basis", str(basis_list), "--db-dir", str(db_dir)]
        )
    assert result.exit_code == 0
    scanned_paths = mock_scan.call_args[0][0]
    assert scanned_paths == (scan_dir.resolve(),)


def test_basis_relative_entry_matches_file_anywhere_in_scan(tmp_path):
    """A relative --basis entry matches a same-named file discovered anywhere in the scan."""
    scan_dir = tmp_path / "src"
    nested_dir = scan_dir / "nested"
    nested_dir.mkdir(parents=True)
    target_file = nested_dir / "IInfuser.gs"
    target_file.write_text("class IInfuser {}\n", encoding="utf-8")
    other_file = scan_dir / "Other.gs"
    other_file.write_text("class Other {}\n", encoding="utf-8")
    basis_list = tmp_path / "basis.txt"
    basis_list.write_text("IInfuser.gs\n", encoding="utf-8")
    db_dir = tmp_path / "db"

    captured = {}

    def fake_write_reports(
        session_db, result, output_dir, output, fmt, basis_files=None
    ):  # pylint: disable=too-many-arguments,unused-argument
        captured["basis_files"] = basis_files
        return []

    runner = CliRunner()
    with patch("codeecho.__main__._write_reports", side_effect=fake_write_reports):
        result = runner.invoke(
            main, [str(scan_dir), "--basis", str(basis_list), "--db-dir", str(db_dir)]
        )
    assert result.exit_code == 0
    assert captured["basis_files"] == frozenset({str(target_file.resolve())})


def test_basis_warns_when_no_overlap_with_scanned_files(tmp_path):
    """A warning is printed when no scanned file falls under any --basis path."""
    scan_dir = tmp_path / "src"
    scan_dir.mkdir()
    (scan_dir / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    basis_dir = tmp_path / "unrelated"
    basis_dir.mkdir()
    basis_list = tmp_path / "basis.txt"
    basis_list.write_text(f"{basis_dir}\n", encoding="utf-8")
    db_dir = tmp_path / "db"
    runner = CliRunner()
    result = runner.invoke(
        main, [str(scan_dir), "--basis", str(basis_list), "--db-dir", str(db_dir)]
    )
    assert result.exit_code == 0
    assert "none of the --basis paths matched" in result.output


def test_basis_files_passed_to_report_writers(tmp_path):
    """Resolved basis files are threaded through to the report writers."""
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    basis_dir = tmp_path / "basis"
    basis_dir.mkdir()
    basis_file = basis_dir / "a.py"
    basis_file.write_text("def foo():\n    pass\n", encoding="utf-8")
    other_file = scan_dir / "b.py"
    other_file.write_text("def bar():\n    pass\n", encoding="utf-8")
    basis_list = tmp_path / "basis.txt"
    basis_list.write_text(f"{basis_dir}\n", encoding="utf-8")
    db_dir = tmp_path / "db"

    discovered = [(basis_file.resolve(), "Python"), (other_file.resolve(), "Python")]
    captured = {}

    def fake_write_reports(
        session_db, result, output_dir, output, fmt, basis_files=None
    ):  # pylint: disable=too-many-arguments,unused-argument
        captured["basis_files"] = basis_files
        return []

    runner = CliRunner()
    with (
        patch("codeecho.__main__.scanner.scan", return_value=discovered),
        patch("codeecho.__main__._write_reports", side_effect=fake_write_reports),
    ):
        result = runner.invoke(
            main,
            [str(scan_dir), "--basis", str(basis_list), "--db-dir", str(db_dir)],
        )
    assert result.exit_code == 0
    assert captured["basis_files"] == frozenset({str(basis_file.resolve())})


# ---------------------------------------------------------------------------
# _load_ignore_file / _build_ignore (config.ini override support)
# ---------------------------------------------------------------------------


def test_load_ignore_file_missing_returns_none(tmp_path):
    """A missing ignore file path is reported as None instead of raising."""
    assert _load_ignore_file(tmp_path / "missing.ignore", tmp_path) is None


def test_load_ignore_file_existing_returns_ignore_file(tmp_path):
    """An existing ignore file path loads successfully."""
    ignore_path = tmp_path / ".ignore"
    ignore_path.write_text("*.log\n", encoding="utf-8")
    result = _load_ignore_file(ignore_path, tmp_path)
    assert result is not None
    assert result.is_ignored(tmp_path / "debug.log")


def test_build_ignore_uses_custom_filename_from_config(tmp_path):
    """_build_ignore prefers the filename returned by the config override."""
    custom_ignore = tmp_path / "custom.ignore"
    custom_ignore.write_text("*.tmp\n", encoding="utf-8")
    with (
        patch("codeecho.__main__.CONF_DIR", str(tmp_path)),
        patch(
            "codeecho.__main__._config.get_ignore_file", return_value="custom.ignore"
        ),
    ):
        result = _build_ignore(tmp_path)
    assert result is not None
    assert result.is_ignored(tmp_path / "scratch.tmp")


def test_build_ignore_falls_back_to_default_when_custom_missing(tmp_path):
    """_build_ignore falls back to the default ignore file if the custom one is missing."""
    default_ignore = tmp_path / ".ignore"
    default_ignore.write_text("*.log\n", encoding="utf-8")
    with (
        patch("codeecho.__main__.CONF_DIR", str(tmp_path)),
        patch("codeecho.__main__.DEFAULT_IGNORE_PATH", str(default_ignore)),
        patch(
            "codeecho.__main__._config.get_ignore_file", return_value="missing.ignore"
        ),
    ):
        result = _build_ignore(tmp_path)
    assert result is not None
    assert result.is_ignored(tmp_path / "debug.log")


def test_build_ignore_returns_none_when_nothing_usable(tmp_path):
    """_build_ignore returns None when neither the custom nor default ignore file exists."""
    with (
        patch("codeecho.__main__.CONF_DIR", str(tmp_path)),
        patch("codeecho.__main__.DEFAULT_IGNORE_PATH", str(tmp_path / ".ignore")),
        patch(
            "codeecho.__main__._config.get_ignore_file", return_value="missing.ignore"
        ),
    ):
        result = _build_ignore(tmp_path)
    assert result is None
