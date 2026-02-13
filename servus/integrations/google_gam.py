import subprocess
import logging
import time
import os
import yaml
from servus.config import CONFIG

logger = logging.getLogger("servus.google")

GAM_PATH = CONFIG.get("GAM_PATH", "gam")
GROUP_POLICY_FILE = os.path.join("servus", "data", "google_groups.yaml")

DEFAULT_GROUP_POLICY = {
    "global": {
        "full_time": [],
        "contractor": [],
        "intern": [],
        "supplier": [],
    },
    "departments": {},
}


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_corporate_email(email):
    normalized = str(email or "").strip().lower()
    return bool(normalized) and "@" in normalized and normalized.endswith("@boom.aero")

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


def _load_group_policy():
    if not os.path.exists(GROUP_POLICY_FILE):
        logger.warning("Google group policy file missing: %s", GROUP_POLICY_FILE)
        return DEFAULT_GROUP_POLICY

    try:
        with open(GROUP_POLICY_FILE, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:
        logger.error("Failed to load Google group policy (%s): %s", GROUP_POLICY_FILE, exc)
        return DEFAULT_GROUP_POLICY

    global_policy = data.get("global")
    dept_policy = data.get("departments")
    if not isinstance(global_policy, dict):
        global_policy = {}
    if not isinstance(dept_policy, dict):
        dept_policy = {}

    normalized_global = {
        "full_time": _normalize_group_list(global_policy.get("full_time")),
        "contractor": _normalize_group_list(global_policy.get("contractor")),
        "intern": _normalize_group_list(global_policy.get("intern")),
        "supplier": _normalize_group_list(global_policy.get("supplier")),
    }
    normalized_dept = {}
    for dept_key, group_values in dept_policy.items():
        key = str(dept_key or "").strip().lower()
        if not key:
            continue
        normalized_dept[key] = _normalize_group_list(group_values)

    return {"global": normalized_global, "departments": normalized_dept}


def _normalize_group_list(raw_values):
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    if not isinstance(raw_values, list):
        return []

    groups = []
    for value in raw_values:
        group = str(value or "").strip()
        if group:
            groups.append(group)
    return groups


def _employment_bucket(employment_type):
    emp_type = str(employment_type or "").strip().lower()
    if "supplier" in emp_type:
        return "supplier"
    if any(token in emp_type for token in ("intern", "temporary")):
        return "intern"
    if any(token in emp_type for token in ("contractor", "1099")):
        return "contractor"
    if "full-time" in emp_type:
        return "full_time"
    return "contractor"


def _groups_for_user(user, policy):
    global_policy = policy.get("global", {})
    dept_policy = policy.get("departments", {})

    groups = []
    groups.extend(global_policy.get(_employment_bucket(user.employment_type), []))
    dept_key = str(user.department or "").strip().lower()
    groups.extend(dept_policy.get(dept_key, []))

    deduped = []
    seen = set()
    for group in groups:
        key = str(group).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(str(group).strip())
    return deduped

def wait_for_user_scim(context):
    """
    Polls Google (via GAM) to wait for the user to be created by Okta SCIM.
    """
    user = context.get("user_profile")
    if not user:
        return {"ok": False, "detail": "Missing user_profile in action context."}
    email = user.work_email
    
    logger.info(f"⏳ Google: Waiting for SCIM to create {email}...")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would wait for {email} (Simulating success)")
        return {"ok": True, "detail": "Dry run simulated SCIM wait success."}
    
    start_time = time.time()
    timeout = 600 # 10 minutes
    
    while time.time() - start_time < timeout:
        # Check if user exists
        success, stdout, _ = run_gam(["info", "user", email])
        if success:
            logger.info(f"✅ Google: User {email} found!")
            return {"ok": True, "detail": "User already exists in Google (SCIM sync complete)."}
        
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

    # 1. Determine Target OU
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

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would evaluate and move {email} to {target_ou}")
        return {"ok": True, "detail": f"Dry run: would move user to '{target_ou}'."}
    
    # 2. Get Current OU
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
            
    # 3. Safety Check
    protected_ous = ["/SuperAdmins", "/Service Accounts", "/Deprovisioning", "/Retention - e-mail"]
    if current_ou in protected_ous:
        logger.warning(f"⚠️ Google: User {email} is in protected OU '{current_ou}'. Skipping move.")
        return {"ok": True, "detail": f"User in protected OU '{current_ou}', move skipped."}
        
    if current_ou == target_ou:
        logger.info(f"✅ Google: User {email} already in {target_ou}")
        return {"ok": True, "detail": f"User already in target OU '{target_ou}'."}
        
    # 4. Move
    logger.info(f"🚚 Google: Moving {email} from '{current_ou}' to '{target_ou}'")
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
    
    group_policy = _load_group_policy()
    groups_to_add = _groups_for_user(user, group_policy)
    
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
            elif (
                "Group not found" in stdout
                or "Group not found" in stderr
                or "Does not exist" in stdout
                or "Does not exist" in stderr
            ):
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

    transfer_target, transfer_reason = _resolve_offboarding_transfer_target(user, context)
    if not transfer_target:
        logger.error("❌ Google: %s", transfer_reason)
        return False
    
    logger.info(f"💣 Google: Starting FULL deprovisioning for {target_email}...")
    logger.info(f"   ℹ️  Transfer Target (Manager Context): {transfer_target}")

    if context.get("dry_run"):
        logger.info(f"[DRY-RUN] Would check user existence (primary/archive) for {target_email}")
        logger.info(f"[DRY-RUN] Would wipe mobile devices")
        logger.info(f"[DRY-RUN] Would remove from all groups")
        logger.info(f"[DRY-RUN] Would transfer Drive & Calendar to {transfer_target}")
        logger.info(f"[DRY-RUN] Would rename to {target_email.replace('@', '-archive@')}")
        logger.info(f"[DRY-RUN] Would move to /Deprovisioning and suspend")
        return True

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


def _resolve_offboarding_transfer_target(user, context):
    """
    Determine transfer recipient for offboarding artifacts.
    Policy:
    1) Prefer resolved manager email from profile/context.
    2) Optional fallback to OFFBOARDING_ADMIN_EMAIL only if explicitly enabled.
    """
    manager_candidates = [
        getattr(user, "manager_email", None),
        (context or {}).get("manager_email"),
    ]
    for candidate in manager_candidates:
        normalized = str(candidate or "").strip().lower()
        if _is_corporate_email(normalized):
            if normalized == str(user.work_email or "").strip().lower():
                continue
            return normalized, "manager email resolved"

    fallback_enabled = _as_bool(CONFIG.get("OFFBOARDING_TRANSFER_FALLBACK_TO_ADMIN"), default=False)
    fallback_admin = str(CONFIG.get("OFFBOARDING_ADMIN_EMAIL") or "").strip().lower()
    if fallback_enabled and _is_corporate_email(fallback_admin):
        return fallback_admin, "fallback admin enabled"

    return None, (
        "Manager email missing/unresolvable for offboarding transfer target. "
        "Populate manager in source systems or set SERVUS_OFFBOARDING_TRANSFER_FALLBACK_TO_ADMIN=true "
        "for temporary admin fallback."
    )

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
