The opposite of [[Offboarding]]!

## MCP Continuity (Local-Only)

- Shared IDE continuity now uses the local MCP hub as the source of truth.
- Use `transcript.append` for step-level capture and `transcript.summarize` for local deterministic checkpoints.
- For mutating actions, include `mutation.idempotency_key` and `mutation.side_effect_fingerprint`.
- For execution traceability, record long operations with `run.begin`, `run.step`, and `run.end`.
- Gate risky changes with `policy.evaluate`, `preflight.check`, and `postflight.verify`.
- Use `lock.acquire`/`lock.release` when multiple agents may touch the same target.
- Use attribution fields on writes to track contributor identity:
  - `source_client` (e.g. `cursor`, `codex`)
  - `source_model` (e.g. model identifier in use)
  - `source_agent` (e.g. `assistant`, `reviewer`)
- No cloud provider API keys are required for this continuity workflow.

## Scheduler Manual Override Queue (CSV)

- Purpose: support urgent/manual onboarding requests without hard-coding users into scripts.
- Queue file default: `servus_state/manual_onboarding_overrides.csv` (override with `SERVUS_ONBOARDING_OVERRIDE_CSV`).
- State file default: `servus_state/scheduler_state.json` (override with `SERVUS_SCHEDULER_STATE_FILE`).
- Template: `docs/manual_onboarding_overrides_template.csv`.

### Required guardrails for each `READY` row

- `request_id` must be present and unique.
- Required user fields: `work_email`, `first_name`, `last_name`, `department`, `employment_type`.
- Two-source confirmation is mandatory: `confirmation_source_a` and `confirmation_source_b` must both be present and distinct.

### Runtime behavior

- Scheduler scans manual overrides every scheduler cycle.
- Only rows with `status=READY` are processed. `HOLD`/`ERROR` rows are ignored.
- `READY` rows are gated by `start_date` by default. If `start_date` is in the future, SERVUS defers execution.
- For urgent off-cycle requests, set row `allow_before_start_date=true` (or use CLI `--urgent`) to allow immediate execution.
- On successful onboarding, the row is removed from the CSV.
- If onboarding fails, the row is marked `ERROR` with `last_error` to prevent retry loops.
- If the user/start-date combination was already successfully onboarded, the row is automatically removed as already satisfied.

### Slack notification mode

- Default mode is `summary`: one start notification and one consolidated run summary notification.
- Use `SERVUS_SLACK_NOTIFICATION_MODE=verbose` for step-by-step notifications.
- Use `SERVUS_SLACK_NOTIFICATION_MODE=final_only` to suppress start notifications and send final summary only.

### Integration preflight command

- Run `python3 scripts/preflight_check.py` before production onboarding windows to validate critical integrations.
- Use `python3 scripts/preflight_check.py --strict` in CI/NOC gates to fail fast on missing scopes, missing groups, or unreachable badge queue endpoints.

### Brivo/badge fallback behavior

- If SQS badge queue is unavailable or push fails, the onboarding run no longer hard-fails on badge step alone.
- SERVUS posts a manual action notification to Slack:
  - "Create Brivo account and print badge manually"
  - user details (name/email/title/manager)
  - profile image URL (best effort from Rippling/Okta)
- `SERVUS_BRIVO_QUEUE_REQUIRED=true` promotes badge queue health to a strict preflight failure.

### Provisioning policy files

- Google group assignment policy is data-driven in `servus/data/google_groups.yaml`.
- Slack channel assignment policy is data-driven in `servus/data/slack_channels.yaml`.
- If the policy file has no matching targets for a user, the step is skipped with an explicit success detail (`...matched policy; skipped`).

### Queue submission helper (headless-safe)

Use `scripts/live_onboard_test.py` to enqueue a request instead of executing onboarding directly.
The helper defaults to `HOLD` for safety.

Dry-run validation:

```bash
# Minimal: provide email + immutable Rippling/Freshservice IDs.
python3 scripts/live_onboard_test.py \
  --work-email kayla.durgee@boom.aero \
  --rippling-worker-id 697924b36aa907afbec5b964 \
  --freshservice-ticket-id 140 \
  --reason "Urgent onboarding" \
  --dry-run
```

Queue for scheduler pickup:

```bash
# 1) Stage request as HOLD (safe default)
python3 scripts/live_onboard_test.py \
  --work-email kayla.durgee@boom.aero \
  --rippling-worker-id 697924b36aa907afbec5b964 \
  --freshservice-ticket-id 140 \
  --reason "Urgent onboarding"

# 2) Approve for execution (switch to READY)
# Note: if request_id was auto-generated above, copy it from command output.
python3 scripts/live_onboard_test.py \
  --request-id REQ-20260212-kayla-001 \
  --work-email kayla.durgee@boom.aero \
  --rippling-worker-id 697924b36aa907afbec5b964 \
  --freshservice-ticket-id 140 \
  --reason "Urgent onboarding" \
  --allow-update \
  --ready

# 3) Urgent mode (execute before start_date)
python3 scripts/live_onboard_test.py \
  --request-id REQ-20260212-kayla-001 \
  --work-email kayla.durgee@boom.aero \
  --rippling-worker-id 697924b36aa907afbec5b964 \
  --freshservice-ticket-id 140 \
  --reason "Urgent onboarding" \
  --allow-update \
  --ready \
  --urgent
```

