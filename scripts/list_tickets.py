import requests
import os
from dotenv import load_dotenv

# Load secrets
load_dotenv()

DOMAIN = os.getenv("SERVUS_FRESHSERVICE_DOMAIN")
API_KEY = os.getenv("SERVUS_FRESHSERVICE_API_KEY")

def list_recent_tickets():
    if not DOMAIN or not API_KEY:
        print("❌ Missing .env config for Freshservice.")
        return

    # Fetch last 10 tickets
    url = f"https://{DOMAIN}/api/v2/tickets?per_page=10&order_type=desc"
    print(f"🔍 Connecting to {DOMAIN}...")

    try:
        response = requests.get(url, auth=(API_KEY, "X"))
        
        if response.status_code == 200:
            tickets = response.json().get("tickets", [])
            print("\n=== RECENT TICKETS ===")
            for t in tickets:
                print(f"ID: {t['id']}  |  Subject: {t['subject']}")
            print("\n✅ Select one of these IDs to inspect.")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    list_recent_tickets()
