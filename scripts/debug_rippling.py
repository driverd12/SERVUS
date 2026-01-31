import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("SERVUS_RIPPLING_API_TOKEN")

def debug_rippling():
    if not TOKEN:
        print("❌ Missing SERVUS_RIPPLING_API_TOKEN")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }

    # Fetch recent workers and filter locally
    url = "https://rest.ripplingapis.com/workers?limit=50"
    
    print(f"🔍 Fetching recent workers from Rippling...")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"✅ Fetched {len(results)} workers. Filtering for 2026-02-02...")
            
            found = []
            for w in results:
                if w.get('start_date') == '2026-02-02':
                    found.append(w)
                    print(f" 🎯 FOUND: {w.get('first_name')} {w.get('last_name')} ({w.get('work_email')})")
            
            if not found:
                print("⚠️ No workers found with start_date 2026-02-02 in the last 50 records.")
                
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    debug_rippling()