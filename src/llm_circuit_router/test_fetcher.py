import asyncio
from src.llm_circuit_router.benchmarks_fetcher import LiveBenchmarkFetcher

async def verify_fetcher_operations():
    print("🚀 Initializing isolated live benchmark lookup sweep test...")
    fetcher = LiveBenchmarkFetcher()
    
    catalog = await fetcher.fetch_live_matrix()
    
    if not catalog:
        print("❌ Test Failed: Could not populate the live matrix maps registry cache.")
        return
        
    print("\n🔍 Validating Data Structure (Printing first 3 entries found):")
    print("=" * 80)
    
    sample_keys = list(catalog.keys())[:10]
    for idx, slug in enumerate(sample_keys):
        item = catalog[slug]
        print(f"[{idx+1}] Model ID Slug: {slug}")
        print(f"    Display Name: {item['name']}")
        print(f"    Context Window capability: {item['context_length']} tokens")
        print(f"    Pricing Metrics Object: {item['pricing']}")
        print("-" * 80)
        
    print("✅ Local Fetcher configuration test complete. Ready for integration loops!")

if __name__ == "__main__":
    asyncio.run(verify_fetcher_operations())
