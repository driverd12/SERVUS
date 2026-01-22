import winrm
import requests
import time
import sys
import argparse
import datetime
import json

# ==========================================
#              CONFIGURATION
# ==========================================

# --- INFRASTRUCTURE ---
AD_HOST = '10.1.0.3'
AD_USER = 'boom\\danadmin'
AD_PASS = '__REDACTED__'

OKTA_DOMAIN = 'boom.okta.com'
OKTA_TOKEN  = '__REDACTED__' 

# --- OKTA APP IDs ---
APP_IDS = {
    "AD_IMPORT": "0oacrzpehXApFBO95696",   # Active Directory Agent
    "GOOGLE":    "0oaiwzuzxPQydMdDa696", 
    "SLACK":     "0oamjkpyxyj0o4msT697",
    "ZOOM":      "0oa3jgqlgrxD6OHzP697",
    "RAMP":      "0oasj7qk7dVE19GJU697"
}

# --- AD CONFIGURATION ---
AD_BASE_DN = "DC=boom,DC=local"
AD_USERS_ROOT = "OU=Boom Users"

# Department -> OU Name Mapping
DEPT_MAP = {
    "Engineering": "Engineering",
    "Manufacturing": "Manufacturing",
    "Finance": "Finance",
    "Legal": "Legal",
    "Marketing": "Marketing",
    "IT": "IT",
    "People": "People",
    "Sales": "Sales",
    "Facilities": "Facilities",
    "Supply Chain": "Supply Chain",
    "Software": "Software",
    "Shipping": "Shipping & Receiving",
    "Shipping & Receiving": "Shipping & Receiving",
    "Avionics": "Engineering", 
    "Propulsion": "Engineering"
}

# ==========================================
#           LOGGING & BRANDING
# ==========================================
LOG_FILE = f"servus_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

def print_banner():
    banner = r"""
  _____  ______  _____  __      __  _    _   _____ 
 / ____||  ____||  __ \ \ \    / / | |  | | / ____|
| (___  | |__   | |__) | \ \  / /  | |  | || (___  
 \___ \ |  __|  |  _  /   \ \/ /   | |  | | \___ \ 
 ____) || |____ | | \ \    \  /    | |__| | ____) |
|_____/ |______||_|  \_\    \/      \____/ |_____/ 
    """
    print(banner)
    print("[ provision in • deprovision out • no loose ends ]\n")

def log(level, system, message):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    colors = {"OK": "\033[92m", "WARN": "\033[93m", "FAIL": "\033[91m", "INFO": "\033[94m", "END": "\033[0m"}
    color = colors.get(level, colors["END"])
    print(f"[{timestamp}] {system.ljust(12)} : {color}[{level}]{colors['END']} {message}")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] [{level}] [{system}] {message}\n")

# ==========================================
#           HELPER FUNCTIONS
# ==========================================
def normalize_dept(input_dept):
    """Case-insensitive lookup for department mapping."""
    for key in DEPT_MAP.keys():
        if key.lower() == input_dept.lower():
            return key
    return input_dept # Return original if no match found (will go to To Be Sorted)

def get_ad_path(user_type, department):
    root = f"{AD_USERS_ROOT},{AD_BASE_DN}"
    
    # 1. Special Handling for Contractors/Interns
    if user_type == "CON": return f"OU=Contractors,{root}"
    if user_type == "INT": return f"OU=Interns,{root}"
    
    # 2. FTE Handling
    clean_dept = normalize_dept(department)
    ou_name = DEPT_MAP.get(clean_dept, "To Be Sorted") 
    
    return f"OU={ou_name},{root}"

def get_template_dn(user_type):
    root = f"{AD_USERS_ROOT},{AD_BASE_DN}"
    if user_type == "CON": return f"CN=Contractor Template,OU=Contractors,{root}"
    elif user_type == "INT": return f"CN=Intern Template,OU=Interns,{root}"
    else: return f"CN=US Employee Template,{root}"

def generate_password(first, last, start_date=None):
    if not start_date: start_date = datetime.datetime.now().strftime('%m%d')
    return f"{first[0].lower()}{last[0].lower()}#{start_date}Temp!"

def okta_call(method, endpoint, data=None):
    url = f"https://{OKTA_DOMAIN}/api/v1{endpoint}"
    headers = {'Authorization': f'SSWS {OKTA_TOKEN}', 'Content-Type': 'application/json'}
    try:
        if method == 'GET': r = requests.get(url, headers=headers)
        else: r = requests.post(url, headers=headers, json=data)
        return r
    except Exception as e:
        log("FAIL", "Okta API", str(e))
        return None

