"""
User-configurable overrides for codeecho, read from ``config.ini``.

:author: Ron Webb
:since: 1.2.0
"""

import configparser
from pathlib import Path

from . import CONF_DIR

_DEFAULT_IGNORE_FILE = ".ignore"


class Config:
    """Reads user-configurable overrides from ``config.ini`` in *conf_dir*.

    :author: Ron Webb
    :since: 1.2.0
    """

    def __init__(self, conf_dir: str | None = None) -> None:
        """Load ``config.ini`` from *conf_dir* (defaults to ``CONF_DIR``).

        :since: 1.2.0
        """
        self._config = configparser.ConfigParser()
        config_path = Path(conf_dir or CONF_DIR) / "config.ini"
        self._config.read(config_path)

    def get_ignore_file(self) -> str:
        """Return the configured ignore filename override.

        Falls back to ``.ignore`` when the section/key is absent.

        :since: 1.2.0
        """
        return self._config.get(
            "override", "ignore-file", fallback=_DEFAULT_IGNORE_FILE
        )
