"""Merge discovery, health, and capability data into the final routing registry."""

from __future__ import annotations

from typing import Dict

from src.llm_circuit_router.config import get_settings
from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.storage import (
    CAPABILITIES_FILE,
    FINAL_REGISTRY_FILE,
    LEDGER_FILE,
    PENDING_FILE,
    JsonDict,
    load_json,
    save_json,
)
from src.llm_circuit_router.timeutils import utc_now_iso

# Baseline capability profile used when a model has no benchmark match.
DEFAULT_BENCHMARKS: Dict[str, float] = {
    "general": 60.0,
    "coding": 55.0,
    "reasoning": 58.0,
    "vision": 0.0,
}

# Composite scores collapse to zero once a model is quarantined or repeatedly failing.
FAILURE_CIRCUIT_THRESHOLD = 3


def match_benchmark_scores(slug: str, capabilities_matrix: JsonDict) -> Dict[str, float]:
    """Find the best available benchmark profile for ``slug``.

    Tries a direct lookup, then a fuzzy match on the model name, and finally
    falls back to keyword-derived defaults so no model is left unscored.
    """
    slug_lower = slug.lower()

    if slug_lower in capabilities_matrix:
        return capabilities_matrix[slug_lower]["benchmarks"]

    for cap_slug, cap_data in capabilities_matrix.items():
        clean_cap_slug = cap_slug.split("/")[-1].replace(":free", "")
        if clean_cap_slug in slug_lower or cap_slug in slug_lower:
            return cap_data["benchmarks"]

    default_scores = dict(DEFAULT_BENCHMARKS)
    if "code" in slug_lower:
        default_scores.update({"coding": 85.0, "reasoning": 70.0})
    elif "reason" in slug_lower or "nemotron" in slug_lower:
        default_scores.update({"reasoning": 88.0, "general": 72.0})
    elif "vision" in slug_lower or "flash" in slug_lower or "agnes" in slug_lower:
        default_scores.update({"vision": 80.0, "general": 70.0})
    return default_scores


def build_registry() -> JsonDict:
    """Compile every active candidate into a single routing registry mapping."""
    candidates = load_json(PENDING_FILE)
    ledger = load_json(LEDGER_FILE)
    capabilities = load_json(CAPABILITIES_FILE)

    if not candidates:
        print(f"❌ Aborted: candidate source '{PENDING_FILE}' is empty or missing.")
        return {}

    timestamp = utc_now_iso()
    print(f"📦 Packaging structural metrics profiles across {len(candidates)} models...")

    registry: JsonDict = {}
    for slug, meta in candidates.items():
        provider = meta.get("provider", "unknown").lower()

        # Prefer the credential captured at discovery time, else fall back to env.
        api_key = meta.get("api_key")
        if not api_key:
            settings = get_settings()
            api_key = (
                settings.NARA_API_KEY if "nara" in provider else settings.OPENROUTER_API_KEY
            )

        ledger_record = ledger.get(slug, {})
        reliability = float(ledger_record.get("reliability_score", 1.0))
        consecutive_failures = int(ledger_record.get("consecutive_failures", 0))
        quarantined_until = ledger_record.get("quarantined_until")

        benchmarks = match_benchmark_scores(slug, capabilities)

        # Composite score = benchmark quality weighted by measured reliability.
        # A tripped circuit breaker collapses every domain to zero.
        tripped = bool(quarantined_until) or consecutive_failures >= FAILURE_CIRCUIT_THRESHOLD
        composite_routing_scores = {
            domain: 0.0 if tripped else round(score * reliability, 1)
            for domain, score in benchmarks.items()
        }

        registry[slug] = {
            "model_name": slug,
            "provider": meta["provider"],
            "base_url": meta["base_url"],
            "api_key": api_key,
            "context_length": meta["context_length"],
            "reliability": {
                "score": reliability,
                "success_count": ledger_record.get("success_count", 0),
                "failure_count": ledger_record.get("failure_count", 0),
                "consecutive_failures": consecutive_failures,
                "quarantined_until": quarantined_until,
            },
            "benchmarks": benchmarks,
            "composite_routing_scores": composite_routing_scores,
            "last_compiled": timestamp,
        }
    return registry


def main() -> None:
    """Compile and persist the master registry."""
    print("🚀 Compiling Master Multi-Provider Unified Registry Database...")
    registry = build_registry()
    if not registry:
        return

    save_json(FINAL_REGISTRY_FILE, registry)

    print("=" * 80)
    print("✅ Success! Master deployment registry cleanly generated.")
    print(f"📂 Complete metadata profiles stored in: '{FINAL_REGISTRY_FILE}'")
    print("=" * 80)


if __name__ == "__main__":
    enable_utf8_console()
    main()
