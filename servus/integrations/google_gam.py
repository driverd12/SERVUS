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
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    email = user.work_email
    
    logger.info(f"⏳ Google: Waiting for SCIM to create {email}...")
    
    start_time = time.time()
    timeout = 600 # 10 minutes
    
    while time.time() - start_time < timeout:
        # Check if user exists
        success, stdout, _ = run_gam(["info", "user", email])
        if success:
            logger.info(f"✅ Google: User {email} found!")
            return {"ok": True, "detail": "User already exists in Google (SCIM sync complete)."}
        
        if context.get("dry_run"):
             logger.info(f"[DRY-RUN] Would wait for {email} (Simulating success)")
             return {"ok": True, "detail": "Dry run simulated SCIM wait success."}

        time.sleep(30)
        
    logger.error(f"❌ Google: Timed out waiting for {email} after {timeout}s")
    return {"ok": False, "detail": f"Timed out waiting for SCIM user creation after {timeout}s."}

def move_user_ou(context):
    """
    Moves the user to the correct OU based on employment_type.
    Respects protected OUs.
    """
    user = context.get("user_profile")
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    email = user.work_email
    
    # 1. Get Current OU
    success, stdout, _ = run_gam(["info", "user", email])
    if not success:
        if context.get("dry_run"):
            logger.info(f"[DRY-RUN] Would check OU for {email}")
            current_ou = "/Unknown" # Fake for dry run
        else:
            logger.error(f"❌ Google: Could not find user {email} to move.")
            return {"ok": False, "detail": f"Could not find Google user {email} for OU move."}
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
        return {"ok": True, "detail": f"User in protected OU '{current_ou}', move skipped."}
        
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
        return {"ok": True, "detail": f"User already in target OU '{target_ou}'."}
        
    # 4. Move
    logger.info(f"🚚 Google: Moving {email} from '{current_ou}' to '{target_ou}'")
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would move {email} to {target_ou}")
        return {"ok": True, "detail": f"Dry run: would move user to '{target_ou}'."}
        
    success, _, stderr = run_gam(["update", "user", email, "org", target_ou])
    if success:
        logger.info(f"✅ Google: Moved {email} to {target_ou}")
        return {"ok": True, "detail": f"Moved user to OU '{target_ou}'."}
    else:
        logger.error(f"❌ Google: Failed to move {email}: {stderr}")
        return {"ok": False, "detail": f"Failed to move user to OU '{target_ou}': {stderr}"}

