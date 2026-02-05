import subprocess
import logging
import time
from servus.config import CONFIG

logger = logging.getLogger("servus.google")

GAM_PATH = CONFIG.get("GAM_PATH", "gam")

def run_gam(args):
    cmd = [GAM_PATH] + args
    try:
        # We capture output but don't strictly fail on non-zero returns 
        # because sometimes GAM warns about non-critical things.
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError:
        logger.error(f"GAM binary not found at {GAM_PATH}")
        return False, "", "Binary missing"

def wait_for_user_scim(context):
    """
    Polls Google (via GAM) to wait for the user to be created by Okta SCIM.
    """
    user = context.get("user_profile")
    if not user: return False
    email = user.work_email
    
    logger.info(f"⏳ Google: Waiting for SCIM to create {email}...")
    
    start_time = time.time()
    timeout = 600 # 10 minutes
    
    while time.time() - start_time < timeout:
        # Check if user exists
        success, stdout, _ = run_gam(["info", "user", email])
        if success:
            logger.info(f"✅ Google: User {email} found!")
            return True
        
        if context.get("dry_run"):
             logger.info(f"[DRY-RUN] Would wait for {email} (Simulating success)")
             return True

        time.sleep(30)
        
    logger.error(f"❌ Google: Timed out waiting for {email} after {timeout}s")
    return False

def move_user_ou(context):
    """
    Moves the user to the correct OU based on employment_type.
    Respects protected OUs.
    """
    user = context.get("user_profile")
    if not user: return False
    email = user.work_email
    
    # 1. Get Current OU
    success, stdout, _ = run_gam(["info", "user", email])
    if not success:
        if context.get("dry_run"):
            logger.info(f"[DRY-RUN] Would check OU for {email}")
            current_ou = "/Unknown" # Fake for dry run
        else:
            logger.error(f"❌ Google: Could not find user {email} to move.")
            return False
    else:
        # Parse OU from stdout (GAM output format varies, usually "Org Unit Path: /Foo")
        current_ou = ""
        for line in stdout.splitlines():
            if "Org Unit Path:" in line:
                current_ou = line.split(":", 1)[1].strip()
                break
            
    # 2. Safety Check
    protected_ous = ["/SuperAdmins", "/Service Accounts", "/Deprovisioning", "/Retention - e-mail"]
    if current_ou in protected_ous:
        logger.warning(f"⚠️ Google: User {email} is in protected OU '{current_ou}'. Skipping move.")
        return True # Treat as success to not break workflow
        
    # 3. Determine Target OU
    emp_type = user.employment_type.lower()
    target_ou = "/empType-CON" # Default
    
    if "full-time" in emp_type:
        target_ou = "/empType-FTE"
    elif "contractor" in emp_type or "1099" in emp_type:
        target_ou = "/empType-CON"
    elif "temporary" in emp_type or "intern" in emp_type:
        target_ou = "/empType-INT"
    elif "supplier" in emp_type:
        target_ou = "/empType-SUP"
        
    if current_ou == target_ou:
        logger.info(f"✅ Google: User {email} already in {target_ou}")
        return True
        
    # 4. Move
    logger.info(f"🚚 Google: Moving {email} from '{current_ou}' to '{target_ou}'")
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would move {email} to {target_ou}")
        return True
        
    success, _, stderr = run_gam(["update", "user", email, "org", target_ou])
    if success:
        logger.info(f"✅ Google: Moved {email} to {target_ou}")
        return True
    else:
        logger.error(f"❌ Google: Failed to move {email}: {stderr}")
        return False

def add_groups(context):
    """
    Adds user to default groups based on department/role.
    """
    user = context.get("user_profile")
    if not user: return False
    email = user.work_email
    
    logger.info(f"👥 Google: Adding groups for {email}...")
    
    groups_to_add = []
    
    # 1. All Hands (FTEs)
    emp_type = user.employment_type.lower()
    if "full-time" in emp_type:
        groups_to_add.append("all-hands@boom.aero")
        
    # 2. Department Groups
    dept = user.department.lower() if user.department else ""
    if "engineering" in dept:
        groups_to_add.append("engineering-all@boom.aero")
        
    # Add more department logic here as needed
    
    if not groups_to_add:
        logger.info("   No groups matched criteria.")
        return True

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would add {email} to groups: {groups_to_add}")
        return True

    success_count = 0
    for group_email in groups_to_add:
        # gam update group <group> add member <user>
        logger.info(f"   Adding to {group_email}...")
        # We capture output to check for "already exists" errors
        success, stdout, stderr = run_gam(["update", "group", group_email, "add", "member", email])
        
        if success:
            logger.info(f"   ✅ Added to {group_email}")
            success_count += 1
        else:
            # GAM error handling
            # Common errors: "Member already exists", "Group not found"
            if "Member already exists" in stdout or "Member already exists" in stderr:
                 logger.info(f"   ℹ️ Already a member of {group_email}")
                 success_count += 1
            elif "Group not found" in stdout or "Group not found" in stderr:
                 logger.error(f"   ❌ Group {group_email} not found!")
            else:
                 logger.error(f"   ❌ Failed to add to {group_email}: {stderr}")
             
    return True

