"""A multi-provider AI model router with health checks and circuit-breaker failover.

The public surface is exposed lazily: importing the package does not pull in the
heavy provider/LLM dependencies until a symbol is actually requested.
"""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "0.1.0"

__all__ = [
    "CircuitRouterSortingEngine",
    "LiveBenchmarkFetcher",
    "ModelDiscoveryEngine",
    "ReboundSession",
    "Settings",
    "get_settings",
]

# Public symbol -> module that defines it.
_EXPORTS = {
    "CircuitRouterSortingEngine": "src.llm_circuit_router.routing_engine",
    "LiveBenchmarkFetcher": "src.llm_circuit_router.benchmarks_fetcher",
    "ModelDiscoveryEngine": "src.llm_circuit_router.discovery",
    "ReboundSession": "src.llm_circuit_router.rebound",
    "Settings": "src.llm_circuit_router.config",
    "get_settings": "src.llm_circuit_router.config",
}


def __getattr__(name: str) -> Any:
    """Resolve a public symbol from :data:`_EXPORTS` on first access."""
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    return sorted(__all__)