def add_groups(context):
    """
    Adds user to default groups based on department/role.
    """
    user = context.get("user_profile")
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
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
        return {"ok": True, "detail": "No Google groups matched policy; skipped."}

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would add {email} to groups: {groups_to_add}")
        return {"ok": True, "detail": f"Dry run: would add user to groups {sorted(groups_to_add)}."}

    success_count = 0
    already_member_count = 0
    failed_groups = []
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
                 already_member_count += 1
            elif "Group not found" in stdout or "Group not found" in stderr:
                 logger.error(f"   ❌ Group {group_email} not found!")
                 failed_groups.append(f"{group_email}:group-not-found")
            else:
                 logger.error(f"   ❌ Failed to add to {group_email}: {stderr}")
                 failed_groups.append(f"{group_email}:add-failed")

    ok = len(failed_groups) == 0 and success_count == len(groups_to_add)
    detail = (
        f"group_targets={len(groups_to_add)}, added_or_present={success_count}, "
        f"already_member={already_member_count}, failed={len(failed_groups)}"
    )
    if failed_groups:
        detail += f", failed_groups={failed_groups}"
    return {"ok": ok, "detail": detail}

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

    # --- STEP 4.5: ALIAS SWAP (Forwarding) ---
    # Since we can't use Recipient Address Maps via API, we use the Alias Swap method.
    # 1. Archive user has 'jason@' as an alias (automatically created on rename).
    # 2. We delete that alias from the archive user.
    # 3. We add 'jason@' as an alias to the manager (transfer_target).
    
    original_email = archive_email.replace("-archive@", "@")
    
    logger.info(f"   5.5. Setting up forwarding via Alias Swap...")
    logger.info(f"        - Removing alias {original_email} from {archive_email}")
    logger.info(f"        - Adding alias {original_email} to {transfer_target}")

    if not context.get("dry_run"):
        # A. Delete alias from archive user
        # Correct Syntax: gam delete alias <alias_email>
        success_del, stdout_del, stderr_del = run_gam(["delete", "alias", original_email])
        if success_del:
            logger.info(f"        ✅ Removed alias {original_email}")
        else:
            # It might fail if the alias doesn't exist (e.g. already deleted), which is fine.
            logger.warning(f"        ⚠️  Could not remove alias (maybe already gone?): {stderr_del}")

        # B. Add alias to manager
        # Correct Syntax: gam create alias <alias_email> user <target_user>
        success_add, stdout_add, stderr_add = run_gam(["create", "alias", original_email, "user", transfer_target])
        if success_add:
            logger.info(f"        ✅ Forwarding Active: {original_email} -> {transfer_target}")
        else:
            if "Duplicate" in stderr_add or "Duplicate" in stdout_add:
                 logger.info(f"        ✅ Forwarding Active (Alias already exists): {original_email} -> {transfer_target}")
            else:
                 logger.error(f"        ❌ Failed to add alias to manager: {stderr_add}")
    else:
        logger.info(f"[DRY-RUN] Would swap aliases to enable forwarding.")

    # --- STEP 5: MOVE OU ---
    logger.info("   6. Moving to /Deprovisioning OU...")
    # Ensure this OU exists in Google Admin, or this step will fail!
    run_gam(["update", "user", archive_email, "org", "/Deprovisioning"])

    # --- STEP 6: SUSPEND ---
    logger.info("   7. Suspending account...")
    run_gam(["update", "user", archive_email, "suspended", "on"])

    logger.info(f"✅ Google Deprovisioning Complete for {target_email} (Now {archive_email})")
    return True

def process_rehire(context):
    """
    Rehire Logic:
    1. Check if user exists in /Deprovisioning with -archive suffix.
    2. Undelete (if deleted).
    3. Unsuspend.
    4. Rename (remove -archive).
    5. Move to active OU based on empType.
    """
    user = context.get("user_profile")
    if not user: return False
    
    target_email = user.work_email # This should be the "clean" email (jason.merret@boom.aero)
    archive_email = target_email.replace("@", "-archive@")
    
    logger.info(f"♻️  Google: Processing Rehire for {target_email}...")
    
    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would check for {archive_email}, unsuspend, rename to {target_email}, and move OU.")
        return True

    # 1. Check for Archive User
    success, stdout, _ = run_gam(["info", "user", archive_email])
    if not success:
        logger.info(f"   ℹ️  Archive user {archive_email} not found. Checking if {target_email} already active...")
        # Check if already active
        s2, out2, _ = run_gam(["info", "user", target_email])
        if s2:
            logger.info("   ✅ User already exists with correct email. Proceeding to OU check.")
            # Proceed to standard move_user_ou logic
            return move_user_ou(context)
        else:
            logger.warning("   ⚠️  No account found (Active or Archive). Standard provisioning will handle creation (via Okta).")
            return True

    # 2. Unsuspend
    logger.info(f"   1. Unsuspending {archive_email}...")
    run_gam(["update", "user", archive_email, "suspended", "off"])
    
    # 3. Rename (Restore original email)
    logger.info(f"   2. Renaming {archive_email} -> {target_email}...")
    run_gam(["update", "user", archive_email, "email", target_email])
    
    # 4. Move OU
    # We reuse the existing logic for this
    logger.info("   3. Moving to Active OU...")
    return move_user_ou(context)

# Keeping the previous functions for Onboarding compatibility
def wait_for_user_and_customize(context):
    """
    Wrapper to wait for SCIM then customize.
    """
    if wait_for_user_scim(context):
        return move_user_ou(context)
    return False
