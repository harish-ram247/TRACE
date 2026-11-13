"""Use the operating system's certificate store for outbound HTTPS.

Python's bundled certificates do not include roots added by the OS, such as antivirus or
corporate TLS-inspection roots, so downloads (for example model weights) fail with
CERTIFICATE_VERIFY_FAILED on such machines. `truststore` keeps verification on and only changes
which trust store is consulted.
"""

from __future__ import annotations

_done = False


def use_system_trust_store() -> None:
    global _done
    if _done:
        return
    import truststore

    truststore.inject_into_ssl()
    _done = True
