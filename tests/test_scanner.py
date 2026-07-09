"""
Tests for codeecho.scanner.

:author: Ron Webb
:since: 1.0.0
"""

from pathlib import Path

from braincraft import IgnoreFile

from codeecho.scanner import EXTENSION_TO_LANGUAGE, scan


def test_scan_finds_py_files(tmp_path):
    (tmp_path / "main.py").write_text("def foo(): pass", encoding="utf-8")
    (tmp_path / "util.py").write_text("def bar(): pass", encoding="utf-8")
    (tmp_path / "README.md").write_text("# doc", encoding="utf-8")
    results = scan(tmp_path)
    languages = {lang for _, lang in results}
    assert "Python" in languages
    assert len(results) == 2


def test_scan_respects_default_exclude(tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "spam.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "real.py").write_text("y = 2", encoding="utf-8")
    results = scan(tmp_path)
    paths = [str(p) for p, _ in results]
    assert not any(".venv" in p for p in paths)
    assert any("real.py" in p for p in paths)


def test_scan_glob_exclude(tmp_path):
    keep = tmp_path / "keep.py"
    keep.write_text("pass", encoding="utf-8")
    skip = tmp_path / "skip.py"
    skip.write_text("pass", encoding="utf-8")
    results = scan(tmp_path, exclude_patterns=("*skip*",))
    paths = [str(p) for p, _ in results]
    assert any("keep.py" in p for p in paths)
    assert not any("skip.py" in p for p in paths)


def test_extension_language_mapping():
    assert EXTENSION_TO_LANGUAGE[".py"] == "Python"
    assert EXTENSION_TO_LANGUAGE[".gs"] == "Gosu"
    assert EXTENSION_TO_LANGUAGE[".ts"] == "TypeScript"
    assert EXTENSION_TO_LANGUAGE[".tsx"] == "TypeScript"
    assert EXTENSION_TO_LANGUAGE[".go"] == "Go"


def test_scan_subdirectory(tmp_path):
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "a.py").write_text("pass", encoding="utf-8")
    results = scan(tmp_path)
    assert len(results) == 1
    assert results[0][1] == "Python"


def test_scan_ignore_file_excludes_file(tmp_path):
    """IgnoreFile patterns cause matching files to be excluded from results."""
    keep = tmp_path / "keep.py"
    keep.write_text("pass", encoding="utf-8")
    skip = tmp_path / "generated.py"
    skip.write_text("pass", encoding="utf-8")

    ignore_path = tmp_path / ".ignore"
    ignore_path.write_text("generated.py\n", encoding="utf-8")
    ig = IgnoreFile(ignore_path, base_dir=tmp_path)

    results = scan(tmp_path, ignore_file=ig)
    paths = [str(p) for p, _ in results]
    assert any("keep.py" in p for p in paths)
    assert not any("generated.py" in p for p in paths)


def test_scan_ignore_file_excludes_directory(tmp_path):
    """IgnoreFile directory patterns cause the whole subtree to be excluded."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    (gen_dir / "output.py").write_text("pass", encoding="utf-8")
    keep = tmp_path / "main.py"
    keep.write_text("pass", encoding="utf-8")

    ignore_path = tmp_path / ".ignore"
    ignore_path.write_text("generated/\n", encoding="utf-8")
    ig = IgnoreFile(ignore_path, base_dir=tmp_path)

    results = scan(tmp_path, ignore_file=ig)
    paths = [str(p) for p, _ in results]
    assert any("main.py" in p for p in paths)
    assert not any("generated" in p for p in paths)


def test_scan_ignore_file_none_does_not_raise(tmp_path):
    """Passing ignore_file=None behaves like no ignore file (backward-compatible)."""
    (tmp_path / "app.py").write_text("pass", encoding="utf-8")
    results = scan(tmp_path, ignore_file=None)
    assert len(results) == 1