Important:
- `HOLD` rows are not processed.
- `READY` rows are processed on the next scheduler cycle.
- Default poll cadence is every 5 minutes.
- `request_id` is optional on insert and auto-generated if omitted.
- You can also approve by editing the CSV row status to `READY`.
- If `start_date` is in the future and urgent mode is not enabled, the row remains `READY` and is retried each cycle until eligible.
- If Rippling lookup cannot supply `start_date`, pass `--start-date` explicitly (kept required for dedupe safety).
- Start unattended scheduler with `python3 scripts/scheduler.py`.
## Manual Onboarding Best Practices
- Always copy-and-paste usernames and names.  If you type usernames or names anywhere, you will eventually make a typo.  Typos in usernames are time consuming to correct.  If there is a Typo in a name, best that it comes from upstream-- not from you.
## Create a checklist document
The onboarding process checklist master template is at: https://docs.google.com/spreadsheets/d/1W_nqezRxGpzKDhKBtAQh-PfsNxgrpAWAsUrYtXO0A70/edit?gid=0#gid=0

- Create a copy of this document [in the same folder](https://drive.google.com/drive/folders/1MRVIxF1UKxH2GpftVxvYUsgk_Z2SB9UX).
- Name the document `Onboarding Firstname Lastname YYYY-MM-DD`
## AD account
- Remote to an on-prem AD server
- Run "Active Directory Users and Computers"
	- Make sure "View" menu > "Advanced Features" is enabled in the "Active Directory Users and Computers" application
### Brand New Users
- Create a new user within the tree: `Boom.local`>`Boom Users`>`(whichever container)
	- Navigate there
	- Right-click the disabled user "US Employee Template" & select "Copy" > fill out firstname, lastname and user email.
	- User Logon name = ‘preferred.lastname’@boom.aero
	  Don't forget to change 'Boom.local' to 'Boom.Aero'! (the template handles this, but safe to check)
	- Password formula we've been using is [<first+last-initial>#<MMDD>Temp!]
		- Set a random throwaway AD password.  No need to record or remember it-- they will blind reset using the Okta enrollment process later.  This password is just required for AD account creation and will never be used.  We do not need to make temporary password sheets for users.  They can initiate Okta enrollment and pick a new password from day-1 which will be synced with AD.
		- You can use use one of these: https://www.random.org/strings/?num=10&len=20&digits=on&upperalpha=on&loweralpha=on&unique=on&format=html&rnd=new
			- Don't save or remember it-- it's throwaway.
			- We'll have them reset in Okta during enrollment.
		- UNCHECK must change password
		- CHECK password never expires
	- Save
	- Double-click the user again in the "Active Directory Users and Computers" window
		- General tab, set their E-mail (3DX impact)
		- Address tab, set their Country to United States (3DX impact)
		- Save and open again
		- Attribute Editor tab
			- Set `employeeType`
				- Used by downstream Okta automation and group mapping
				- https://sites.google.com/boom.aero/kappa/it-security/identity-and-access/okta/okta-workflows-pseudocode?authuser=0
				- `FTE` (Full time employee)
				- `MRG` (Manager)
				- `CON` (Contractor) (also includes interns)
				- `SUP` (Supplier worker)
			-  Set `department`
				- Used by downstream Ramp
				- https://docs.google.com/spreadsheets/d/1YX8C-npXxud9ImO18Glo9elcEGg49_hWWEph3oZBchY/edit?gid=0#gid=0
			- Set departmentNumber
				- Used by downstream Ramp
				- https://docs.google.com/spreadsheets/d/1NB9TWGWMTeuo3kfcKymSWSuK7gwn4OtKMaWb8-QHxPk/edit?gid=1046035534#gid=1046035534
### Reactivations
- Right-click on Boom.local > Find.  Find the user.
	- If their user account has a down-arrow overtop of the icon, then they are disabled.  We'll need to move them to a correct OU and re-activate their AD account.
	- Right-click on the user > Move.  Move them to the correct OU under the "Boom Users" container.
- Now close the search results, and navigate the directory tree to the container in which you moved the user account.
- Double-click the user account to open the Properties pane.
	- (if you do this from the search results, you'll need a nearly-identical-but-not-exactly-identical properties pane.  It's important that you navigate to the container in which the user account is stored, and open the Properties pane from there.)
- General tab > Confirm that the user has an e-mail defined. (3dx impact)
- Address tab > Confirm that the user has a Country defined.
- Account tab >
	- Check the box `Unlock account`
	- Uncheck the box `Account is disabled` 
	- Verify that no account expiry date is set
- Attribute Editor tab
	- If you don't see this tab, then you probably opened the Properties pane from a search results window.  You may need to navigate to the actual directory folder in which the user is stored and open the Properties pane from there
	- Confirm the `employeeType` definition as shown above
## Google Workspace
- Actions performed in Google Workspace Admin happen within "Google Time"
	- "Google Time" = "changes you make WILL eventually happen.  It may be 20 seconds, 20 minutes, or 20 hours later.  But it WILL happen."
	- When you make a change to a user (move OU, unsuspend, add to groups, etc), the change won't immediately reflect in the user admin interface.  Wait 20 seconds, 20 minutes, or 20 hours, and refresh.  It will eventually be there.
	- There is no known way to predict this, circumvent it, etc.  It is some effect of Google datacenter replication.
	- Be aware that you may try to make some change, observe that it appears to not have actually happened.  But it will happen.  Just wait.  For a while.  Some amount of time.  No way to know.  Could be tomorrow even.  This is "Google Time"
-  - Open https://admin.google.com as a Google Workspace admin
### Brand New Users
 - Create the new user (TODO - Complete this section)
### Reactivations
- Search and find the user
	- Unarchive / Unsuspend the user using the links under the username.
	- Rename the user appropriately (removing -archive, etc)
	- Move the user to the proper OU
	- Check groups
		- Add minimally to `team@boom.aero` for FTE, or `contractors@boom.aero` for non-FTE
- Apps on the left > Google Workspace > Gmail
	- Routing section at the bottom
	- "Email forwarding using recipient address map" section > "Offboarded Persons" > "Edit"
	- Search and remove any forwarding in place
## Slack Onboarding
- Open https://boomtech.slack.com as a Slack admin
	- Home tab on the left
	- `Boom \/` Link at the top
	- "Tools and Settings" > "Workspace Settings" or [Direct Link](https://boomtech.slack.com/admin/settings)
	- "Manage Members" on the left
### Brand New Accounts
- TODO - Complete this section
- On-prem channels: `#hq4_alarm`
- All User Type channels:
	- `#be-inspired`: CUM4497U5
	- `#ciso`: C03EVQF5XT4
	- `#hq4-announcements`: C0HDVLJRW
	- `#hq4-facilities`: C04N9EYMZH8
	- `#news`: C0HDTU95W
	- `#quotewall`: C0CNSTACE
	- `#random`: C03K49RUT
- FTE:
	- `#company-announcements`: C03K49RUR
	- `#arrivals-departures`: C0586LM1K6Z
- CON:
	- `#contractor-announcements`: C027SL8CW95
- MGR:
	- `#people-management`: G011Z2YQ7B8
	- `#company-announcements`: C03K49RUR
	- `#arrivals-departures`: C0586LM1K6Z
### Reactivations
- Search for the user.  They are probably showing "Deactivated"
- Click on the three-dots > Activate
	- Reactivate as a Regular Member for FTE, or make a multi-channel guest if necessary, etc
## Okta
- Visit https://boom-admin.okta.com as an Okta admin
- "Directory" > "Directory Integrations"
	- "Active Directory"
	- "Import" tab
	- "Import Now" > "Incremental"
	- You should see a change indicated in the import results (either a new or updated user).  Click OK
	- Search for the username in the results.
		- You should see it appear as a potential match between AD and Okta, or a NEW Okta user.  Tick the box next to that row and click Confirm Assignments.
- Once imported from AD, search for the user in the main Okta search box at the top.  Open the user.
	- Profile tab > "Edit"
	- Set their Secondary E-mail Address to their Personal E-mail
- Send the user an e-mail so they're not surprised by the Okta activation e-mail they're about to get
	- Suggested Template:
Subject: Your Boom Accounts

Hi :

!!!MY NAME!!! here with Boom IT.  I received a request to activate your Boom Gmail, Drive, and Slack accounts.  We use Okta as an identity provider for Gmail, and you can use Okta to log-in and access your e-mail, Drive, etc.

I have sent an Okta enrollment and password reset e-mail to your address: !!!Personal e-mail!!!

Your Okta/Slack username is: !!!Slack/Okta username!!!

You should be able to reset your Okta password with the reset e-mail arriving shortly after this one.  Once you set your new password, you will need to download and install the Okta Verify app on your mobile device.  Follow the prompts in Okta Verify to configure your authenticator.  

Once that's done, you should be all-set to log-in to https://boom.okta.com and then access Gmail with the link therein!  If not, let me know and I'll reset the authenticators on this side and you can re-install and re-enroll Okta verify on your mobile phone.

Let me know if you have any trouble or questions!

Once Okta is set-up, you can login there and click the Gmail button to access your e-mail.

Slack is accessible at the link: https://boomtech.slack.com

Let me know if you get this far and have any issues getting connected.
Thanks again!

- After sending the e-mail, back in their Okta account, click the Activate button.
	- Then, they'll receive the Okta enrollment e-mail at their Personal e-mail address
	- They can follow the link in that e-mail to establish their account, their authenticators, and choose their new AD/Okta password for the first time

### Slack
#### Channels for new FTE
- arrivals-departures
- be-inspired
- boomu
- ciso
- hq4_alarm
- hq4-announcements
- hq4-facilities
- quotewall
- random
