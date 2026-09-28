# src/llm_circuit_router/benchmarks_fetcher.py
import httpx
from typing import Dict, Any, List
import json
import os

class LiveBenchmarkFetcher:
    def __init__(self, api_key: str = None):
        self.api_url = "https://artificialanalysis.ai"
        self.api_key = api_key

    def _normalize_score(self, value: Any, multiplier: float = 1.0) -> float:
        """Safely extracts a numeric float and normalizes it out of 100 max points."""
        if value is None:
            return 0.0
        try:
            val = float(value)
            # If it's already a 0-1 decimal index like hle or scicode, scale it to percentage
            if 0.0 <= val <= 1.0 and multiplier == 1.0:
                return round(val * 100, 1)
            return round(min(val * multiplier, 100.0), 1)
        except (ValueError, TypeError):
            return 0.0

    def _classify_single_model(self, item: Dict[str, Any]) -> Dict[str, float]:
        """
        Applies hierarchical scoring logic to map evaluations into 
        unambiguous capabilities scores out of 100.
        """
        slug = item.get("slug", "").lower()
        name = item.get("name", "").lower()
        evals = item.get("evaluations", {})
        
        # Extract base baseline benchmark metrics safely
        intel_index = self._normalize_score(evals.get("artificial_analysis_intelligence_index"))
        if intel_index == 0.0:
            intel_index = 60.0  # Safe foundational default threshold score

        # 1. GENERAL SCALE (Core Intelligence Index Mapping)
        general_score = intel_index

        # 2. CODING SCALE (Priority: LiveCodeBench -> Coding Index -> Intelligence Proxy)
        lcb = self._normalize_score(evals.get("livecodebench"))
        coding_idx = self._normalize_score(evals.get("artificial_analysis_coding_index"))
        
        if lcb > 0:
            coding_score = lcb
        elif coding_idx > 0:
            coding_score = coding_idx
        else:
            # Fall back to base intelligence proxy, boosting if model slug contains code flags
            coding_score = general_score * 1.1 if "code" in slug else general_score * 0.95
        
        # 3. REASONING SCALE (Priority: HLE -> SciCode -> Math Indexes)
        hle = self._normalize_score(evals.get("hle"))
        scicode = self._normalize_score(evals.get("scicode"))
        math_idx = self._normalize_score(evals.get("artificial_analysis_math_index"))
        
        if hle > 0:
            reasoning_score = hle
        elif scicode > 0:
            reasoning_score = scicode
        elif math_idx > 0:
            reasoning_score = math_idx
        else:
            reasoning_score = general_score * 1.15 if "reason" in slug or "opus" in slug else general_score * 0.95

        # 4. VISION SCALE (Determined structurally by model identifier keywords mapping)
        vision_score = 0.0
        if any(term in slug or term in name for term in ["vision", "vl", "clip", "agnes", "flash"]):
            # Give flash/vision models a high capability standing for image processing
            vision_score = max(75.0, general_score * 1.05)

        return {
            "general": round(min(general_score, 100.0), 1),
            "coding": round(min(coding_score, 100.0), 1),
            "reasoning": round(min(reasoning_score, 100.0), 1),
            "vision": round(min(vision_score, 100.0), 1)
        }

    async def fetch_live_matrix(self, local_json_path: str = None) -> Dict[str, Any]:
        """
        Fetches or loads raw Artificial Analysis schema arrays and parses them 
        into searchable, clean task capabilities dictionaries.
        """
        raw_data_list = []
        
        # Optional: Load from local saved cache file to speed up execution
        if local_json_path and os.path.exists(local_json_path):
            try:
                with open(local_json_path, 'r', encoding='utf-8') as f:
                    file_payload = json.load(f)
                    raw_data_list = file_payload.get("data", [])
            except Exception:
                pass

        # Otherwise crawl live endpoint using your key headers
        if not raw_data_list and self.api_key:
            headers = {"x-api-key": self.api_key, "Accept": "application/json"}
            async with httpx.AsyncClient(follow_redirects=True) as client:
                try:
                    response = await client.get(self.api_url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        raw_data_list = response.json().get("data", [])
                except Exception:
                    print("⚠️ Remote lookup error. Using baseline fallbacks.")

        # Transform raw profile data array objects into structured metrics
        final_scores_matrix = {}
        for item in raw_data_list:
            slug = item.get("slug")
            if slug:
                final_scores_matrix[slug.lower()] = {
                    "name": item.get("name"),
                    "scores": self._classify_single_model(item),
                    "pricing": item.get("pricing", {})
                }
                
        return final_scores_matrix
