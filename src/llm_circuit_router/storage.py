"""Shared JSON persistence helpers and canonical pipeline artifact paths.

Every stage of the pipeline reads and writes small JSON documents on disk.
Centralising that logic here keeps the individual stages free of duplicated
``open()``/``json.load()`` boilerplate and gives each artifact a single
authoritative filename.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

# A JSON document shaped like ``{"slug": {...}}``.
JsonDict = Dict[str, Any]
PathLike = Union[str, Path]

# ── Canonical pipeline artifacts ──────────────────────────────────────────────
# Paths are resolved relative to the process working directory, matching how
# the pipeline stages have always been invoked (``python -m ...`` from the repo
# root). Override them per-call when a stage needs a different location.
RAW_BENCHMARKS_FILE: str = "artificial_analysis_models.json"
CAPABILITIES_FILE: str = "model_capabilities.json"
PENDING_FILE: str = "pending.json"
LEDGER_FILE: str = "reliability_ledger.json"
FINAL_REGISTRY_FILE: str = "final_model_registry.json"


def load_json(path: PathLike, default: Optional[JsonDict] = None) -> JsonDict:
    """Load a JSON object from ``path``.

    Returns ``default`` (an empty dict when omitted) if the file is missing,
    unreadable, malformed, or does not contain a JSON object. Callers therefore
    never have to guard against a partially-written artifact.
    """
    fallback: JsonDict = {} if default is None else default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback
    return data if isinstance(data, dict) else fallback


def save_json(path: PathLike, data: Any) -> None:
    """Write ``data`` to ``path`` as indented UTF-8 JSON.

    Missing parent directories are created on demand. Any OS or serialisation
    error propagates so that a failed write is never mistaken for a success.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
