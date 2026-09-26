# src/llm_circuit_router/benchmarks_fetcher.py
import httpx
from typing import Dict, Any

class LiveBenchmarkFetcher:
    def __init__(self, directory_url: str = "https://openrouter.ai/api/v1/models"):
        self.directory_url = directory_url

    async def fetch_live_matrix(self) -> Dict[str, Any]:
        """
        Queries the online directory repository registry to extract live model metadata.
        Returns a dictionary keyed by model identifiers.
        """
        print(f"🌐 [Fetcher] Connecting to remote catalog directory: {self.directory_url}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        try:
            # Use follow_redirects=True to guarantee Cloudflare gateway passes don't block access
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(self.directory_url, headers=headers, timeout=15)
                
                if response.status_code != 200:
                    print(f"❌ [Fetcher] Server returned error response status: {response.status_code}")
                    return {}
                data = response.json()
                models_data = data.get("data", [])
                
                # Transform list array layout into a fast key-value lookup map
                benchmark_map = {}
                for model in models_data:
                    model_id = model.get("id")
                    if model_id:
                        benchmark_map[model_id] = {
                            "name": model.get("name"),
                            "context_length": model.get("context_length", 0),
                            "pricing": model.get("pricing", {}),
                            "top_provider": model.get("top_provider", {}),
                            "architecture": model.get("architecture", {})
                        }
                        
                print(f"✅ [Fetcher] Successfully processed {len(benchmark_map)} models from live index directory.")
                return benchmark_map
                
        except httpx.HTTPError as he:
            print(f"❌ [Fetcher] Transport network framework connection hurdle: {he}")
        except ValueError:
            print("❌ [Fetcher] Failed to serialize JSON layout payload. Target returned non-JSON/HTML contents.")
        except Exception as e:
            print(f"❌ [Fetcher] Unexpected collection mapping anomaly: {e}")
            
        return {}
