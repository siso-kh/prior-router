import os
import json
import asyncio
from src.llm_circuit_router.discovery import ModelDiscoveryEngine
from src.llm_circuit_router.config import settings 

# Target file configuration matching your testing engine loop specifications
PENDING_FILE = "pending.json"

async def main():
    # Pass multiple keys seamlessly into the aggregating tool loop
    my_keys = [
        {
            "provider": "openrouter",
            "api_key": settings.OPENROUTER_API_KEY,
            "base_url": settings.OPENROUTER_BASE_URL
        },
        {
             "provider": "routerbynara",
             "api_key": settings.NARA_API_KEY,
             "base_url": settings.NARA_BASE_URL
        }
    ]

    engine = ModelDiscoveryEngine(provider_credentials=my_keys)
    free_models = await engine.get_all_free_models()

    print(f"\n📊 Total Aggregated Multi-Provider Free Catalog Size: {len(free_models)}")
    print("=" * 70)
    for index, item in enumerate(free_models):
        print(f"[{index + 1}] Model: {item['model_name']}")
        print(f"    Provider: {item['provider'].upper()} | Context Limit: {item['context_length']} tokens")
    print("=" * 70)

    # 💾 SAVE STAGE: Structuring and logging the collected dataset into pending.json
    print(f"\n📂 Exporting raw candidate matrix to '{PENDING_FILE}' for downstream verification...")
    
    pending_payload = {}
    for item in free_models:
        model_slug = item["model_name"]
        pending_payload[model_slug] = {
            "model_name": model_slug,
            "provider": item["provider"],
            "base_url": item["base_url"],
            "api_key": item["api_key"], # Handed down securely to permit independent test execution blocks
            "context_length": item["context_length"],
            "status": "pending",        # Ready for your classification routing loops
            "last_tested": None
        }

    try:
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending_payload, f, indent=2, ensure_ascii=False)
        print(f"✅ Successfully wrote {len(pending_payload)} models into {PENDING_FILE}!")
    except Exception as e:
        print(f"❌ Failed to write file: {e}")

if __name__ == "__main__":
    asyncio.run(main())
