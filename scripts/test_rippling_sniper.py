import requests
import os
import json
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("SERVUS_RIPPLING_API_TOKEN")

def sniper_search(first, last, domain="boom.aero"):
    if not API_TOKEN:
        print("❌ Error: SERVUS_RIPPLING_API_TOKEN is missing in .env")
        return

    target_email = f"{first}.{last}@{domain}".lower()
    print(f"🎯 Sniper Mode: Aiming for [{target_email}]...")
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # --- STEP 1: LIGHTWEIGHT LOOKUP (Get ID only) ---
    print("   [Step 1] Fetching Worker ID (No details)...")
    query = f"work_email eq '{target_email}'"
    encoded_query = urllib.parse.quote(query)
    
    # NO expands here. Just find the record.
    url_step1 = f"https://rest.ripplingapis.com/workers?filter={encoded_query}"
    
    worker_id = None
    
    try:
        response = requests.get(url_step1, headers=headers)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                worker_id = results[0].get("id")
                print(f"   ✅ Found Worker ID: {worker_id}")
            else:
                print(f"❌ No worker found for {target_email}")
                return
        else:
            print(f"❌ Step 1 Error {response.status_code}: {response.text}")
            return
    except Exception as e:
        print(f"❌ Step 1 Exception: {e}")
        return

    # --- STEP 2: DIRECT FETCH (Get Details) ---
    if worker_id:
        print("   [Step 2] Fetching full details by ID...")
        # Now we expand, because looking up by ID is much faster for the server
        expand = "department,employment_type,manager"
        url_step2 = f"https://rest.ripplingapis.com/workers/{worker_id}?expand={expand}"
        
        try:
            response = requests.get(url_step2, headers=headers)
            if response.status_code == 200:
                worker = response.json()
                print("\n✅ BULLSEYE! Data Retrieved.")
                
                # Extract Data
                user = worker.get("user") or {}
                user_name = (user.get("name") or {}).get("formatted", "Unknown")
                
                # Department
                dept_obj = worker.get("department") or {}
                dept_name = dept_obj.get("name", "No Dept Assigned")
                
                # Employment Type
                emp_type_obj = worker.get("employment_type")
                if isinstance(emp_type_obj, dict):
                    emp_type_label = emp_type_obj.get("label") or emp_type_obj.get("name")
                    sub_type = emp_type_obj.get("type", "")
                else:
                    emp_type_label = str(emp_type_obj)
                    sub_type = "Unknown"

                print(f"   Name:  {user_name}")
                print(f"   Email: {worker.get('work_email')}")
                print(f"   Dept:  {dept_name}")
                print(f"   Type:  {emp_type_label} (Category: {sub_type})")
                
            else:
                print(f"❌ Step 2 Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"❌ Step 2 Exception: {e}")

if __name__ == "__main__":
    sniper_search("Mark", "Loiseau")
