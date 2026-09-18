"""
Tests for codeecho.config.

:author: Ron Webb
:since: 1.2.0
"""

from codeecho.config import Config


def test_get_ignore_file_defaults_when_config_missing(tmp_path):
    """Without a config.ini present, the default ignore filename is returned."""
    config = Config(conf_dir=str(tmp_path))
    assert config.get_ignore_file() == ".ignore"


def test_get_ignore_file_defaults_when_section_absent(tmp_path):
    """A config.ini without an [override] section falls back to the default."""
    (tmp_path / "config.ini").write_text("[other]\nkey = value\n", encoding="utf-8")
    config = Config(conf_dir=str(tmp_path))
    assert config.get_ignore_file() == ".ignore"


def test_get_ignore_file_returns_custom_override(tmp_path):
    """A configured [override] ignore-file value is returned as-is."""
    (tmp_path / "config.ini").write_text(
        "[override]\nignore-file = .customignore\n", encoding="utf-8"
    )
    config = Config(conf_dir=str(tmp_path))
    assert config.get_ignore_file() == ".customignore"
