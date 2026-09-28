"""Compile the raw benchmark snapshot into the capability lookup registry."""

from __future__ import annotations

import asyncio
import os

from src.llm_circuit_router.benchmarks_fetcher import LiveBenchmarkFetcher
from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.storage import (
    CAPABILITIES_FILE,
    RAW_BENCHMARKS_FILE,
    JsonDict,
    save_json,
)
from src.llm_circuit_router.timeutils import utc_now_iso


async def build_capability_catalog() -> JsonDict:
    """Parse the raw snapshot into a standardized capability catalog."""
    fetcher = LiveBenchmarkFetcher()
    parsed_matrix = await fetcher.fetch_live_matrix(local_json_path=RAW_BENCHMARKS_FILE)
    if not parsed_matrix:
        return {}

    timestamp = utc_now_iso()
    catalog: JsonDict = {}
    for slug, profile in parsed_matrix.items():
        scores = profile["scores"]
        best_domain = max(scores, key=scores.get)

        catalog[slug] = {
            "model_name": slug,
            "display_name": profile["name"],
            # Baseline standing; the health-check stage overwrites this in the ledger.
            "reliability_score": 1.0,
            "benchmarks": scores,
            "inferred_specialization": (
                best_domain if scores[best_domain] > 0.0 else "general"
            ),
            "pricing": profile["pricing"],
            "last_updated": timestamp,
        }
    return catalog


async def main() -> None:
    """Compile capabilities and persist them to ``model_capabilities.json``."""
    print("🚀 Initializing Dynamic Capabilities Matrix Compiler...")

    if not os.path.exists(RAW_BENCHMARKS_FILE):
        print(f"❌ Error: raw benchmark snapshot '{RAW_BENCHMARKS_FILE}' missing.")
        print("💡 Hint: run the raw benchmark fetcher first to dump the snapshot.")
        return

    catalog = await build_capability_catalog()
    if not catalog:
        print("❌ Compilation aborted: no structural records could be parsed.")
        return

    print(f"📊 Compiled {len(catalog)} structured capability profiles.")
    save_json(CAPABILITIES_FILE, catalog)
    print("=" * 70)
    print("✅ Success! Generated capabilities lookup registry index map.")
    print(f"📂 Operational profiles saved inside: '{CAPABILITIES_FILE}'")
    print("=" * 70)


if __name__ == "__main__":
    enable_utf8_console()
    asyncio.run(main())
