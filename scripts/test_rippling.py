import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("SERVUS_RIPPLING_API_TOKEN")

def search_rippling_employee(target_name):
    if not API_TOKEN:
        print("❌ Error: SERVUS_RIPPLING_API_TOKEN is missing in .env")
        return

    print(f"🔍 Searching Rippling API for: '{target_name}'...")
    
    url = "https://api.rippling.com/platform/api/employees/include_terminated"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Rippling doesn't always support direct search filters in V1, 
        # so we fetch the list and filter in Python (ok for <2000 employees).
        # If you have a huge org, we would iterate pages.
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ API Error {response.status_code}: {response.text}")
            return

        employees = response.json()
        
        # Filter for the name
        found = []
        for emp in employees:
            # combine names to check
            full = f"{emp.get('firstName', '')} {emp.get('lastName', '')}"
            if target_name.lower() in full.lower():
                found.append(emp)

        if not found:
            print("❌ No matching employee found.")
            print("   (Note: Check if the user is in 'Onboarding' status vs 'Active')")
        else:
            print(f"✅ Found {len(found)} match(es)!")
            for e in found:
                print("\n--- EMPLOYEE DATA ---")
                print(f"Name:  {e.get('firstName')} {e.get('lastName')}")
                print(f"Email: {e.get('workEmail')}")
                print(f"Type:  {e.get('type')}") # FTE/Contractor
                print(f"Dept:  {e.get('department')}")
                print(f"Title: {e.get('title')}")
                print(f"Start: {e.get('startDate')}")

    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    # We test with the name we scraped from the ticket
    search_rippling_employee("Mark Loiseau")
