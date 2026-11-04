"""Karjimut: Arsitektur Memori Dua Lapis berbasis Model Context Protocol
dengan Konsolidasi Fase Idle untuk Efisiensi Token Lintas Agentic AI."""

from __future__ import annotations

import sys

__app_name__ = "Karjimut"
__version__ = "2.0.2"

# Backward-compatible module aliasing (mendukung import `karjimut.*` maupun `src.*`)
if __name__ == "karjimut" and "src" not in sys.modules:
    sys.modules["src"] = sys.modules[__name__]
elif __name__ == "src" and "karjimut" not in sys.modules:
    sys.modules["karjimut"] = sys.modules[__name__]

