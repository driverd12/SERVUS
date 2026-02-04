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

def disable_user(context):
    """
    Disables the AD account AND moves it to the 'Disabled Users' OU.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    session = get_session()
    if not session: return False

    target_email = user_profile.work_email
    
    # Define the specific Disabled OU (Verify this path matches your AD structure)
    # Using the Base DN from config to construct the full path
    base_dn = CONFIG.get("AD_BASE_DN", "DC=boom,DC=local")
    disabled_ou_dn = f"OU=Disabled Users,{base_dn}" 

    logger.info(f"🚫 AD: Disabling and Moving {target_email}...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would run: Disable-ADAccount -Identity {target_email}")
        logger.info(f"[DRY-RUN] Would run: Move-ADObject -Identity {target_email} -TargetPath '{disabled_ou_dn}'")
        return True

    # PowerShell: Disable first, then Move
    ps_script = f"""
    try {{
        $u = Get-ADUser -Identity "{target_email}" -ErrorAction Stop
        
        # 1. Disable
        Disable-ADAccount -Identity $u
        Write-Output "DISABLED"
        
        # 2. Move
        Move-ADObject -Identity $u.DistinguishedName -TargetPath "{disabled_ou_dn}"
        Write-Output "MOVED"
    }} catch {{
        Write-Error $_.Exception.Message
    }}
    """
    
    try:
        result = session.run_ps(ps_script)
        if result.status_code == 0 and "DISABLED" in result.std_out.decode():
            logger.info(f"✅ AD Account Disabled and Moved to {disabled_ou_dn}")
            return True
        else:
            err = result.std_err.decode()
            logger.error(f"❌ AD Disable Failed: {err}")
            return False
            
    except Exception as e:
        logger.error(f"❌ AD Connection Error: {e}")
        return False
