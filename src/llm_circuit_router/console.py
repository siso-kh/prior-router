"""Console encoding helpers.

The pipeline prints emoji-rich progress output. On Windows the default console
encoding (cp1252) cannot represent those characters, which raises
``UnicodeEncodeError`` mid-run. CLI entrypoints call :func:`enable_utf8_console`
once, up front, to avoid that.
"""

from __future__ import annotations

import sys


def enable_utf8_console() -> None:
    """Best-effort switch of ``stdout``/``stderr`` to UTF-8.

    Streams that do not support reconfiguration (e.g. when redirected to a
    buffer) are left untouched.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass
