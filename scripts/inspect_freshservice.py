import requests
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

DOMAIN = os.getenv("SERVUS_FRESHSERVICE_DOMAIN")
API_KEY = os.getenv("SERVUS_FRESHSERVICE_API_KEY")

def inspect_ticket(ticket_id):
    if not DOMAIN or not API_KEY:
        print("❌ Error: Missing .env config for Freshservice.")
        return

    url = f"https://{DOMAIN}/api/v2/tickets/{ticket_id}"
    print(f"🔍 Fetching Ticket #{ticket_id} from {DOMAIN}...")

    try:
        response = requests.get(url, auth=(API_KEY, "X"))
        
        if response.status_code == 200:
            data = response.json().get("ticket", {})
            
            print("\n=== TICKET BODY (The Data is likely here) ===")
            # description_text is the plain text version (no HTML)
            print(data.get('description_text'))
            
            print("\n✅ DONE.")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/inspect_freshservice.py <TICKET_ID>")
    else:
        inspect_ticket(sys.argv[1])
