"""Discover free, zero-priced model endpoints across supported providers."""

from __future__ import annotations

import traceback
from typing import Any, Dict, List

import httpx

# A single provider credential block as accepted by ModelDiscoveryEngine.
ProviderCredentials = Dict[str, str]
ModelRecord = Dict[str, Any]


class ModelDiscoveryEngine:
    """Aggregates free models from every provider it has a driver for."""

    def __init__(self, provider_credentials: List[ProviderCredentials]) -> None:
        """
        Args:
            provider_credentials: One entry per provider, e.g.::

                [
                    {"provider": "openrouter", "api_key": "<openrouter-key>",
                     "base_url": "https://openrouter.ai/api/v1"},
                    {"provider": "bynara", "api_key": "<bynara-key>",
                     "base_url": "https://router.bynara.id/v1"},
                ]
        """
        self.credentials = provider_credentials

    async def get_all_free_models(self) -> List[ModelRecord]:
        """Return every free model reachable through the configured providers."""
        aggregated_free_catalog: List[ModelRecord] = []

        async with httpx.AsyncClient(follow_redirects=True) as client:
            for cred in self.credentials:
                provider = cred.get("provider", "unknown").lower().strip()
                api_key = cred.get("api_key")
                base_url = cred.get("base_url", "").rstrip("/")

                if not api_key or not base_url:
                    print(
                        f"⚠️ Skipping invalid config credential block for: {provider}"
                    )
                    continue

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "LLM-Circuit-Router-Discovery",
                }

                if "openrouter" in provider:
                    models = await self._discover_openrouter(
                        client, base_url, api_key, headers
                    )
                    aggregated_free_catalog.extend(models)
                elif "bynara" in provider or "nara" in provider:
                    models = await self._discover_bynara(
                        client, base_url, api_key, headers
                    )
                    aggregated_free_catalog.extend(models)
                else:
                    print(
                        f"⚠️ Provider '{provider}' has no discovery driver yet. "
                        "Skipping..."
                    )

        return aggregated_free_catalog

    async def _discover_openrouter(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        headers: Dict[str, str],
    ) -> List[ModelRecord]:
        """Discover zero-priced models from OpenRouter's ``/models`` catalog."""
        free_models: List[ModelRecord] = []
        target_url = f"{base_url}/models"

        print(f"📡 [Driver: OpenRouter] Fetching registry from {target_url}...")
        try:
            response = await client.get(target_url, headers=headers, timeout=12)
            if response.status_code != 200:
                print(
                    f"❌ OpenRouter returned status {response.status_code}: "
                    f"{response.text[:100]}"
                )
                return []

            for model in response.json().get("data", []):
                pricing = model.get("pricing", {})
                prompt_cost = float(pricing.get("prompt", 0))
                completion_cost = float(pricing.get("completion", 0))

                if prompt_cost == 0.0 and completion_cost == 0.0:
                    free_models.append(
                        {
                            "model_name": model.get("id"),
                            "api_key": api_key,
                            "base_url": base_url,
                            "provider": "openrouter",
                            "context_length": model.get("context_length", 0),
                        }
                    )
            print(
                f"✅ OpenRouter Driver complete. Found {len(free_models)} free endpoints."
            )
        except Exception as exc:  # noqa: BLE001 - a driver failure must not abort discovery
            print(f"❌ OpenRouter Driver execution error: {exc}")

        return free_models

    async def _discover_bynara(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        headers: Dict[str, str],
    ) -> List[ModelRecord]:
        """Discover available plan models from Bynara's ``/v1/models`` API."""
        free_models: List[ModelRecord] = []

        if base_url.endswith("/v1"):
            target_url = f"{base_url}/models"
            actual_base = base_url
        elif "/v1" in base_url:
            target_url = f"{base_url.split('/v1')[0]}/v1/models"
            actual_base = base_url
        else:
            target_url = f"{base_url}/v1/models"
            actual_base = f"{base_url}/v1"

        print(f"📡 [Driver: Bynara] Fetching backend API registry from {target_url}...")
        try:
            response = await client.get(target_url, headers=headers, timeout=12)
            if response.status_code != 200:
                print(
                    f"❌ Bynara API returned error status {response.status_code}. "
                    f"Details: {response.text[:150]}"
                )
                return []

            data = response.json()
            models_list = data.get("data", []) if isinstance(data, dict) else data

            for model in models_list:
                model_id = model.get("id")
                name_lower = model_id.lower()
                pricing = model.get("pricing", {})

                # Bynara labels free-tier models explicitly (e.g. a "-free" suffix)
                # and sometimes omits pricing entirely for plan-included models.
                is_free_suffix = "free" in name_lower
                is_free_price = bool(pricing) and (
                    float(pricing.get("prompt", 0)) == 0.0
                    and float(pricing.get("completion", 0)) == 0.0
                )

                if is_free_suffix or is_free_price or not pricing:
                    free_models.append(
                        {
                            "model_name": model_id,
                            "api_key": api_key,
                            "base_url": actual_base,
                            "provider": "bynara",
                            "context_length": model.get("context_length", 0),
                        }
                    )
            print(
                "✅ Bynara Driver complete. Extracted "
                f"{len(free_models)} available plan models."
            )
        except ValueError:
            print("❌ Bynara parse crash: received web HTML instead of JSON payload.")
        except Exception:  # noqa: BLE001 - a driver failure must not abort discovery
            print(f"❌ Bynara Driver execution error details:\n{traceback.format_exc()}")

        return free_models
