import json
import os
import datetime
from src.llm_circuit_router.config import settings

PENDING_FILE = "pending.json"
LEDGER_FILE = "reliability_ledger.json"
CAPABILITIES_FILE = "model_capabilities.json"
FINAL_REGISTRY_FILE = "final_model_registry.json"

def load_json_file(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_json_output(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error writing to {path}: {e}")

def match_benchmark_scores(slug: str, capabilities_matrix: dict) -> dict:
    """
    Finds the closest benchmark matching entry for a model slug.
    Attempts strict matches first, then falls back to parent architecture signatures.
    """
    slug_lower = slug.lower()
    
    # 1. Look for a clean direct match in our evaluation library
    if slug_lower in capabilities_matrix:
        return capabilities_matrix[slug_lower]["benchmarks"]
        
    # 2. Heuristic fallback: Match by checking if an evaluation profile exists inside the model name
    for cap_slug, cap_data in capabilities_matrix.items():
        clean_cap_slug = cap_slug.split('/')[-1].replace(':free', '')
        if clean_cap_slug in slug_lower or cap_slug in slug_lower:
            return cap_data["benchmarks"]
            
    # 3. Base structural fallbacks if the specific model family hasn't been crawled yet
    default_scores = {"general": 60.0, "coding": 55.0, "reasoning": 58.0, "vision": 0.0}
    if "code" in slug_lower:
        default_scores.update({"coding": 85.0, "reasoning": 70.0})
    elif "reason" in slug_lower or "nemotron" in slug_lower:
        default_scores.update({"reasoning": 88.0, "general": 72.0})
    elif "vision" in slug_lower or "flash" in slug_lower or "agnes" in slug_lower:
        default_scores.update({"vision": 80.0, "general": 70.0})
        
    return default_scores

def main():
    print("🚀 Compiling Master Multi-Provider Unified Registry Database...")

    # Load all standalone pipeline tracking layers
    candidates = load_json_file(PENDING_FILE)
    ledger = load_json_file(LEDGER_FILE)
    capabilities = load_json_file(CAPABILITIES_FILE)

    if not candidates:
        print(f"❌ Aborted: Candidate source file '{PENDING_FILE}' is empty or missing.")
        return

    final_registry = {}
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
    
    print(f"📦 Packaging structural metrics profiles across {len(candidates)} active models...")

    for slug, meta in candidates.items():
        provider = meta.get("provider", "unknown").lower()
        
        # 🔒 Secure Credentials Extraction Loop
        # Merges localized active credentials strings with fallback settings configs
        api_key = meta.get("api_key")
        if not api_key:
            api_key = settings.NARA_API_KEY if "nara" in provider else settings.OPENROUTER_API_KEY

        # 🧠 Health Stats and Performance Extractions
        ledger_record = ledger.get(slug, {})
        reliability = float(ledger_record.get("reliability_score", 1.0))
        consecutive_fails = int(ledger_record.get("consecutive_failures", 0))
        quar_status = ledger_record.get("quarantined_until")

        # Pull true numeric capabilities out of our compiled Artificial Analysis library
        benchmarks = match_benchmark_scores(slug, capabilities)

        # 🎯 Composite Routing Calculation Engine
        # Formulates task priority by balancing benchmark limits against real world key health metrics
        composite_routing_scores = {}
        for domain, score in benchmarks.items():
            if quar_status or consecutive_fails >= 3:
                composite_routing_scores[domain] = 0.0
            else:
                composite_routing_scores[domain] = round(score * reliability, 1)

        # Build entry blueprint
        final_registry[slug] = {
            "model_name": slug,
            "provider": meta["provider"],
            "base_url": meta["base_url"],
            "api_key": api_key,
            "context_length": meta["context_length"],
            "reliability": {
                "score": reliability,
                "success_count": ledger_record.get("success_count", 0),
                "failure_count": ledger_record.get("failure_count", 0),
                "consecutive_failures": consecutive_fails,
                "quarantined_until": quar_status
            },
            "benchmarks": benchmarks,
            "composite_routing_scores": composite_routing_scores,
            "last_compiled": timestamp
        }

    # Commit unified ledger map to disk
    save_json_output(FINAL_REGISTRY_FILE, final_registry)
    
    print("=" * 80)
    print(f"✅ Success! Master deployment registry cleanly generated.")
    print(f"📂 Complete metadata profiles stored in: '{FINAL_REGISTRY_FILE}'")
    print("=" * 80)

if __name__ == "__main__":
    main()
