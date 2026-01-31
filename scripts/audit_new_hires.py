import argparse
import logging
import sys
import os
import requests
import urllib.parse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.config import CONFIG
from servus.integrations.okta import OktaClient
from servus.integrations.brivo import BrivoClient
from servus.integrations.slack import _lookup_user_by_email as slack_lookup
# Import AD and Google logic if possible, or reimplement lightweight checks
from servus.integrations.ad import validate_user_exists as ad_validate
# For Google, we might need to run a GAM command or use SCIM check. 
# google_gam.py has wait_for_user_scim which runs 'gam info user'.
from servus.integrations.google_gam import run_gam

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("audit")

def fetch_rippling_new_hires(target_date="2026-02-02", limit=200):
    """
    Scans recent Rippling workers for a specific start date.
    """
    token = CONFIG.get("RIPPLING_API_TOKEN")
    if not token:
        logger.error("❌ Missing SERVUS_RIPPLING_API_TOKEN")
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    logger.info(f"🔍 Scanning Rippling for start_date={target_date} (Limit: {limit})...")
    
    matches = []
    url = f"https://rest.ripplingapis.com/workers?limit=50"
    
    fetched_count = 0
    while url and fetched_count < limit:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.error(f"❌ Rippling API Error: {resp.status_code}")
                break
                
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
                
            for w in results:
                if w.get("start_date") == target_date:
                    matches.append(w)
            
            fetched_count += len(results)
            logger.info(f"   Scanned {fetched_count} workers...")
            
            # Pagination Logic
            url = data.get("next_link")
            # If next_link is None or empty, we are done
            if not url:
                break
            
            # If we found 3 or more, we can stop (assuming user asked for 3)
            if len(matches) >= 3:
                break
                
        except Exception as e:
            logger.error(f"❌ Rippling Connection Error: {e}")
            break

    return matches

def check_google(email):
    """
    Checks Google Workspace via GAM.
    """
    # gam info user <email>
    # We use the helper from google_gam.py if available, or subprocess
    # run_gam returns (success, stdout, stderr)
    try:
        success, stdout, stderr = run_gam(["info", "user", email])
        if success:
            return "✅ Exists"
        else:
            if "User not found" in stdout or "User not found" in stderr:
                return "❌ Not Found"
            return f"⚠️ Error: {stderr.strip()}"
    except Exception as e:
        return f"⚠️ Exception: {e}"

def check_ad(email):
    """
    Checks AD via PyWinRM (using ad.py logic if possible).
    """
    # We can mock a context and call validate_user_exists, 
    # but that function might try to wait/poll.
    # Let's try to run a simple PowerShell command via the same mechanism.
    # Actually, ad.py isn't easily importable for a single check without context.
    # Let's skip deep AD check for this script to avoid complexity, 
    # or assume if Okta has them, AD likely does (Okta Masters AD).
    # OR, we can try to use the ad module if we can.
    
    # For now, let's mark as "Manual Verify" or "Check Okta" since Okta masters AD.
    return "❓ Check Manually (or via Okta)"

def audit_user(user):
    first = user.get("first_name")
    last = user.get("last_name")
    email = user.get("work_email")
    
    print(f"\n👤 AUDIT: {first} {last} ({email})")
    
    dept = user.get('department')
    dept_name = dept.get('name') if isinstance(dept, dict) else "Unknown"
    print(f"   Dept: {dept_name}")
    
    emp_type = user.get('employment_type')
    emp_label = emp_type.get('label') if isinstance(emp_type, dict) else "Unknown"
    print(f"   Type: {emp_label}")
    
    # 1. Okta Check
    okta_client = OktaClient()
    okta_user = okta_client.get_user(email)
    okta_status = f"✅ Active (ID: {okta_user['id']})" if okta_user else "❌ Not Found"
    print(f"   🔹 Okta:   {okta_status}")
    
    # 2. Google Check
    google_status = check_google(email)
    print(f"   🔹 Google: {google_status}")
    
    # 3. Slack Check
    slack_id = slack_lookup(email)
    slack_status = f"✅ Found ({slack_id})" if slack_id else "❌ Not Found"
    print(f"   🔹 Slack:  {slack_status}")
    
    # 4. Brivo Check
    brivo_client = BrivoClient()
    brivo_user = brivo_client.find_user(email)
    brivo_status = f"✅ Found (ID: {brivo_user['id']})" if brivo_user else "❌ Not Found"
    print(f"   🔹 Brivo:  {brivo_status}")
    
    # 5. Badge Readiness
    # Check for photo URL in Rippling data (if available in keys) or Okta
    # Rippling API v1 usually doesn't expose photo URL easily in list view.
    # We'll assume if Brivo user exists, we *could* print.
    photo_ready = "❓ Check Photo Source"
    if brivo_user:
        photo_ready = "✅ Ready to Print (User in Brivo)"
    else:
        photo_ready = "❌ Cannot Print (User missing in Brivo)"
    print(f"   🔹 Badge:  {photo_ready}")

def fetch_rippling_user_by_email(email):
    """
    Fetches a single user from Rippling by email.
    """
    token = CONFIG.get("RIPPLING_API_TOKEN")
    if not token: return {}
    
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    query = urllib.parse.quote(f"work_email eq '{email}'")
    url = f"https://rest.ripplingapis.com/workers?filter={query}"
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                # Fetch full details to get department/employment_type expanded if needed
                # But the list view usually has basic info.
                # Let's try to get the first result.
                user = results[0]
                
                # Expand if needed (optional, but let's try to get better data)
                # If name is missing, it might be in 'personal_information' or root
                # Based on previous debug, 'first_name' and 'last_name' are in root.
                # If they are None, maybe the user object is sparse?
                # Let's fetch the full worker object by ID
                worker_id = user.get("id")
                if worker_id:
                    detail_url = f"https://rest.ripplingapis.com/workers/{worker_id}?expand=department,employment_type"
                    detail_resp = requests.get(detail_url, headers=headers, timeout=10)
                    if detail_resp.status_code == 200:
                        return detail_resp.json()
                
                return user
    except Exception as e:
        logger.error(f"❌ Rippling Lookup Error: {e}")
        
    return {}

def main():
    parser = argparse.ArgumentParser(description="Audit New Hires for SERVUS")
    parser.add_argument("--date", default="2026-02-02", help="Start Date to scan for (YYYY-MM-DD)")
    parser.add_argument("--email", help="Specific email to audit (skips Rippling scan)")
    args = parser.parse_args()
    
    if args.email:
        # Manual Mode
        print(f"🔍 Looking up {args.email} in Rippling...")
        rippling_user = fetch_rippling_user_by_email(args.email)
        
        if rippling_user:
            print(f"✅ Found in Rippling: {rippling_user.get('first_name')} {rippling_user.get('last_name')}")
            # Use the data from Rippling
            audit_user(rippling_user)
        else:
            print(f"⚠️ Not found in Rippling. Proceeding with manual check...")
            audit_user({"first_name": "Manual", "last_name": "Check", "work_email": args.email})
    else:
        # Scan Mode
        new_hires = fetch_rippling_new_hires(args.date)
        
        if not new_hires:
            print(f"⚠️ No new hires found in Rippling for {args.date} (checked recent 50).")
            print("   Try providing an email directly: python scripts/audit_new_hires.py --email user@boom.aero")
        else:
            print(f"\n🎯 Found {len(new_hires)} new hires for {args.date}:")
            for user in new_hires:
                audit_user(user)

if __name__ == "__main__":
    main()