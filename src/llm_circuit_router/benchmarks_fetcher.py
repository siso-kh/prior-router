"""Translate raw Artificial Analysis evaluations into 0-100 task scores."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

BenchmarkScores = Dict[str, float]
ParsedMatrix = Dict[str, Dict[str, Any]]

# Keywords that let us infer a capability the source data does not expose.
CODING_HINTS = ("code",)
REASONING_HINTS = ("reason", "opus")
VISION_HINTS = ("vision", "vl", "clip", "agnes", "flash")

DEFAULT_INTELLIGENCE_PROXY = 60.0


class LiveBenchmarkFetcher:
    """Builds a per-model capability matrix from Artificial Analysis data."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_url = "https://artificialanalysis.ai"
        self.api_key = api_key

    def _normalize_score(self, value: Any, multiplier: float = 1.0) -> float:
        """Coerce ``value`` to a float on a 0-100 scale, or ``0.0`` if unusable.

        Values already expressed as a 0-1 fraction (e.g. ``hle``) are scaled to
        percentages; everything else is multiplied by ``multiplier`` and capped.
        """
        if value is None:
            return 0.0
        try:
            val = float(value)
        except (ValueError, TypeError):
            return 0.0
        if 0.0 <= val <= 1.0 and multiplier == 1.0:
            return round(val * 100, 1)
        return round(min(val * multiplier, 100.0), 1)

    def _classify_single_model(self, item: Dict[str, Any]) -> BenchmarkScores:
        """Map one raw model record onto general/coding/reasoning/vision scores."""
        slug = item.get("slug", "").lower()
        name = item.get("name", "").lower()
        evals = item.get("evaluations", {})

        # 1. GENERAL — the core intelligence index, with a safe fallback.
        general_score = self._normalize_score(
            evals.get("artificial_analysis_intelligence_index")
        )
        if general_score == 0.0:
            general_score = DEFAULT_INTELLIGENCE_PROXY

        # 2. CODING — LiveCodeBench > coding index > intelligence proxy.
        livecodebench = self._normalize_score(evals.get("livecodebench"))
        coding_index = self._normalize_score(evals.get("artificial_analysis_coding_index"))
        if livecodebench > 0:
            coding_score = livecodebench
        elif coding_index > 0:
            coding_score = coding_index
        elif any(hint in slug for hint in CODING_HINTS):
            coding_score = general_score * 1.1
        else:
            coding_score = general_score * 0.95

        # 3. REASONING — HLE > SciCode > math index > intelligence proxy.
        hle = self._normalize_score(evals.get("hle"))
        scicode = self._normalize_score(evals.get("scicode"))
        math_index = self._normalize_score(evals.get("artificial_analysis_math_index"))
        if hle > 0:
            reasoning_score = hle
        elif scicode > 0:
            reasoning_score = scicode
        elif math_index > 0:
            reasoning_score = math_index
        elif any(hint in slug for hint in REASONING_HINTS):
            reasoning_score = general_score * 1.15
        else:
            reasoning_score = general_score * 0.95

        # 4. VISION — inferred from identifier keywords.
        vision_score = 0.0
        if any(hint in slug or hint in name for hint in VISION_HINTS):
            vision_score = max(75.0, general_score * 1.05)

        return {
            "general": round(min(general_score, 100.0), 1),
            "coding": round(min(coding_score, 100.0), 1),
            "reasoning": round(min(reasoning_score, 100.0), 1),
            "vision": round(min(vision_score, 100.0), 1),
        }

    async def fetch_live_matrix(self, local_json_path: Optional[str] = None) -> ParsedMatrix:
        """Return a slug-keyed capability matrix.

        Prefers a local raw snapshot at ``local_json_path``; falls back to the
        live API when one is configured and the snapshot is unavailable.
        """
        raw_data_list: List[Dict[str, Any]] = []

        if local_json_path and os.path.exists(local_json_path):
            try:
                with open(local_json_path, "r", encoding="utf-8") as handle:
                    raw_data_list = json.load(handle).get("data", [])
            except (OSError, json.JSONDecodeError, AttributeError):
                raw_data_list = []

        if not raw_data_list and self.api_key:
            headers = {"x-api-key": self.api_key, "Accept": "application/json"}
            async with httpx.AsyncClient(follow_redirects=True) as client:
                try:
                    response = await client.get(self.api_url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        raw_data_list = response.json().get("data", [])
                except Exception:  # noqa: BLE001 - degrade to baseline fallbacks
                    print("⚠️ Remote lookup error. Using baseline fallbacks.")

        matrix: ParsedMatrix = {}
        for item in raw_data_list:
            slug = item.get("slug")
            if slug:
                matrix[slug.lower()] = {
                    "name": item.get("name"),
                    "scores": self._classify_single_model(item),
                    "pricing": item.get("pricing", {}),
                }
        return matrix
