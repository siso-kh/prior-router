import json
import os
import asyncio
import datetime
import argparse
import sys
import time
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from src.llm_circuit_router.config import settings

PENDING_FILE = "pending.json"
LEDGER_FILE = "reliability_ledger.json"

FAILURE_THRESHOLD = 3
QUARANTINE_DURATION_SECS = 900  # 15 minutes timeout

def load_json_file(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to read file '{filepath}': {e}")
        return {}

def save_json_output(filepath: str, data: dict):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error writing to {filepath}: {e}")

async def test_single_model(slug: str, model_info: dict, delay: float, ledger: dict, lock: asyncio.Lock):
    """Initializes an independent client channel and executes a tracked, rolling check pass."""
    await asyncio.sleep(delay)
    
    provider = model_info.get("provider", "unknown").lower()
    print(f"🔄 Testing: {slug}...")

    # Load/initialize ledger record layout block 
    async with lock:
        if slug not in ledger:
            ledger[slug] = {
                "provider": model_info["provider"],
                "base_url": model_info["base_url"],
                "context_length": model_info["context_length"],
                "success_count": 0,
                "failure_count": 0,
                "reliability_score": 1.0, # Start with perfect score
                "consecutive_failures": 0,
                "quarantined_until": None,
                "last_tested": None
            }
        record = ledger[slug]

    # Resolve token permissions safely
    api_key = model_info.get("api_key") or settings.NARA_API_KEY if "nara" in provider else settings.OPENROUTER_API_KEY

    llm = ChatOpenAI(
        model=slug,
        api_key=api_key,
        base_url=model_info["base_url"],
        temperature=0.0,
        max_retries=0
    )

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    success = False
    
    try:
        response = await llm.ainvoke([HumanMessage(content="Respond with just the single word 'ONLINE'.")])
        if response.content.strip():
            success = True
            print(f"✅ {slug:<45} -> ONLINE")
    except Exception as e:
        print(f"❌ {slug:<45} -> Down ({str(e)[:40]}...)")

    async with lock:
        # 🧠 METRIC UPDATE AND ROLLING CALCULATION ENGINE
        if success:
            record["success_count"] += 1
            record["consecutive_failures"] = 0
            record["quarantined_until"] = None
        else:
            record["failure_count"] += 1
            record["consecutive_failures"] += 1
            
            # Trip circuit breaker if consecutive failure threshold is breached
            if record["consecutive_failures"] >= FAILURE_THRESHOLD:
                quarantine_expiry = time.time() + QUARANTINE_DURATION_SECS
                record["quarantined_until"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(quarantine_expiry))
                print(f"🚨 [CIRCUIT TRIPPED] {slug} quarantined due to excessive flaky behavior.")

        # Calculate Rolling Reliability Score
        total_runs = record["success_count"] + record["failure_count"]
        record["reliability_score"] = round(record["success_count"] / total_runs, 3)
        record["last_tested"] = timestamp
        
        # Save structural checkpoint update instantly
        save_json_output(LEDGER_FILE, ledger)

async def main():
    parser = argparse.ArgumentParser(description="LLM Reliability Engine Suite")
    parser.add_argument("--sweep", action="store_true", help="Execute status sweep check on all registered profiles")
    args = parser.parse_args()

    ledger = load_json_file(LEDGER_FILE)
    
    # Identify our candidate source profiles pool
    if args.sweep and ledger:
        print(f"🔄 [LEDGER SWEEP] Re-evaluating existing registry ledger data...")
        candidates = ledger
    else:
        print(f"🚀 [STANDARD OPERATION] Importing newly discovered profiles from '{PENDING_FILE}'...")
        candidates = load_json_file(PENDING_FILE)

    if not candidates:
        print("⚠️ Warning: No target models found to evaluate.")
        return

    state_lock = asyncio.Lock()
    tasks = [test_single_model(slug, data, idx * 0.6, ledger, state_lock) for idx, (slug, data) in enumerate(candidates.items())]

    print(f"⚡ Processing updates across {len(tasks)} models. Synchronizing live ledger...\n")
    await asyncio.gather(*tasks)

    # 📋 DISPLAY RANKED DIRECTORY REPORT CARD TERMINAL INTERFACE
    print("\n🏆 Live Reliability Ranking Report Card:")
    print("=" * 85)
    
    # Sort active models by score descending
    ranked_list = sorted(ledger.items(), key=lambda x: x[1]["reliability_score"], reverse=True)
    
    for idx, (slug, data) in enumerate(ranked_list):
        q_status = f"🚫 QUARANTINED until {data['quarantined_until']}" if data['quarantined_until'] else "🟢 ACTIVE"
        print(f"[{idx+1}] {slug:<45} | Score: {data['reliability_score']:.3f} | Success/Fails: {data['success_count']}/{data['failure_count']} | {q_status}")
    print("=" * 85)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