# ==========================================
#           1. PROVISIONING (IN)
# ==========================================
def provision_ad(user_data, user_type, department, password, dry_run=False):
    target_path = get_ad_path(user_type, department)
    template_dn = get_template_dn(user_type)
    
    log("INFO", "ActiveDir", f"Targeting OU: {target_path}")

    ps_script = f"""
    $ErrorActionPreference = "Stop"
    $email = "{user_data['email']}"
    $sam = "{user_data['sam']}"
    $password = ConvertTo-SecureString "{password}" -AsPlainText -Force
    
    $u = Get-ADUser -Filter "EmailAddress -eq '$email' -or SamAccountName -eq '$sam'"
    if ($u) {{ Write-Output "EXISTS" }} 
    else {{
        {'Write-Output "DRY_RUN"' if dry_run else f'''
        try {{
            $t = Get-ADUser -Identity "{template_dn}"
            New-ADUser -Name "{user_data['first']} {user_data['last']}" `
                       -SamAccountName $sam `
                       -EmailAddress $email `
                       -UserPrincipalName $email `
                       -AccountPassword $password `
                       -Enabled $true `
                       -Instance $t `
                       -Path "{target_path}" `
                       -ChangePasswordAtLogon $true
            
            Start-Sleep -Seconds 3
            $check = Get-ADUser -Filter "SamAccountName -eq '$sam'"
            if ($check) {{ Write-Output "CREATED" }} else {{ Write-Output "VERIFY_FAIL" }}
        }} catch {{ Write-Output "ERROR|$($_.Exception.Message)" }}
        '''}
    }}
    """
    try:
        s = winrm.Session(AD_HOST, auth=(AD_USER, AD_PASS), transport='ntlm')
        res = s.run_ps(ps_script)
        out = res.std_out.decode().strip()
        
        if "CREATED" in out: log("OK", "ActiveDir", "User created successfully.")
        elif "EXISTS" in out: log("WARN", "ActiveDir", "User already exists. Proceeding.")
        elif "DRY_RUN" in out: log("INFO", "ActiveDir", "[DRY RUN] Would create user.")
        elif "ERROR" in out:
            log("FAIL", "ActiveDir", f"AD Error: {out.split('|')[1]}")
            return False
        else:
            log("FAIL", "ActiveDir", f"Unexpected AD output: {out}")
            return False
        return True
    except Exception as e:
        log("FAIL", "ActiveDir", str(e))
        return False

def assign_app(user_id, app_name, app_key, username, dry_run=False):
    app_id = APP_IDS.get(app_key)
    if not app_id: return
    
    log("INFO", "Okta", f"Assigning {app_name}...")
    if dry_run: return

    payload = {"id": user_id, "scope": "USER", "credentials": {"userName": username}}
    r = okta_call('POST', f'/apps/{app_id}/users', payload)
    if r.status_code == 200: log("OK", "Okta", f"{app_name} Assigned.")
    elif r.status_code == 400: log("OK", "Okta", f"{app_name} already assigned.")
    else: log("FAIL", "Okta", f"Assignment error: {r.text}")

def run_provisioning(args):
    print("\n--- NEW HIRE ONBOARDING ---")
    email = input("Email (e.g. trista.gooday@boom.aero): ").strip()
    first = input("First Name: ").strip()
    last = input("Last Name: ").strip()
    
    print("\nDepartments: " + ", ".join(sorted(list(DEPT_MAP.keys()))))
    dept = input("Department: ").strip()
    
    t_choice = input("\nType (1=FTE, 2=CON, 3=INT): ").strip()
    u_type = {"1": "FTE", "2": "CON", "3": "INT"}.get(t_choice, "FTE")
    
    start_date = input("Start Date MMDD (Enter for today): ").strip()

    password = generate_password(first, last, start_date)
    sam = f"{first}.{last}"
    user_data = {"email": email, "first": first, "last": last, "sam": sam}

    print(f"\n--- PLAN: {first} {last} ({u_type}) ---")
    print(f"AD OU: {get_ad_path(u_type, dept)}")
    print(f"Pass:  {password}")
    
    if not args.dry_run:
        if input("\nType 'yes' to PROVISION: ").strip().lower() != 'yes': return

    # 1. AD
    if not provision_ad(user_data, u_type, dept, password, args.dry_run): return

    # 2. Okta Sync
    log("INFO", "Okta", "Triggering AD Import...")
    if not args.dry_run:
        okta_call('POST', f'/apps/{APP_IDS["AD_IMPORT"]}/users/import')
        print("      ...Waiting 20s for Okta to ingest identity...")
        time.sleep(20)

    # 3. Find & Assign
    log("INFO", "Okta", "Searching for linked user profile...")
    r_user = okta_call('GET', f'/users?q={email}')
    
    if r_user and r_user.status_code == 200 and len(r_user.json()) > 0:
        uid = r_user.json()[0]['id']
        log("OK", "Okta", f"User linked (ID: {uid})")
        
        # Assign Apps
        for app, key in [("Google", "GOOGLE"), ("Slack", "SLACK")]:
            assign_app(uid, app, key, email, args.dry_run)
            
        if u_type == "FTE":
            assign_app(uid, "Zoom", "ZOOM", email, args.dry_run)
            assign_app(uid, "Ramp", "RAMP", email, args.dry_run)
    else:
        log("FAIL", "Okta", "User not found in Okta. Match failed or AD sync timed out.")

