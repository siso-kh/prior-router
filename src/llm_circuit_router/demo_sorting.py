"""Manual demo: print the ranked fallback lineup for a few task types.

Run with::

    python -m src.llm_circuit_router.demo_sorting

Requires a compiled ``final_model_registry.json`` in the working directory.
"""

from __future__ import annotations

from typing import Optional, Tuple

from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.routing_engine import CircuitRouterSortingEngine

# (scenario label, task key) — ``None`` exercises the general-knowledge default.
SCENARIOS: Tuple[Tuple[str, Optional[str]], ...] = (
    ("Coding Pipeline Assigner", "coding"),
    ("Scholarship Essay Logic Review", "reasoning"),
    ("Dynamic Default Fallback", None),
)


def main() -> None:
    engine = CircuitRouterSortingEngine()

    for label, task in SCENARIOS:
        print("\n" + "=" * 70)
        print(f"🎬 Scenario: {label} (task key: '{task}')")
        print("=" * 70)

        ranked = engine.get_ranked_models_for_task(task_type=task)
        if not ranked:
            print("⚠️ No unquarantined models available for this task type.")
            continue

        winner = ranked[0]
        print(f"🎯 TOP RANKED MODEL: {winner['model_name']}")
        print(f"   Provider Base Path: {winner['base_url']}")
        print(f"   Composite Score:    {winner['composite_score']} pts")

        print("\n📋 Full Prioritized Lineup Stack:")
        for index, model in enumerate(ranked):
            print(
                f"  [{index + 1}] {model['model_name']:<45} | "
                f"Score: {model['composite_score']:<5} | "
                f"Base Benchmark: {model['benchmark_base']}"
            )

    print("\n✅ Sorting demo complete.")


if __name__ == "__main__":
    enable_utf8_console()
    main()
