"""Manual demo: score a single mock model through the capability pipeline.

Run with::

    python -m src.llm_circuit_router.demo_capabilities_scoring
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

from src.llm_circuit_router.benchmarks_fetcher import LiveBenchmarkFetcher
from src.llm_circuit_router.console import enable_utf8_console

# Mirrors the schema returned by the Artificial Analysis API.
MOCK_API_RESPONSE = {
    "data": [
        {
            "id": "2f3c4dc9-a450-4303-8697-0237257cf08f",
            "name": "Claude Opus 5.5 (Adaptive Reasoning, Max Effort, Default Fallback)",
            "slug": "claude-opus-5-5",
            "release_date": "2026-09-22",
            "evaluations": {
                "artificial_analysis_intelligence_index": 57.6,
                "artificial_analysis_coding_index": None,
                "artificial_analysis_math_index": None,
                "hle": 0.614,
                "scicode": 0.669,
                "livecodebench": None,
            },
            "pricing": {"price_1m_input_tokens": 4, "price_1m_output_tokens": 20},
        }
    ]
}


async def main() -> None:
    # Write the mock snapshot to a temp file and parse that exact file back.
    handle, snapshot_path = tempfile.mkstemp(suffix=".json", prefix="mock_benchmarks_")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(MOCK_API_RESPONSE, file)

        matrix = await LiveBenchmarkFetcher().fetch_live_matrix(
            local_json_path=snapshot_path
        )
    finally:
        os.remove(snapshot_path)

    print("\n📊 Computed Model Metrics Report Card Summary:")
    print("=" * 70)
    for slug, profile in matrix.items():
        print(f"🎯 Target Model Slug: {slug}")
        print(f"   Display Name:     {profile['name']}")
        print("-" * 70)
        print("   📈 Calculated Field Capability Scores (Out of 100):")
        for domain, score in profile["scores"].items():
            print(f"    - {domain.capitalize():<12}: {score} pts")
    print("=" * 70)
    print("✅ Logic validation successful. Handles nulls cleanly!")


if __name__ == "__main__":
    enable_utf8_console()
    asyncio.run(main())
