from src.llm_circuit_router.config import Settings
import requests
import json

def download_benchmarks_to_file():

    API_KEY =Settings().BENCHMARK_API_KEY
    URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
    OUTPUT_FILE = "artificial_analysis_models.json"
    
    headers = {
        "x-api-key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LLM-Circuit-Router"
    }
    
    print(f"📡 Fetching live evaluation matrix from Artificial Analysis API...")
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        
        if response.status_code == 200:
            payload_data = response.json()
            
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(payload_data, f, indent=2, ensure_ascii=False)
                
            print(f"✅ Success! Saved raw catalog into: '{OUTPUT_FILE}'")
            print(f"📊 Total items extracted: {len(payload_data.get('data', []))}")
        else:
            print(f"❌ Server Error {response.status_code}: {response.text[:150]}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    download_benchmarks_to_file()
