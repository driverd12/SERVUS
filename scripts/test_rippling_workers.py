import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("SERVUS_RIPPLING_API_TOKEN")

def search_workers(target_name):
    if not API_TOKEN:
        print("❌ Error: SERVUS_RIPPLING_API_TOKEN is missing in .env")
        return

    print(f"🔍 Searching Rippling WORKERS API for: '{target_name}'...")
    
    # Starting URL
    url = "https://rest.ripplingapis.com/workers" 
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # We ask for 50 at a time
    params = {"page_size": 50} 
    
    page_count = 1
    total_checked = 0
    found = False

    while url:
        print(f"   [Page {page_count}] Fetching...")
        
        try:
            # Note: valid 'next_link' URLs from Rippling already contain params, 
            # so we only pass params on the very first manual call.
            if page_count == 1:
                response = requests.get(url, headers=headers, params=params)
            else:
                response = requests.get(url, headers=headers)

            if response.status_code != 200:
                print(f"❌ Error {response.status_code}: {response.text}")
                break

            data = response.json()
            workers = data.get("results", [])
            total_checked += len(workers)
            
            # --- SEARCH THIS PAGE ---
            for w in workers:
                # We search broadly in the JSON blob to avoid structure guessing
                blob = json.dumps(w).lower()
                
                if target_name.lower() in blob:
                    found = True
                    print(f"\n✅ FOUND MATCH: {target_name}")
                    
                    # Extract Key Data
                    user_obj = w.get("user", {})
                    name = user_obj.get("name", {}).get("formatted") or "Unknown"
                    email = w.get("work_email")
                    dept = w.get("department", {}).get("name")
                    title = w.get("title", {}).get("name")
                    emp_type = w.get("type") # EMPLOYEE vs CONTRACTOR

                    print(f"   Name:  {name}")
                    print(f"   Email: {email}")
                    print(f"   Dept:  {dept}")
                    print(f"   Title: {title}")
                    print(f"   Type:  {emp_type}")
                    
                    # Stop looping once found
                    return 

            # --- SETUP NEXT PAGE ---
            # Rippling provides 'next' or 'next_link'
            url = data.get("next") or data.get("next_link")
            
            if not url:
                print(f"\n❌ Reached end of list. Checked {total_checked} records.")
                break
                
            page_count += 1
            
        except Exception as e:
            print(f"❌ Exception: {e}")
            break

if __name__ == "__main__":
    search_workers("Mark Loiseau")
