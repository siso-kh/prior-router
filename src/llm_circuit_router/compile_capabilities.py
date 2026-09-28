import asyncio
import json
import os
import datetime
from src.llm_circuit_router.benchmarks_fetcher import LiveBenchmarkFetcher

# Config inputs matching your local raw metrics extraction dump
RAW_SOURCE_FILE = "artificial_analysis_models.json"
OUTPUT_CAPABILITIES_FILE = "model_capabilities.json"

async def main():
    print("🚀 Initializing Dynamic Capabilities Matrix Compiler...")
    
    # 1. Initialize our standalone scoring driver utility framework
    fetcher = LiveBenchmarkFetcher()
    
    # Check if raw cache log copy exists on local disk
    if not os.path.exists(RAW_SOURCE_FILE):
        print(f"❌ Error: Raw benchmark snapshot cache file '{RAW_SOURCE_FILE}' missing.")
        print("💡 Hint: Execute your cURL download or fetcher script first to dump raw metrics.")
        return
        
    # 2. Extract and translate raw evaluations matrix profiles into unified 0-100 metrics
    parsed_matrix = await fetcher.fetch_live_matrix(local_json_path=RAW_SOURCE_FILE)
    
    if not parsed_matrix:
        print("❌ Compilation Aborted: Could not parse structural records from target cache file.")
        return
        
    print(f"📊 Compiling {len(parsed_matrix)} structured capability profile records mapping metrics...")
    
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    compiled_catalog = {}
    
    for slug, profile in parsed_matrix.items():
        # Identify the best performance capability type natively
        scores = profile["scores"]
        best_domain = max(scores, key=scores.get)
        
        # Structure the final standardized profile blueprint layout entry
        compiled_catalog[slug] = {
            "model_name": slug,
            "display_name": profile["name"],
            "reliability_score": 1.0,  # Default baseline standing; hot-swapped by test routines later
            "benchmarks": scores,
            "inferred_specialization": best_domain if scores[best_domain] > 0.0 else "general",
            "pricing": profile["pricing"],
            "last_updated": timestamp
        }
        
    # 3. Save the clean structural database matrix back to standard JSON records disk cache
    try:
        with open(OUTPUT_CAPABILITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(compiled_catalog, f, indent=2, ensure_ascii=False)
        print(f"======================================================================")
        print(f"✅ Success! Generated capabilities lookup registry index map.")
        print(f"📂 Operational profiles saved inside: '{OUTPUT_CAPABILITIES_FILE}'")
        print(f"======================================================================")
    except Exception as e:
        print(f"❌ Storage file system serialization error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
