"""Discover free models across all providers and stage them in ``pending.json``."""

from __future__ import annotations

import asyncio

from src.llm_circuit_router.config import get_settings
from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.discovery import ModelDiscoveryEngine
from src.llm_circuit_router.storage import PENDING_FILE, JsonDict, save_json


def build_provider_credentials() -> list[dict]:
    """Assemble the provider credential blocks from the environment."""
    settings = get_settings()
    return [
        {
            "provider": "openrouter",
            "api_key": settings.OPENROUTER_API_KEY,
            "base_url": settings.OPENROUTER_BASE_URL,
        },
        {
            "provider": "routerbynara",
            "api_key": settings.NARA_API_KEY,
            "base_url": settings.NARA_BASE_URL,
        },
    ]


def to_pending_payload(free_models: list[dict]) -> JsonDict:
    """Convert discovered models into the ``pending.json`` staging shape."""
    payload: JsonDict = {}
    for model in free_models:
        slug = model["model_name"]
        payload[slug] = {
            "model_name": slug,
            "provider": model["provider"],
            "base_url": model["base_url"],
            # Handed down so the health-check stage can test each endpoint directly.
            "api_key": model["api_key"],
            "context_length": model["context_length"],
            "status": "pending",
            "last_tested": None,
        }
    return payload


async def main() -> None:
    """Run discovery and export the candidate matrix."""
    engine = ModelDiscoveryEngine(provider_credentials=build_provider_credentials())
    free_models = await engine.get_all_free_models()

    print(f"\n📊 Total Aggregated Multi-Provider Free Catalog Size: {len(free_models)}")
    print("=" * 70)
    for index, item in enumerate(free_models):
        print(f"[{index + 1}] Model: {item['model_name']}")
        print(
            f"    Provider: {item['provider'].upper()} | "
            f"Context Limit: {item['context_length']} tokens"
        )
    print("=" * 70)

    payload = to_pending_payload(free_models)
    print(f"\n📂 Exporting {len(payload)} candidate models to '{PENDING_FILE}'...")
    try:
        save_json(PENDING_FILE, payload)
        print(f"✅ Successfully wrote {len(payload)} models into {PENDING_FILE}!")
    except OSError as exc:
        print(f"❌ Failed to write file: {exc}")


if __name__ == "__main__":
    enable_utf8_console()
    asyncio.run(main())
