"""Probe every candidate model and track rolling reliability in the ledger."""

from __future__ import annotations

import argparse
import asyncio
import sys

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.llm_circuit_router.config import get_settings
from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.storage import (
    LEDGER_FILE,
    PENDING_FILE,
    JsonDict,
    load_json,
    save_json,
)
from src.llm_circuit_router.timeutils import utc_after_iso, utc_now_iso

FAILURE_THRESHOLD = 3
QUARANTINE_DURATION_MINUTES = 15

# Concurrency comes from a bounded delay per model; this keeps it configurable.
PROBE_STAGGER_SECS = 0.6


def _new_ledger_record(model_info: JsonDict) -> JsonDict:
    """Build the initial ledger record for a model that has never been tested."""
    return {
        "provider": model_info["provider"],
        "base_url": model_info["base_url"],
        "context_length": model_info["context_length"],
        "success_count": 0,
        "failure_count": 0,
        "reliability_score": 1.0,
        "consecutive_failures": 0,
        "quarantined_until": None,
        "last_tested": None,
    }


def _resolve_api_key(model_info: JsonDict) -> str:
    """Return the credential to use for a model, preferring its own block."""
    provider = model_info.get("provider", "unknown").lower()
    settings = get_settings()
    fallback = settings.NARA_API_KEY if "nara" in provider else settings.OPENROUTER_API_KEY
    return model_info.get("api_key") or fallback


async def probe_model(
    slug: str,
    model_info: JsonDict,
    delay: float,
    ledger: JsonDict,
    lock: asyncio.Lock,
) -> None:
    """Send a trivial prompt to one model and update its ledger record."""
    await asyncio.sleep(delay)
    print(f"🔄 Testing: {slug}...")

    async with lock:
        if slug not in ledger:
            ledger[slug] = _new_ledger_record(model_info)
        record = ledger[slug]

    llm = ChatOpenAI(
        model=slug,
        api_key=_resolve_api_key(model_info),
        base_url=model_info["base_url"],
        temperature=0.0,
        max_retries=0,
    )

    timestamp = utc_now_iso()
    success = False
    try:
        response = await llm.ainvoke(
            [HumanMessage(content="Respond with just the single word 'ONLINE'.")]
        )
        if response.content.strip():
            success = True
            print(f"✅ {slug:<45} -> ONLINE")
    except Exception as exc:  # noqa: BLE001 - any failure is recorded, not raised
        print(f"❌ {slug:<45} -> Down ({str(exc)[:40]}...)")

    async with lock:
        if success:
            record["success_count"] += 1
            record["consecutive_failures"] = 0
            record["quarantined_until"] = None
        else:
            record["failure_count"] += 1
            record["consecutive_failures"] += 1
            if record["consecutive_failures"] >= FAILURE_THRESHOLD:
                record["quarantined_until"] = utc_after_iso(QUARANTINE_DURATION_MINUTES)
                print(f"🚨 [CIRCUIT TRIPPED] {slug} quarantined for flaky behavior.")

        total_runs = record["success_count"] + record["failure_count"]
        record["reliability_score"] = round(record["success_count"] / total_runs, 3)
        record["last_tested"] = timestamp
        save_json(LEDGER_FILE, ledger)


def _select_candidates(sweep: bool) -> JsonDict:
    """Choose which models to probe, based on the requested mode."""
    ledger = load_json(LEDGER_FILE)
    if sweep and ledger:
        print("🔄 [LEDGER SWEEP] Re-evaluating existing registry ledger data...")
        return ledger
    print(f"🚀 [STANDARD OPERATION] Importing profiles from '{PENDING_FILE}'...")
    return load_json(PENDING_FILE)


def _print_report(ledger: JsonDict) -> None:
    """Print the ranked reliability report card."""
    print("\n🏆 Live Reliability Ranking Report Card:")
    print("=" * 85)
    ranked = sorted(
        ledger.items(), key=lambda item: item[1]["reliability_score"], reverse=True
    )
    for index, (slug, data) in enumerate(ranked):
        quarantine = data["quarantined_until"]
        status = f"🚫 QUARANTINED until {quarantine}" if quarantine else "🟢 ACTIVE"
        print(
            f"[{index + 1}] {slug:<45} | Score: {data['reliability_score']:.3f} | "
            f"Success/Fails: {data['success_count']}/{data['failure_count']} | {status}"
        )
    print("=" * 85)


async def main() -> None:
    """Run the health-check sweep and persist the updated ledger."""
    parser = argparse.ArgumentParser(description="LLM Reliability Engine Suite")
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Re-check every model already present in the reliability ledger",
    )
    args = parser.parse_args()

    candidates = _select_candidates(args.sweep)
    if not candidates:
        print("⚠️ Warning: No target models found to evaluate.")
        return

    # The ledger is loaded once and mutated in place; each write persists the whole
    # mapping, so every save is guarded by the same lock.
    ledger = load_json(LEDGER_FILE)
    lock = asyncio.Lock()
    tasks = [
        probe_model(slug, data, index * PROBE_STAGGER_SECS, ledger, lock)
        for index, (slug, data) in enumerate(candidates.items())
    ]

    print(f"⚡ Processing updates across {len(tasks)} models. Syncing live ledger...\n")
    await asyncio.gather(*tasks)
    _print_report(ledger)


if __name__ == "__main__":
    enable_utf8_console()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
