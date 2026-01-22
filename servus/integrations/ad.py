from __future__ import annotations
import re
from typing import Any
import winrm

# Mirrors the legacy DEPT_MAP behavior; override later if desired.
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
    "Propulsion": "Engineering",
}

TEMPLATE_USERS = {
    "FTE": "US Employee Template",
    "CON": "US Contractor Template",
    "INT": "US Intern Template",
}

def _session(ctx: dict[str, Any]) -> winrm.Session:
    cfg = ctx["config"].ad
    return winrm.Session(f"http://{cfg.host}:5985/wsman", auth=(cfg.username, cfg.password))

def _run_ps(session: winrm.Session, script: str) -> str:
    r = session.run_ps(script)
    if r.status_code != 0:
        raise RuntimeError(r.std_err.decode(errors="ignore"))
    return r.std_out.decode(errors="ignore")

def provision_user(ctx: dict[str, Any]) -> dict[str, Any]:
    p = ctx["profile"]
    dept = p.department or "To Be Sorted"
    ou_leaf = DEPT_MAP.get(dept, "To Be Sorted")
    template = TEMPLATE_USERS.get(str(p.worker_type), TEMPLATE_USERS["FTE"])
    username = p.username
    display = p.display_name
    email = str(p.work_email)

    ps = f'''
Import-Module ActiveDirectory
$User = Get-ADUser -Filter "UserPrincipalName -eq '{email}'" -ErrorAction SilentlyContinue
if ($User) {{
  # Reactivate path: ensure enabled
  Enable-ADAccount -Identity $User
  Unlock-ADAccount -Identity $User -ErrorAction SilentlyContinue
  Write-Output "REACTIVATED:{email}"
}} else {{
  $Template = Get-ADUser -Filter "Name -eq '{template}'" -ErrorAction Stop
  $TempPwd = ConvertTo-SecureString -String ("RANDOM-" + (Get-Random)) -AsPlainText -Force
  $NewUser = New-ADUser -Name "{display}" -GivenName "{p.first_name}" -Surname "{p.last_name}" `
    -UserPrincipalName "{email}" -SamAccountName "{username}" -EmailAddress "{email}" `
    -AccountPassword $TempPwd -Enabled $true -PasswordNeverExpires $true -PassThru
  Write-Output "CREATED:{email}"
}}
# Move to OU leaf if present (best effort)
try {{
  $dn = (Get-ADUser -Filter "UserPrincipalName -eq '{email}'").DistinguishedName
  if ($dn) {{
    # naive OU move based on leaf name under Boom Users
    $targetOu = Get-ADOrganizationalUnit -Filter "Name -eq '{ou_leaf}'" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($targetOu) {{
      Move-ADObject -Identity $dn -TargetPath $targetOu.DistinguishedName
      Write-Output "MOVED_OU:{ou_leaf}"
    }} else {{
      Write-Output "OU_NOT_FOUND:{ou_leaf}"
    }}
  }}
}} catch {{
  Write-Output ("OU_MOVE_ERR:" + $_.Exception.Message)
}}
'''
    s = _session(ctx)
    out = _run_ps(s, ps)
    return {"output": out.strip(), "email": email, "ou": ou_leaf, "template": template}

def verify_user(ctx: dict[str, Any]) -> dict[str, Any]:
    p = ctx["profile"]
    email = str(p.work_email)
    ps = f'''
Import-Module ActiveDirectory
$u = Get-ADUser -Filter "UserPrincipalName -eq '{email}'" -Properties Enabled -ErrorAction SilentlyContinue
if ($u) {{
  Write-Output ("FOUND:" + $u.Enabled)
  exit 0
}} else {{
  Write-Error "NOT_FOUND"
  exit 2
}}
'''
    s = _session(ctx)
    out = _run_ps(s, ps)
    return {"verified": True, "output": out.strip()}

def disable_user(ctx: dict[str, Any]) -> dict[str, Any]:
    p = ctx["profile"]
    email = str(p.work_email)
    ps = f'''
Import-Module ActiveDirectory
$u = Get-ADUser -Filter "UserPrincipalName -eq '{email}'" -ErrorAction Stop
Disable-ADAccount -Identity $u
Write-Output "DISABLED"
'''
    s = _session(ctx)
    out = _run_ps(s, ps)
    return {"disabled": True, "output": out.strip()}
