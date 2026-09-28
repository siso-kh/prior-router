"""Download the raw Artificial Analysis evaluation snapshot to local disk."""

from __future__ import annotations

import requests

from src.llm_circuit_router.config import get_settings
from src.llm_circuit_router.console import enable_utf8_console
from src.llm_circuit_router.storage import RAW_BENCHMARKS_FILE, save_json

BENCHMARKS_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"


def download_benchmarks_to_file(output_file: str = RAW_BENCHMARKS_FILE) -> None:
    """Fetch the raw evaluation matrix and write it to ``output_file``."""
    headers = {
        "x-api-key": get_settings().BENCHMARK_API_KEY,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LLM-Circuit-Router",
    }

    print("📡 Fetching live evaluation matrix from Artificial Analysis API...")
    try:
        response = requests.get(BENCHMARKS_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ Server error {response.status_code}: {response.text[:150]}")
            return

        payload = response.json()
        save_json(output_file, payload)
        print(f"✅ Success! Saved raw catalog into: '{output_file}'")
        print(f"📊 Total items extracted: {len(payload.get('data', []))}")
    except Exception as exc:  # noqa: BLE001 - surface any network failure to the CLI
        print(f"❌ Request failed: {exc}")


if __name__ == "__main__":
    enable_utf8_console()
    download_benchmarks_to_file()
