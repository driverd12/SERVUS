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

def verify_user_disabled(context):
    """
    Verifies that the user is disabled and in the Disabled Users OU in AD.
    This is used to confirm Okta's deactivation propagated correctly.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    session = get_session()
    if not session: return False

    target_email = user_profile.work_email
    
    # Define the specific Disabled OU
    base_dn = CONFIG.get("AD_BASE_DN", "DC=boom,DC=local")
    disabled_ou_dn = f"OU=Disabled Users,{base_dn}" 

    logger.info(f"🔍 AD: Verifying disable status for {target_email}...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would verify AD account is disabled and in {disabled_ou_dn}")
        return True

    # PowerShell: Check Enabled property and DistinguishedName
    ps_script = f"""
    try {{
        $u = Get-ADUser -Identity "{target_email}" -Properties Enabled,DistinguishedName -ErrorAction Stop
        
        if ($u.Enabled -eq $false) {{
            Write-Output "STATUS:DISABLED"
        }} else {{
            Write-Output "STATUS:ENABLED"
        }}
        
        Write-Output "DN:$($u.DistinguishedName)"
        
    }} catch {{
        Write-Output "NOT_FOUND"
        Write-Error $_.Exception.Message
    }}
    """
    
    try:
        result = session.run_ps(ps_script)
        output = result.std_out.decode()
        
        if "NOT_FOUND" in output:
            logger.error(f"❌ AD: User {target_email} not found.")
            return False
            
        is_disabled = "STATUS:DISABLED" in output
        in_correct_ou = disabled_ou_dn.lower() in output.lower() # Case-insensitive check
        
        if is_disabled and in_correct_ou:
            logger.info(f"✅ AD: User is DISABLED and in Disabled OU.")
            return True
        else:
            if not is_disabled:
                logger.warning(f"⚠️ AD: User is still ENABLED.")
            if not in_correct_ou:
                logger.warning(f"⚠️ AD: User is NOT in Disabled OU.")
            return False
            
    except Exception as e:
        logger.error(f"❌ AD Connection Error: {e}")
        return False
