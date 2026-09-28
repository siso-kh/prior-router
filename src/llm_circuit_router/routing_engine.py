"""Rank the compiled model registry into a task-specific fallback order."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.llm_circuit_router.storage import FINAL_REGISTRY_FILE, load_json

# Task keys understood by the registry's ``composite_routing_scores`` block.
VALID_TASKS: tuple[str, ...] = ("general", "coding", "reasoning", "vision")
DEFAULT_TASK: str = "general"


class CircuitRouterSortingEngine:
    """Ranks registry entries by their composite score for a requested task.

    Quarantined models are dropped entirely and vision tasks exclude models
    without any vision capability, so the returned list is always a safe,
    ordered fallback stack.
    """

    def __init__(self, registry_filepath: str = FINAL_REGISTRY_FILE) -> None:
        self.registry_filepath = registry_filepath

    def _load_registry(self) -> Dict[str, Any]:
        """Read the master registry, returning an empty mapping when unavailable."""
        registry = load_json(self.registry_filepath)
        if not registry:
            print(
                f"❌ Error: registry file '{self.registry_filepath}' is missing or "
                "empty. Build the master registry first."
            )
        return registry

    def get_ranked_models_for_task(
        self, task_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return working models sorted by descending composite score.

        ``task_type`` selects which ``composite_routing_scores`` field to rank
        on. Unknown or omitted values fall back to ``general``.
        """
        registry = self._load_registry()
        if not registry:
            return []

        selected_task = (task_type or DEFAULT_TASK).lower().strip()
        if selected_task not in VALID_TASKS:
            print(
                f"⚠️ Warning: invalid task '{selected_task}' requested. "
                f"Defaulting to '{DEFAULT_TASK}'."
            )
            selected_task = DEFAULT_TASK

        active_lineup: List[Dict[str, Any]] = []

        for slug, data in registry.items():
            reliability = data.get("reliability", {})

            # Circuit-breaker gate: skip anything currently quarantined.
            if reliability.get("quarantined_until"):
                continue

            benchmarks = data.get("benchmarks", {})

            # A model with no vision score simply cannot serve vision requests.
            if selected_task == "vision" and benchmarks.get("vision", 0.0) == 0.0:
                continue

            composite_scores = data.get("composite_routing_scores", {})
            active_lineup.append(
                {
                    "model_name": slug,
                    "provider": data["provider"],
                    "base_url": data["base_url"],
                    "api_key": data["api_key"],
                    "context_length": data["context_length"],
                    "reliability_score": reliability.get("score", 1.0),
                    "composite_score": float(composite_scores.get(selected_task, 0.0)),
                    "benchmark_base": benchmarks.get(selected_task, 0.0),
                }
            )

        return sorted(
            active_lineup, key=lambda model: model["composite_score"], reverse=True
        )
