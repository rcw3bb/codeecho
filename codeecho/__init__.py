"""
codeecho - A developer tool that scans your codebase to detect and highlight ECHOES
of duplicated or near-duplicated code so you can refactor toward cleaner, more
maintainable designs.

:author: Ron Webb
:since: 1.0.0
"""

from env_dir_bootstrap import EnvDirBootstrap
from logenrich import setup_logger

__version__ = "1.0.0"

_bootstrapper = EnvDirBootstrap(
    env_var="CODEECHO_CONFIG_DIR",
    resources=["logging.ini", ".ignore"],
    package="codeecho",
)

_bootstrapper.setup()

CONF_DIR = str(_bootstrapper.get_dir())

setup_logger("codeecho", conf_dir=CONF_DIR)
