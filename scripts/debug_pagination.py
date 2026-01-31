import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("SERVUS_RIPPLING_API_TOKEN")

def check_meta():
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
    url = "https://rest.ripplingapis.com/workers?limit=5"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print("Keys:", data.keys())
        if "__meta" in data: # It was in the worker keys in previous output? No, wait.
            # The previous output showed keys of a WORKER object.
            # I need to check the root response keys.
            pass
        # Let's print the whole root keys
        print("Root Keys:", list(data.keys()))
        # And check if there is pagination info
        print("Meta:", json.dumps(data.get("meta"), indent=2)) # 'meta' or '__meta'?
        print("Links:", json.dumps(data.get("links"), indent=2))

if __name__ == "__main__":
    check_meta()