import logging
import winrm
import time
from servus.config import CONFIG

logger = logging.getLogger("servus.ad")

def get_session():
    host = CONFIG.get("AD_HOST")
    user = CONFIG.get("AD_USER")
    password = CONFIG.get("AD_PASS")
    
    if not host or not user or not password:
        logger.error("❌ AD Config missing.")
        return None
        
    # Using NTLM for Linux/EC2 compatibility
    # Ensure requests-ntlm is installed in your environment
    return winrm.Session(host, auth=(user, password), transport='ntlm')

def validate_user_exists(context):
    """
    Passively checks if the user exists in AD (synced from Okta).
    Also validates group membership AND employeeType attribute based on employment_type.
    Does NOT provision.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    target_email = user_profile.work_email
    logger.info(f"⏳ AD: Waiting for sync of {target_email}...")
    
    # Determine expected AD Group
    emp_type_input = user_profile.employment_type.lower()
    expected_group = "Contractors" # Default
    
    if "full-time" in emp_type_input:
        expected_group = "FTE"
    elif "contractor" in emp_type_input or "1099" in emp_type_input:
        expected_group = "Contractors"
    elif "intern" in emp_type_input or "temporary" in emp_type_input:
        expected_group = "Interns"
    elif "supplier" in emp_type_input:
        expected_group = "Suppliers"

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would wait for AD sync of {target_email}")
        logger.info(f"[DRY-RUN] Would verify membership in '{expected_group}'")
        logger.info(f"[DRY-RUN] Would verify employeeType matches '{user_profile.employment_type}'")
        return True

    session = get_session()
    if not session: return False

    start_time = time.time()
    timeout = 600 # 10 minutes (AD sync can be slow)

    while time.time() - start_time < timeout:
        # Fetch user, memberOf attribute, and employeeType
        ps_script = f"""
        try {{
            $u = Get-ADUser -Identity "{target_email}" -Properties memberOf,employeeType -ErrorAction Stop
            Write-Output "FOUND"
            Write-Output "GROUPS:$($u.memberOf -join ';')"
            Write-Output "EMPTYPE:$($u.employeeType)"
        }} catch {{
            Write-Output "NOT_FOUND"
        }}
        """
        
        try:
            result = session.run_ps(ps_script)
            output = result.std_out.decode()
            
            if result.status_code == 0 and "FOUND" in output:
                logger.info(f"✅ AD: User {target_email} found.")
                
                # 1. Check Group Membership
                if f"CN={expected_group}," in output or f"CN={expected_group};" in output:
                    logger.info(f"✅ AD: User is correctly in '{expected_group}'.")
                else:
                    logger.warning(f"⚠️ AD: User found but MISSING '{expected_group}' group. Check Okta Rules!")

                # 2. Check Attribute (employeeType)
                found_emp_type = ""
                for line in output.splitlines():
                    if line.startswith("EMPTYPE:"):
                        found_emp_type = line.replace("EMPTYPE:", "").strip()
                        break
                
                if user_profile.employment_type.lower() in found_emp_type.lower() or found_emp_type.lower() in user_profile.employment_type.lower():
                     logger.info(f"✅ AD: Attribute Verified: '{found_emp_type}'")
                else:
                     logger.warning(f"⚠️ AD: Attribute Mismatch! Expected '{user_profile.employment_type}', found '{found_emp_type}'. Check Okta Mappings!")
                    
                return True
            else:
                logger.info(f"   ... Waiting for AD Sync ...")
                time.sleep(30)
                
        except Exception as e:
            logger.error(f"❌ AD Connection Error: {e}")
            return False

    logger.error(f"❌ AD: Timed out waiting for {target_email} after {timeout}s")
    return False

def ensure_user_disabled(context):
    """
    Ensures that the user is disabled and in the Disabled Users OU in AD.
    If the user is found and enabled, it will DISABLE them.
    This acts as a safety net if Okta fails to disable the user.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    session = get_session()
    if not session: return False

    target_email = user_profile.work_email
    
    # Define the specific Disabled OU
    base_dn = CONFIG.get("AD_BASE_DN", "DC=boom,DC=local")
    disabled_ou_dn = f"OU=Disabled Users,{base_dn}" 

    logger.info(f"🛡️ AD: Ensuring disable status for {target_email}...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would ensure AD account is disabled and in {disabled_ou_dn}")
        return True

    # PowerShell: Check Status and Disable if needed
    # Note: We use SilentlyContinue to suppress errors if Identity search fails initially.
    # The 'try/catch' block handles critical failures.
    ps_script = f"""
    $ErrorActionPreference = "Stop"
    try {{
        $u = $null
        
        # 1. Try Identity (Exact Match)
        try {{
            $u = Get-ADUser -Identity "{target_email}" -Properties Enabled,DistinguishedName -ErrorAction Stop
        }} catch {{
            # Ignore identity not found, move to filters
        }}

        # 2. Try Email Address
        if (-not $u) {{
            $u = Get-ADUser -Filter "EmailAddress -eq '{target_email}'" -Properties Enabled,DistinguishedName -ErrorAction SilentlyContinue
        }}
        
        # 3. Try Mail Attribute
        if (-not $u) {{
            $u = Get-ADUser -Filter "mail -eq '{target_email}'" -Properties Enabled,DistinguishedName -ErrorAction SilentlyContinue
        }}
        
        # 4. Try UPN
        if (-not $u) {{
            $u = Get-ADUser -Filter "UserPrincipalName -eq '{target_email}'" -Properties Enabled,DistinguishedName -ErrorAction SilentlyContinue
        }}
        
        # 5. Try SamAccountName (Prefix)
        if (-not $u) {{
            $prefix = "{target_email}".Split("@")[0]
            $u = Get-ADUser -Filter "SamAccountName -eq '$prefix'" -Properties Enabled,DistinguishedName -ErrorAction SilentlyContinue
        }}

        # 6. Try Display Name (First Last) - Case Insensitive
        if (-not $u) {{
            $u = Get-ADUser -Filter "Name -eq '{user_profile.first_name} {user_profile.last_name}' -or DisplayName -eq '{user_profile.first_name} {user_profile.last_name}'" -Properties Enabled,DistinguishedName -ErrorAction SilentlyContinue
        }}

        if (-not $u) {{
            Write-Output "NOT_FOUND"
            return
        }}

        $actions = @()

        # 1. Check Enabled Status
        if ($u.Enabled -eq $true) {{
            Disable-ADAccount -Identity $u
            $actions += "DISABLED"
        }} else {{
            $actions += "ALREADY_DISABLED"
        }}

        # 2. Check OU
        if ($u.DistinguishedName -notlike "*{disabled_ou_dn}*") {{
            Move-ADObject -Identity $u.DistinguishedName -TargetPath "{disabled_ou_dn}"
            $actions += "MOVED"
        }} else {{
            $actions += "ALREADY_MOVED"
        }}
        
        Write-Output ($actions -join "|")
        
    }} catch {{
        Write-Error $_.Exception.Message
    }}
    """
    
    try:
        result = session.run_ps(ps_script)
        output = result.std_out.decode().strip()
        error_out = result.std_err.decode().strip()

        # Debug logging to see what's actually happening
        if output:
            logger.info(f"   [DEBUG] AD Output: {output}")
        if error_out:
            logger.error(f"   [DEBUG] AD Error: {error_out}")
        
        if "NOT_FOUND" in output:
            logger.warning(f"⚠️ AD: User {target_email} ({user_profile.first_name} {user_profile.last_name}) not found.")
            return True # Treat as success for idempotency
            
        if "DISABLED" in output:
            logger.warning(f"🛡️ AD: User was ENABLED. Forced DISABLE.")
        if "MOVED" in output:
            logger.warning(f"🛡️ AD: User was in wrong OU. Forced MOVE.")
            
        if "ALREADY_DISABLED" in output and "ALREADY_MOVED" in output:
            logger.info(f"✅ AD: User is already disabled and in correct OU.")
            
        # If we got output but didn't match any known state, something is wrong
        if not any(x in output for x in ["DISABLED", "MOVED", "ALREADY_DISABLED", "ALREADY_MOVED"]):
            logger.error(f"❌ AD: Unknown response from PowerShell: {output}")
            return False

        return True
            
    except Exception as e:
        logger.error(f"❌ AD Connection Error: {e}")
        return False