# ==========================================
#           2. DEPROVISIONING (OUT)
# ==========================================
def run_deprovisioning(args):
    print("\n--- USER OFFBOARDING ---")
    print("WARNING: This will DISABLE the user in AD and DEACTIVATE in Okta.")
    email = input("Enter Email to Offboard: ").strip()

    # Safety Check
    confirm = input(f"Type '{email}' to CONFIRM DESTRUCTION: ").strip()
    if confirm != email:
        print("❌ Mismatch. Aborted.")
        return

    print(f"\n🚀 SERVUS: Deprovisioning {email}...")

    # 1. Active Directory Disable
    log("INFO", "ActiveDir", "Disabling account...")
    ps_script = f"""
    $ErrorActionPreference = "Stop"
    $u = Get-ADUser -Filter "EmailAddress -eq '{email}'"
    if ($u) {{
        Disable-ADUser -Identity $u
        Set-ADUser -Identity $u -Description "Disabled by SERVUS on $(Get-Date)"
        Write-Output "DISABLED|$($u.SamAccountName)"
    }} else {{
        Write-Output "NOT_FOUND"
    }}
    """
    if args.dry_run:
        log("INFO", "ActiveDir", "[DRY RUN] Would disable AD account.")
    else:
        try:
            s = winrm.Session(AD_HOST, auth=(AD_USER, AD_PASS), transport='ntlm')
            res = s.run_ps(ps_script)
            out = res.std_out.decode().strip()
            if "DISABLED" in out:
                log("OK", "ActiveDir", f"Account disabled: {out.split('|')[1]}")
            elif "NOT_FOUND" in out:
                log("WARN", "ActiveDir", "User not found in AD. Skipping to Okta.")
            else:
                log("FAIL", "ActiveDir", f"AD Error: {out}")
        except Exception as e:
            log("FAIL", "ActiveDir", str(e))

    # 2. Okta Deactivate (Cascades to Google/Slack)
    log("INFO", "Okta", "Deactivating identity...")
    if args.dry_run:
        log("INFO", "Okta", "[DRY RUN] Would deactivate Okta user.")
        return

    r_user = okta_call('GET', f'/users?q={email}')
    if r_user and len(r_user.json()) > 0:
        uid = r_user.json()[0]['id']
        status = r_user.json()[0]['status']
        
        if status == 'DEPROVISIONED':
            log("WARN", "Okta", "User is already Deactivated.")
        else:
            # Deactivate
            r_deac = okta_call('POST', f'/users/{uid}/lifecycle/deactivate')
            if r_deac.status_code == 200:
                log("OK", "Okta", "User Deactivated Successfully.")
                log("INFO", "Okta", ">> Google/Slack access revoked via SCIM.")
            else:
                log("FAIL", "Okta", f"Deactivation failed: {r_deac.text}")
    else:
        log("FAIL", "Okta", "User not found in Okta.")

# ==========================================
#           MAIN MENU
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="SERVUS: Provision in. Deprovision out.")
    parser.add_argument('--dry-run', action='store_true', help="Simulate actions")
    args = parser.parse_args()

    print_banner()

    if args.dry_run:
        print("🔸 MODE: DRY RUN (Safe)\n")

    print("SELECT OPERATION:")
    print("1. Provision (Onboard)")
    print("2. Deprovision (Offboard)")
    print("Q. Quit")
    
    choice = input("\nChoice: ").strip().upper()

    if choice == '1':
        run_provisioning(args)
    elif choice == '2':
        run_deprovisioning(args)
    elif choice == 'Q':
        sys.exit()
    else:
        print("Invalid choice.")

    print(f"\n✅ SERVUS Operation Complete. Log: {LOG_FILE}")

if __name__ == "__main__":
    main()