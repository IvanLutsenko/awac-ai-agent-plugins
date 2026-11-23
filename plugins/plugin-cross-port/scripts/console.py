"""Console setup shared by the entry points (cross_port.py and both converters)."""
from __future__ import annotations

import sys


def utf8_console() -> None:
    """Windows consoles default to a legacy code page that cannot encode the
    report's symbols; print them as UTF-8 instead of failing the conversion."""
    for stream, errors in ((sys.stdout, "replace"), (sys.stderr, "backslashreplace")):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=errors)
