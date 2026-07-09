"""
SHA-256 fingerprinting of raw and normalised token sequences.

:author: Ron Webb
:since: 1.0.0
"""

import hashlib
import logging

from .models import Fragment

_logger = logging.getLogger("codeecho.fingerprint")

_SEP: str = "|"


def hash_fragment(fragment: Fragment) -> None:
    """Compute and set ``raw_hash`` and ``normalized_hash`` on *fragment* in place.

    :param fragment: A :class:`~codeecho.models.Fragment` whose ``token_sequence``
                     and ``normalized_tokens`` are already populated.
    """
    fragment.raw_hash = _sha256(_SEP.join(fragment.token_sequence))
    fragment.normalized_hash = _sha256(_SEP.join(fragment.normalized_tokens))
    fragment.token_count = len(fragment.token_sequence)


def hash_all(fragments: list[Fragment]) -> None:
    """Apply :func:`hash_fragment` to every item in *fragments*."""
    for frag in fragments:
        hash_fragment(frag)
    _logger.debug("Hashed %d fragments.", len(fragments))


def _sha256(text: str) -> str:
    """Return the hex-encoded SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