def deprovision_user(context):
    """
    Full Google Offboarding Suite:
    1. Wipe Mobile Devices
    2. Remove from Groups
    3. Transfer Drive/Docs -> admin-wolverine@boom.aero
    4. Transfer Calendar -> admin-wolverine@boom.aero
    5. Rename to 'archive'
    6. Move to Deprovisioning OU
    7. Suspend
    """
    user = context.get("user_profile")
    if not user: return False
    
    target_email = user.work_email
    
    # 🎯 TARGET FOR DATA TRANSFER
    transfer_target = CONFIG.get("OFFBOARDING_ADMIN_EMAIL", "admin-wolverine@boom.aero")
    
    logger.info(f"💣 Google: Starting FULL deprovisioning for {target_email}...")
    logger.info(f"   ℹ️  Transfer Target (Service Account Context): {transfer_target}")

    # 1. Check if user exists (Primary or Archive)
    # We check the primary email first
    success, stdout, _ = run_gam(["info", "user", target_email])
    
    if not success:
        # Check if already renamed to -archive
        archive_email = target_email.replace("@", "-archive@")
        logger.info(f"   ℹ️  User {target_email} not found. Checking {archive_email}...")
        success_archive, stdout_archive, _ = run_gam(["info", "user", archive_email])
        
        if success_archive:
            logger.info(f"   ✅ Found renamed user: {archive_email}")
            target_email = archive_email # Update target to the archive email
            # Check suspension status from stdout
            if "Account suspended: True" in stdout_archive:
                logger.info(f"   ✅ User {target_email} is ALREADY suspended.")
                # We can return True here if we only care about suspension, 
                # but we might want to ensure other steps (wipe, transfer) happened.
                # For now, let's proceed to ensure idempotency.
        else:
            logger.warning(f"⚠️ Google: User {target_email} (and archive) not found. Already deleted?")
            return True

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would Wipe devices")
        logger.info(f"[DRY-RUN] Would Remove from all groups")
        logger.info(f"[DRY-RUN] Would Transfer Drive & Calendar to {transfer_target}")
        logger.info(f"[DRY-RUN] Would Rename to {target_email.replace('@', '-archive@')}")
        logger.info(f"[DRY-RUN] Would Move to /Deprovisioning and Suspend")
        return True

    # --- STEP 1: WIPE DEVICES ---
    # Removes corporate data from sync'd mobile devices
    logger.info("   1. Wiping mobile devices...")
    run_gam(["update", "user", target_email, "wipe"])

    # --- STEP 2: REMOVE FROM GROUPS ---
    logger.info("   2. Removing from all groups...")
    run_gam(["user", target_email, "delete", "groups"])

    # --- STEP 3: DATA TRANSFER (CRITICAL) ---
    # Note: These commands initiate a background job in Google. 
    # They usually return quickly, but the transfer happens async.
    logger.info(f"   3. Transferring Drive files to {transfer_target}...")
    run_gam(["create", "transfer", "drive", target_email, transfer_target, "keep_user"])
    
    logger.info(f"   4. Transferring Calendar events to {transfer_target}...")
    run_gam(["create", "transfer", "calendar", target_email, transfer_target, "release_resources", "true"])

    # --- STEP 4: RENAME TO ARCHIVE ---
    # We rename BEFORE moving/suspending so the archive name sticks
    
    # Check if already renamed (target_email ends with -archive@...)
    if "-archive@" in target_email:
        logger.info(f"   ℹ️  User {target_email} is ALREADY renamed. Skipping rename step.")
        archive_email = target_email
    else:
        archive_email = target_email.replace("@", "-archive@")
        logger.info(f"   5. Renaming to {archive_email}...")
        run_gam(["update", "user", target_email, "email", archive_email])

    # --- STEP 5: MOVE OU ---
    logger.info("   6. Moving to /Deprovisioning OU...")
    # Ensure this OU exists in Google Admin, or this step will fail!
    run_gam(["update", "user", archive_email, "org", "/Deprovisioning"])

    # --- STEP 6: SUSPEND ---
    logger.info("   7. Suspending account...")
    run_gam(["update", "user", archive_email, "suspended", "on"])

    logger.info(f"✅ Google Deprovisioning Complete for {target_email} (Now {archive_email})")
    return True

# Keeping the previous functions for Onboarding compatibility
def wait_for_user_and_customize(context):
    """
    Wrapper to wait for SCIM then customize.
    """
    if wait_for_user_scim(context):
        return move_user_ou(context)
    return False
