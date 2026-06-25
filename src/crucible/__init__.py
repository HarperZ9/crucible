"""Crucible: an accountable judgment organ.

Register a thesis, steelman it, measure it against a substrate, and emit a re-checkable verdict per
claim (MATCH / DRIFT / UNVERIFIABLE). The verdict is grounded in the measurement, not a judge's
say-so, and recomputes from the record. The core is pure standard library; impure and optional edges
live behind Protocol seams with a Null default, so Crucible stands alone and composes as a peer.
"""
from __future__ import annotations

__version__ = "0.0.0"

__all__ = ["__version__"]
