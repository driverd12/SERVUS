import logging
import winrm
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
    return winrm.Session(host, auth=(user, password), transport='ntlm')

def validate_user_exists(context):
    """
    Passively checks if the user exists in AD (synced from Okta).
    Does NOT provision.
    """
    user_profile = context.get("user_profile")
    if not user_profile: return False
    
    target_email = user_profile.work_email
    logger.info(f"🔍 AD: Checking if {target_email} exists...")
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would check AD for {target_email}")
        return True

    session = get_session()
    if not session: return False

    ps_script = f"""
    try {{
        $u = Get-ADUser -Identity "{target_email}" -ErrorAction Stop
        Write-Output "FOUND"
    }} catch {{
        Write-Output "NOT_FOUND"
    }}
    """
    
    try:
        result = session.run_ps(ps_script)
        if result.status_code == 0 and "FOUND" in result.std_out.decode():
            logger.info(f"✅ AD: User {target_email} found.")
            return True
        else:
            logger.warning(f"⚠️ AD: User {target_email} NOT found. (Okta sync delay?)")
            return False
            
    except Exception as e:
        logger.error(f"❌ AD Connection Error: {e}")
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
