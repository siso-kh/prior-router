import httpx
import traceback
from typing import List, Dict, Any

class ModelDiscoveryEngine:
    def __init__(self, provider_credentials: List[Dict[str, str]]):
        """
        Expects a list of provider configuration credential dictionaries:
        [
            {"provider": "openrouter", "api_key": "sk-or-...", "base_url": "https://openrouter.ai"},
            {"provider": "bynara", "api_key": "nar-...", "base_url": "https://router.bynara.id/v1"}
        ]
        """
        self.credentials = provider_credentials

    async def get_all_free_models(self) -> List[Dict[str, Any]]:
        """Iterates through keys and calls the specific driver function for major providers."""
        aggregated_free_catalog = []

        # follow_redirects=True ensures HTTP routing blocks resolve smoothly
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for cred in self.credentials:
                provider = cred.get("provider", "unknown").lower().strip()
                api_key = cred.get("api_key")
                base_url = cred.get("base_url", "").rstrip('/')

                if not api_key or not base_url:
                    print(f"⚠️ Skipping invalid config credential block for: {provider}")
                    continue

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "LLM-Circuit-Router-Discovery"
                }

                if "openrouter" in provider:
                    models = await self._discover_openrouter(client, base_url, api_key, headers)
                    aggregated_free_catalog.extend(models)
                elif "bynara" in provider or "nara" in provider:
                    models = await self._discover_bynara(client, base_url, api_key, headers)
                    aggregated_free_catalog.extend(models)
                else:
                    print(f"⚠️ Provider '{provider}' does not have a custom driver function yet. Skipping...")

        return aggregated_free_catalog

    async def _discover_openrouter(self, client: httpx.AsyncClient, base_url: str, api_key: str, headers: dict) -> List[Dict[str, Any]]:
        """Custom discovery driver optimized for OpenRouter's /api/v1/models catalog endpoint."""
        free_models = []
        target_url = f"{base_url}/models"
        
        print(f"📡 [Driver: OpenRouter] Fetching registry from {target_url}...")
        try:
            response = await client.get(target_url, headers=headers, timeout=12)
            if response.status_code != 200:
                print(f"❌ OpenRouter returned status {response.status_code}: {response.text[:100]}")
                return []

            data = response.json()
            for model in data.get("data", []):
                model_id = model.get("id")
                pricing = model.get("pricing", {})
                
                prompt_cost = float(pricing.get("prompt", 0))
                completion_cost = float(pricing.get("completion", 0))

                if prompt_cost == 0.0 and completion_cost == 0.0:
                    free_models.append({
                        "model_name": model_id,
                        "api_key": api_key,
                        "base_url": base_url,
                        "provider": "openrouter",
                        "context_length": model.get("context_length", 0)
                    })
            print(f"✅ OpenRouter Driver complete. Found {len(free_models)} free endpoints.")
        except Exception as e:
            print(f"❌ OpenRouter Driver execution error: {e}")
            
        return free_models

    async def _discover_bynara(self, client: httpx.AsyncClient, base_url: str, api_key: str, headers: dict) -> List[Dict[str, Any]]:
        """Custom discovery driver optimized for Bynara's true /v1/models background API path."""
        free_models = []
        
        if not base_url.endswith('/v1'):
            target_url = f"{base_url}/v1/models" if "/v1" not in base_url else f"{base_url.split('/v1')[0]}/v1/models"
            actual_base = f"{base_url}/v1" if "/v1" not in base_url else base_url
        else:
            target_url = f"{base_url}/models"
            actual_base = base_url
        
        print(f"📡 [Driver: Bynara] Fetching backend API registry from {target_url}...")
        try:
            response = await client.get(target_url, headers=headers, timeout=12)
            
            if response.status_code != 200:
                print(f"❌ Bynara API returned error status {response.status_code}. Details: {response.text[:150]}")
                return []

            data = response.json()
            models_list = data.get("data", []) if isinstance(data, dict) else data
            for model in models_list:
                model_id = model.get("id")
                name_lower = model_id.lower()
                
                # Bynara labels free-tier models explicitly (like '-free' suffix)
                is_free_suffix = "free" in name_lower or "-free" in name_lower
                
                pricing = model.get("pricing", {})
                is_free_price = pricing and float(pricing.get("prompt", 0)) == 0.0 and float(pricing.get("completion", 0)) == 0.0

                # Since NaraRouter allows free billing routing across its active base tier options,
                # if pricing metrics keys are left blank by their config, map them cleanly via names.
                if is_free_suffix or is_free_price or not pricing:
                    free_models.append({
                        "model_name": model_id,
                        "api_key": api_key,
                        "base_url": actual_base, 
                        "provider": "bynara",
                        "context_length": model.get("context_length", 0)
                    })
            print(f"✅ Bynara Driver complete. Successfully extracted available plan models.")
        except ValueError:
            print("❌ Bynara parse crash: Still received web layout HTML instead of JSON data payload.")
        except Exception as e:
            # ✅ FIXED: Printing the full traceback error explicitly to capture exactly why it triggers a fallback
            print(f"❌ Bynara Driver execution error details:\n{traceback.format_exc()}")
            
        return free_models
