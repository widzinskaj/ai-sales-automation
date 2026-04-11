# Stage 0 — Operational Runbook

**Audience:** Technical operator / deployment engineer.
This document is written for the person who deploys, configures, and maintains the
Stage 0 runtime environment. It is not intended for business users — they interact
with the system exclusively through Google Sheets.

---

## 1. Purpose

Stage 0 provides automated first-touch email handling for inbound sales leads.

**What it does:**

- Reads new leads from the `automation_stage0_input` tab in Google Sheets.
- Sends each new lead a Polish-language auto-reply email with 3 PDF attachments and a
  calendar booking link.
- Records the send result in the `automation_stage0_status` tab (timestamp + status).
- After 3 days without a human response, marks the lead as requiring follow-up
  (`Wymaga follow-upu = YES`) so the sales team can act.

**What it does not do:**

- It does not send follow-up emails automatically — only flags them for humans.
- It does not write to the input sheet.
- It never sends to real leads while test mode is active.

---

## 2. Operating Model

### Roles and responsibilities

| Role | Responsibilities |
|---|---|
| **Technical operator** | Deploy the repository, configure `.env`, set up and maintain the scheduler, monitor logs, apply code updates, handle incidents and escalations. |
| **Business user** | Work exclusively in Google Sheets — review the status tab and mark follow-ups complete. |

### What the business user never touches

- The host machine or its file system.
- The repository, any code file, or the virtual environment.
- The `.env` file or any credentials (SMTP, Google service account).
- Task Scheduler or any runtime configuration.

### Runtime boundary

All runtime components — the scheduler, the Python process, `.env`, secrets, PDF
attachments, and log files — live on the client host managed by the technical operator.
Google Sheets is the only interface the business user interacts with.

---

## 3. Host Requirements

The following must be true of the machine running Stage 0:

| Requirement | Detail |
|---|---|
| **Stable host** | Machine is always-on or reliably available during business hours. Missed scheduler runs delay lead response. |
| **Internet access** | Outbound HTTPS (Google Sheets API) and outbound SMTP (port 587) must be reachable. Firewall and VPN rules must permit both. |
| **Python 3.11+** | Installed and on the system PATH. Verify: `python --version`. |
| **Scheduler** | Windows Task Scheduler (Windows host) or cron (Linux). Required for automated recurring runs. |
| **File system paths** | `.env` at the repository root; `secrets/` for the service account JSON; `assets/attachments/` for the 3 PDF files; `logs/` for scheduler output. None of these are committed to version control. |
| **Restricted access** | Only the technical operator should have access to the host, the repository directory, and the `.env` file. |

---

## 4. Quick Verification

For a technical operator who needs to confirm Stage 0 is alive:

- **Job is running:** Open `logs\stage0_scheduler.log` — you should see repeating pairs of
  `Stage0 job start` / `Stage0 job complete` lines with timestamps advancing at the configured interval.
- **Last run succeeded:** Task Scheduler → find the task → **Last Run Result** = `0x0`.
- **Test mode is active:** Each run's log block must contain a `TEST MODE active` line.
- **Sheets status is written:** Open `automation_stage0_status` — check that `Email wysłany`
  and `Status emaila` are filled for processed leads.

For full setup and troubleshooting see [section 14](#14-windows-task-scheduler-setup) and [section 12](#12-troubleshooting).

---

## 5. Preconditions

### Google Sheets

Two tabs must exist in the configured spreadsheet, with the exact column headers shown below.

**Tab: `automation_stage0_input`** (read-only for this system)

| Column header | Notes |
|---|---|
| `Imię i nazwisko / Firma` | Lead full name or company name |
| `Email` | Lead email address |
| `Telefon dodatkowy` | Additional phone (not processed, may be blank) |

This tab is populated externally (e.g. Meta Lead Ads export). The system reads it but never
writes to it.

**Tab: `automation_stage0_status`** (read-write)

The operator must create this tab manually with the following headers in row 1,
**in exact order and spelling** (copy-paste recommended):

| Column header | Who writes it | Notes |
|---|---|---|
| `Lead` | System (once, at row creation) | Lead full name or company — copied from input tab |
| `Email` | System (once, at row creation) | Lead email address — logical key, unique per row |
| `Email wysłany` | System | Filled on successful send (`YYYY-MM-DD HH:MM`, Europe/Warsaw) |
| `Status emaila` | System | `SENT` \| `ERROR: <message>` \| empty |
| `Follow-up od` | System | Filled 3 days after successful send |
| `Wymaga follow-upu` | System | `YES` / `NO` |
| `Follow-up wykonany` | Sales team (manual) | Filled when follow-up is completed |

The system creates rows automatically but will fail if the tab does not exist or any
header is misspelled. Headers are case-sensitive and space-sensitive.

### SMTP

- SMTP server accessible from the host where the job runs.
- STARTTLS on port 587 (standard). Other ports can be configured via `SMTP_PORT`.
- Valid credentials for the sending account (`SMTP_USER` / `SMTP_PASS`).
- The sender address (`SMTP_FROM_EMAIL`) must be authorised to send from the SMTP server.

### Google Credentials (Service Account)

- A Google Cloud service account with **Sheets Editor** access on the spreadsheet.
  Viewer access is not sufficient.
- The service account key file (JSON) placed at the path configured in
  `GOOGLE_SERVICE_ACCOUNT_JSON` (default: `secrets/service_account.json`).
- The `secrets/` directory is not committed to version control.

### PDF Attachments

Three PDF files are attached to every outbound email. Their paths are set in
`STAGE0_PDF_1`, `STAGE0_PDF_2`, `STAGE0_PDF_3`. The files must exist at those paths
when the job runs. The `assets/attachments/` directory is not committed to version control.

---

## 6. Environment Variables

Copy `.env.example` to `.env` and fill in every value before running the job.

### Google Sheets

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_SHEET_ID` | Yes | Spreadsheet ID from the Google Sheets URL |
| `GOOGLE_SHEET_TAB_INPUT` | Yes | Name of the input tab (default: `automation_stage0_input`) |
| `GOOGLE_SHEET_TAB_STATUS` | Yes | Name of the status tab (default: `automation_stage0_status`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes | Path to service account JSON key file (default: `secrets/service_account.json`) |

### SMTP

| Variable | Required | Description |
|---|---|---|
| `SMTP_HOST` | Yes | SMTP server hostname |
| `SMTP_PORT` | Yes | SMTP port (typically `587` for STARTTLS) |
| `SMTP_USER` | Yes | SMTP login username |
| `SMTP_PASS` | Yes | SMTP login password |
| `SMTP_FROM_EMAIL` | Yes | Sender email address shown to recipients |
| `SMTP_FROM_NAME` | Yes | Sender display name shown to recipients |

### Runtime

| Variable | Required | Description |
|---|---|---|
| `CALENDAR_URL` | Yes | Calendar booking link included in every email |
| `STAGE0_PDF_1` | Yes | Path to first PDF attachment |
| `STAGE0_PDF_2` | Yes | Path to second PDF attachment |
| `STAGE0_PDF_3` | Yes | Path to third PDF attachment |

### Test Mode

| Variable | Required | Description |
|---|---|---|
| `STAGE0_TEST_MODE` | No | Set to `1` to enable test mode. Default: `0` (disabled). |
| `TEST_RECIPIENT_EMAIL` | Conditional | **Required when `STAGE0_TEST_MODE=1`**. All outbound emails are redirected to this address. Real lead addresses are never contacted while test mode is active. |

**Test mode behaviour:**

- When `STAGE0_TEST_MODE=1` and `TEST_RECIPIENT_EMAIL` is set: every email that would
  normally go to a lead is instead delivered to `TEST_RECIPIENT_EMAIL`. The real lead
  address never reaches the SMTP layer.
- When `STAGE0_TEST_MODE=1` and `TEST_RECIPIENT_EMAIL` is missing or blank: the job
  raises an error immediately and sends nothing.
- When `STAGE0_TEST_MODE=0` (or unset): emails go to the actual lead addresses from the
  input sheet.

---

## 7. How to Run Locally

### Setup (technical operator only)

```bash
git clone <repo-url> && cd ai-sales-automation
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
cp .env.example .env
# Edit .env — fill in all required values
```

Place the service account JSON at the path in `GOOGLE_SERVICE_ACCOUNT_JSON`.
Place the three PDF files at the paths in `STAGE0_PDF_1/2/3`.

### Run the job (test mode — use before every production change)

```bash
# Set STAGE0_TEST_MODE=1 and TEST_RECIPIENT_EMAIL in .env, then:
python -m src.stage0.job
```

Check the inbox at `TEST_RECIPIENT_EMAIL` to confirm delivery. Check the status tab in
Google Sheets to confirm rows were written.

### Run the job (production mode)

Ensure `STAGE0_TEST_MODE=0` (or unset) in `.env`, then:

```bash
python -m src.stage0.job
```

### Run tests

```bash
pytest -q                       # full suite (no network, no credentials required)
pytest tests/stage0/ -q         # stage 0 tests only
```

All tests use mocks. A passing test suite does not require a live Google Sheet or SMTP
server.

---

## 8. Scheduler Operation

The intended scheduler target is:

```bash
python -m src.stage0.job
```

### Idempotency guarantee

The job is safe to run multiple times. Once `Email wysłany` is written for a lead,
that lead is never processed again — regardless of how many times the scheduler fires.
Running the job more often than needed causes no harm.

### Recommended cadence

Every 15–60 minutes is sufficient for typical lead volumes. More frequent runs reduce
response latency; less frequent runs are fine if same-day response is acceptable.

### Example cron line (Linux)

```
*/30 * * * * cd /app && .venv/bin/python -m src.stage0.job >> /var/log/stage0.log 2>&1
```

### Cloud schedulers

GCP Cloud Scheduler, AWS EventBridge, or any task runner that invokes a shell command can
be used. No persistent process or message queue is required.

---

## 9. Status Fields and Interpretation

All status information is in the `automation_stage0_status` tab.

### `Email wysłany`

| Value | Meaning |
|---|---|
| Empty | Email has not been successfully delivered yet. Lead is eligible for processing. |
| `YYYY-MM-DD HH:MM` | Email was confirmed delivered at this timestamp (Europe/Warsaw). Lead will not be processed again. |

### `Status emaila`

| Value | Meaning |
|---|---|
| Empty | No send attempt has been made yet. |
| `SENT` | Email delivered successfully. |
| `ERROR: <message>` | Last send attempt failed. `Email wysłany` is empty — lead will be retried on next run. |

A lead with `Email wysłany` set is **never retried**, even if `Status emaila`
shows `ERROR`. Both fields being set simultaneously is an edge case that is handled
conservatively (no retry).

### `Follow-up od`

Set automatically to `Email wysłany + 3 days` after a successful send. Empty means the
email has not been sent yet, or the follow-up logic has not run since the send.

### `Wymaga follow-upu`

| Value | Meaning |
|---|---|
| `YES` | The 3-day window has passed; the sales team should follow up manually. |
| `NO` | Follow-up is either not yet due, or has already been completed. |

The sales team sets `Follow-up wykonany` manually when the follow-up is done. The
system then sets `Wymaga follow-upu = NO` on the next run.

### Typical row lifecycle

```
[lead appears in input sheet]
    Lead = "Jan Kowalski"   Email = "jan@example.com"
    Email wysłany = ""      Status emaila = ""
    Follow-up od = ""       Wymaga follow-upu = ""

[job runs — send succeeds]
    Email wysłany   = "2025-03-10 09:15"
    Status emaila   = "SENT"
    Follow-up od    = "2025-03-13 09:15"
    Wymaga follow-upu = "NO"     <- scheduled, not yet due

[job runs — 3 days pass, now >= Follow-up od]
    Wymaga follow-upu = "YES"    <- sales team should follow up

[sales team follows up -> sets Follow-up wykonany manually]
[next job run]
    Wymaga follow-upu = "NO"

[job runs — send fails]
    Email wysłany = ""
    Status emaila = "ERROR: [Errno 111] Connection refused"
    (lead will be retried on next run)
```

---

## 10. Safe Change Procedure

### Switching from a test sheet to the production sheet

1. Confirm the production spreadsheet has both required tabs with correct headers (section 5).
2. Confirm the service account has Sheets Editor access on the production sheet.
3. Update `GOOGLE_SHEET_ID` in `.env` to the production spreadsheet ID.
4. Update `GOOGLE_SHEET_TAB_INPUT` and `GOOGLE_SHEET_TAB_STATUS` if the tab names differ.
5. Run one job cycle in test mode against the production sheet first:
   - Set `STAGE0_TEST_MODE=1` and `TEST_RECIPIENT_EMAIL=<internal address>`.
   - Run `python -m src.stage0.job`.
   - Confirm the status tab received rows and the test inbox received emails.
6. Proceed to the next section to disable test mode.

### Disabling test mode — pre-production checklist

Work through this list in order before setting `STAGE0_TEST_MODE=0`:

- [ ] `GOOGLE_SHEET_ID` points to the production spreadsheet.
- [ ] `GOOGLE_SHEET_TAB_INPUT` and `GOOGLE_SHEET_TAB_STATUS` match the production tab names.
- [ ] A test-mode run against the production sheet completed without errors (step 5 above).
- [ ] The service account has Sheets Editor access on the production sheet.
- [ ] SMTP credentials are valid and the sending quota is sufficient.
- [ ] PDF attachments exist at the configured paths.
- [ ] `CALENDAR_URL` is the correct production booking link.
- [ ] Set `STAGE0_TEST_MODE=0` (or remove the variable entirely).
- [ ] Confirm `TEST_RECIPIENT_EMAIL` is empty or absent.

### First manual production run

Before enabling the scheduler, run the job once manually:

```bash
python -m src.stage0.job
```

Confirm:
- Log shows `Stage0 job complete — scanned=N new=M sent=M failed=0`.
- Status tab shows `Status emaila = SENT` and `Email wysłany` filled for each
  processed lead.
- No `ERROR:` entries in `Status emaila`.

**Enable the scheduler only after this run completes without errors.**

### Rollback procedure

If a production run produces unexpected results:

1. **Immediately enable test mode** to prevent further sends to real leads:
   set `STAGE0_TEST_MODE=1` in `.env` and restart/redeploy the scheduler.
2. If you switched to the wrong spreadsheet, revert `GOOGLE_SHEET_ID` to the previous value.
3. To reset a specific lead (so it will be re-processed on the next run):
   - In the `automation_stage0_status` tab, clear the `Email wysłany` and
     `Status emaila` cells for that lead's row.
   - Do **not** modify the `automation_stage0_input` tab.
4. Investigate the root cause before re-running in production mode.

---

## 11. First 48 Hours Monitoring

Run through this checklist after enabling the scheduler in production for the first time.

**Check at least twice per day during the first 48 hours.**

### Log file

- [ ] Open `logs\stage0_scheduler.log`.
- [ ] Confirm repeating pairs of `Stage0 job start` / `Stage0 job complete` at the configured interval.
- [ ] Confirm no gaps longer than two trigger intervals (indicates missed runs — check Task Scheduler status).
- [ ] Confirm `failed=0` in every `job complete` line. A non-zero value is an alert condition.

### Google Sheets status tab

- [ ] `Status emaila` column contains only `SENT` or is empty for unprocessed leads.
- [ ] No `ERROR:` values. If present, note the error message and investigate root cause before the next cycle.
- [ ] `Email wysłany` is filled for every lead that received an email.
- [ ] `Follow-up od` is set correctly to `Email wysłany + 3 days` for all sent leads.

### SMTP

- [ ] Confirm the sending account has not been throttled or suspended by checking the mail provider's dashboard.
- [ ] Verify that sent emails are landing in recipients' inboxes and not in spam (check with a test send to a known address if needed).

### Escalation

If any of the above checks fail and the root cause is not immediately clear:
1. Set `STAGE0_TEST_MODE=1` in `.env` to stop real sends immediately.
2. Preserve the full `logs\stage0_scheduler.log` file.
3. Check `Status emaila` in the status tab for error details.
4. Investigate and resolve before re-enabling production mode.

---

## 12. Troubleshooting

### Missing environment variable

**Symptom:** Job exits immediately with a message like `KeyError: 'SMTP_HOST'` or
`ValueError: GOOGLE_SHEET_ID is required`.

**Fix:** Check that `.env` exists, is in the working directory, and contains all required
variables. Re-read section 6.

---

### Google Sheets authentication error

**Symptom:** `gspread.exceptions.APIError` or `google.auth.exceptions.TransportError`.

**What to check:**
1. The service account JSON file exists at the path in `GOOGLE_SERVICE_ACCOUNT_JSON`.
2. The service account email has been granted **Sheets Editor** access on the spreadsheet
   (share the sheet with the service account email address, the same way you share with a
   person).
3. `GOOGLE_SHEET_ID` matches the spreadsheet (copy it from the spreadsheet URL).

---

### Sheets tab or column not found

**Symptom:** `WorksheetNotFound` or `KeyError` on a column name.

**What to check:**
1. The tab names in `GOOGLE_SHEET_TAB_INPUT` and `GOOGLE_SHEET_TAB_STATUS` match the
   actual tab names in the spreadsheet exactly (case-sensitive).
2. The column headers in `automation_stage0_status` match the names listed in section 5.

---

### SMTP error

**Symptom:** `SMTPAuthenticationError`, `ConnectionRefusedError`, or `TimeoutError` during
send. The lead's row will show `Status emaila = ERROR: <message>`.

**What to check:**
1. `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` are correct.
2. The SMTP server is reachable from the host (firewall, VPN).
3. The sending account has not been rate-limited or suspended.

The lead remains eligible for retry. Fix the SMTP issue, then re-run the job.

---

### PDF attachment not found

**Symptom:** `FileNotFoundError` for a PDF path.

**Fix:** Ensure the files exist at the paths configured in `STAGE0_PDF_1/2/3`.

---

### Test mode is active but `TEST_RECIPIENT_EMAIL` is missing

**Symptom:** `RuntimeError: TEST_RECIPIENT_EMAIL is required when STAGE0_TEST_MODE=1`.

**Fix:** Either set `TEST_RECIPIENT_EMAIL` to an internal address, or set
`STAGE0_TEST_MODE=0` to disable test mode.

---

### How to confirm test mode is active

Look for this line near the top of the log output:

```
[INFO] src.stage0.job — TEST MODE active — all outbound emails go to test recipient
```

If this line is absent, the job is running in production mode (emails go to real leads).

---

### Where to look in logs

The job emits structured log lines. Key lines to watch:

```
Stage0 job start — test_mode=False
Stage0 job complete — scanned=12 new=3 sent=3 failed=0
```

Log lines never contain email addresses, names, or phone numbers. If `failed` is
non-zero, check the `Status emaila` column in the status tab for `ERROR:` entries —
the error message is written there.

---

## 13. Emergency Stop

### Option 1 — Enable test mode (preferred: stops real sends immediately)

Set `STAGE0_TEST_MODE=1` in `.env` and save. No scheduler restart needed — variables are
read from `.env` at the start of each job run.

This takes effect on the next run and redirects all outbound emails to `TEST_RECIPIENT_EMAIL`
instead of real leads. The job continues to execute and write status rows, making it easy to
verify the stop took effect without losing observability.

**Use this option first** when the goal is to stop real sends without fully disabling the
scheduler.

After the next scheduled run, confirm the log contains:

```
[INFO] src.stage0.job — TEST MODE active — all outbound emails go to test recipient
```

### Option 2 — Stop the scheduler (full stop)

Use this when you need to halt all job execution, not just real sends.

- **Task Scheduler (Windows):** Right-click the task → **Disable**. Takes effect immediately.
  Re-enable via right-click → **Enable**.
- **Cron:** Comment out or remove the cron entry (`crontab -e`).
- **Cloud scheduler:** Pause or disable the schedule in your cloud console.
- **Systemd timer:** `systemctl stop <timer-name> && systemctl disable <timer-name>`.

The job has no persistent process — it exits after each run. Disabling the scheduler
prevents future invocations but does not interrupt a run already in progress.

### When to use each option

| Situation | Recommended action |
|---|---|
| Real sends must stop immediately, scheduler should keep running | Set `STAGE0_TEST_MODE=1` (Option 1) |
| All job execution must stop (maintenance, incident, decommission) | Disable the scheduler (Option 2) |
| Need fastest stop with highest confidence | Option 1 first, then Option 2 if needed |

---

## 14. Windows Task Scheduler Setup

This section is for operators running Stage 0 on a Windows machine without access to
cron or cloud schedulers. No knowledge of the codebase is required.

> **Encoding note (Windows):** If you see garbled characters when reading log files or
> copying Polish column headers, open the file in VS Code (it reads UTF-8 correctly),
> or run `chcp 65001` in PowerShell before copy-pasting any Polish text.

---

### 14.1 Prerequisites

Before configuring the task, verify the following on the Windows host:

1. **Python 3.11+** installed and on the system PATH.
   Verify: open PowerShell and run `python --version`. Expected output: `Python 3.11.x` or later.

2. **Repository cloned** to a stable local path with no spaces if possible.
   Example: `C:\apps\ai-sales-automation`

3. **Virtual environment created and dependencies installed:**
   ```
   cd C:\apps\ai-sales-automation
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **`.env` file present** at the repository root with all required variables filled in
   (see section 6). The `.env` file must be at `C:\apps\ai-sales-automation\.env`.

5. **`secrets\service_account.json`** present at the path set in
   `GOOGLE_SERVICE_ACCOUNT_JSON`.

6. **PDF attachments** present at the paths set in `STAGE0_PDF_1/2/3`.

7. **`logs\` directory created** inside the repository root (Task Scheduler will not
   create it automatically):
   ```
   mkdir C:\apps\ai-sales-automation\logs
   ```

---

### 14.2 Creating the Task (Create Task, not Basic Task)

Open **Task Scheduler** (`taskschd.msc`) and in the right-hand panel choose
**Create Task…** (not "Create Basic Task"). Work through each tab in order.

---

#### General tab

| Field | Value |
|---|---|
| **Name** | `Stage0 Auto-Reply Job` |
| **Description** | Sends auto-reply emails to new sales leads and updates follow-up status. |
| **Security options** | See below |

**Security options — two choices:**

| Scenario | Setting |
|---|---|
| Machine is always on, operator is always logged in | *Run only when user is logged on* — simpler, no password required. |
| Machine may be unattended (server, background PC) | *Run whether user is logged on or not* — requires entering the Windows account password when saving the task. Recommended for production. |

Leave **Run with highest privileges** unchecked unless the repository path or Python
installation requires elevated access. In most deployments it is not needed.

---

#### Triggers tab

Click **New…** and set:

| Field | Value |
|---|---|
| **Begin the task** | On a schedule |
| **Settings** | Daily |
| **Start** | Today's date, `00:00:00` (start of day) |
| **Advanced settings — Repeat task every** | `5 minutes` (or `30 minutes` for lower volume) |
| **for a duration of** | `Indefinitely` |
| **Enabled** | Checked |

Click **OK**.

> To run every 5 minutes: set "Repeat task every" = 5 minutes, duration = Indefinitely.
> Task Scheduler does not offer a sub-minute interval.

---

#### Actions tab

Click **New…** and configure:

| Field | Value |
|---|---|
| **Action** | Start a program |
| **Program/script** | `cmd.exe` |
| **Add arguments** | `/c scripts\run_stage0_job.cmd` |
| **Start in** | `C:\apps\ai-sales-automation` |

---

#### Conditions tab

Leave default values unless the machine is a laptop:

| Setting | Value |
|---|---|
| **Start the task only if the computer is on AC power** | Uncheck if the host is a desktop or server. Keep checked for laptops. |
| **Wake the computer to run this task** | Leave unchecked (not needed). |

---

#### Settings tab

| Setting | Value | Reason |
|---|---|---|
| **Allow task to be run on demand** | Checked | Enables the "Run" button for manual testing. |
| **Run task as soon as possible after a scheduled start is missed** | Checked | Recovers missed runs after a reboot. |
| **Stop the task if it runs longer than** | `5 minutes` | The job should complete in seconds. A 5-minute timeout prevents a hung process from blocking the next cycle. |
| **If the task is already running, then the following rule applies** | **Do not start a new instance** | Prevents overlap if a slow Sheets API call extends beyond the trigger interval. |

Click **OK** and enter the Windows account password when prompted (required for
"Run whether user is logged on or not").

---

### 14.3 Ensuring `.env` is Loaded

The job loads `.env` from the **current working directory**. Task Scheduler sets the
working directory to the value of the **Start in** field in the Actions tab.

**Required:** `Start in` must be set to the repository root (e.g.
`C:\apps\ai-sales-automation`). If it is left empty, `.env` will not be found and the
job will fail with a missing-variable error.

**How to verify `.env` is loading correctly:**

After the first scheduled run, open `logs\stage0_scheduler.log` and confirm you see:

```
Stage0 job start — test_mode=False
```

If instead you see `KeyError` or `ValueError` for a variable name, `.env` is not being
read. Check that:
1. `Start in` in the Action is set to the repository root.
2. The `.env` file exists at the repository root (not in a subdirectory).
3. The `.env` file contains all required variables (section 6).

---

### Quick verification (Windows)

- Scheduler task name: `ai-sales-automation Stage0`
- Log file (wrapper): `logs/stage0_scheduler.log`

To confirm the job is running:
1) Open `logs/stage0_scheduler.log`
2) Verify you see repeating pairs of lines:
   - `Stage0 job start`
   - `Stage0 job complete`
   (timestamps should advance roughly at the configured interval, e.g. every 5 minutes)

---

### 14.4 Operational Procedures

#### Manual run (on-demand)

1. Open Task Scheduler → Task Scheduler Library.
2. Find `Stage0 Auto-Reply Job`.
3. In the right-hand panel click **Run**.
4. Wait a few seconds, then press **F5** to refresh.
5. Check the **Last Run Result** column. Expected value: `0x0` (success).
   Any other value indicates the job exited with an error — open `logs\stage0_scheduler.log`
   for details.

#### Read the last run result codes

| Code | Meaning |
|---|---|
| `0x0` | Success |
| `0x1` | Python exited with `sys.exit(1)` — job failed; check log |
| `0x41301` | Task is currently running (not an error) |
| `0x8004131F` | No instances allowed to run concurrently (task was already running when triggered) |

#### Restart a running task

Right-click the task → **End** → wait for status to clear → **Run**.

#### Disable the task (emergency stop)

Right-click the task → **Disable**. The task will no longer trigger automatically.
Re-enable via right-click → **Enable**.

Disabling is the fastest way to stop all future runs on Windows. It takes effect
immediately — the next scheduled trigger is skipped.

#### Verify the job is running on schedule

In `logs\stage0_scheduler.log`, each cycle appends two timestamped lines:

```
2025-03-10 09:30:01 [INFO] src.stage0.job — Stage0 job start — test_mode=False
2025-03-10 09:30:03 [INFO] src.stage0.job — Stage0 job complete — scanned=5 new=0 sent=0 failed=0
```

Confirm the timestamps are spaced at the configured interval (e.g. every 5 or 30 minutes).
If lines stop appearing, check whether the task is still enabled and whether the last run
result is `0x0`.

---

### 14.5 Emergency Stop Drill on Windows (Test Mode)

Use this procedure to verify that the system can be safely switched to test mode before
disabling it completely, or whenever you need to stop real sends without stopping the job.

**Step 1 — Set test mode in `.env`:**

Open `C:\apps\ai-sales-automation\.env` and set:

```
STAGE0_TEST_MODE=1
TEST_RECIPIENT_EMAIL=test-recipient@example.com
```

Save the file. No restart of Task Scheduler is needed — variables are read from `.env`
at the start of each job run.

**Step 2 — Trigger a manual run:**

Open Task Scheduler → right-click `Stage0 Auto-Reply Job` → **Run**.

**Step 3 — Verify test mode is active in the log:**

Open `logs\stage0_scheduler.log` and confirm the following line appears in the most recent run:

```
[INFO] src.stage0.job — TEST MODE active — all outbound emails go to test recipient
```

If this line is absent, `.env` may not have been saved or the old value is still cached.
Verify the file content and run again.

**Step 4 — Verify in the test inbox:**

Check the inbox at `TEST_RECIPIENT_EMAIL`. You should receive one email per lead that was
eligible for processing. No email should arrive at any real lead address.

**Step 5 — Verify in Google Sheets:**

Open the `automation_stage0_status` tab. For each lead that was processed during the
drill:
- `Email wysłany` should contain a timestamp.
- `Status emaila` should be `SENT`.

The status sheet is written even in test mode, so the drill is a full end-to-end
verification of the pipeline (credentials, SMTP, Sheets write) with zero risk to real
leads.

**Step 6 — Restore production mode:**

When ready to resume production sends, set `STAGE0_TEST_MODE=0` (or remove the line)
in `.env` and save. The next job run will send to real leads.

---

### 14.6 Ten-Cycle Operational Verification (Windows)

Run through this checklist after the initial setup or after any significant change to the
environment (new machine, updated `.env`, re-created virtual environment).

**Prerequisites:** Task Scheduler configured, job enabled, at least one new lead present
in `automation_stage0_input`.

---

#### Phase 1 — First-send verification (cycles 1–3)

- [ ] Trigger manual run (cycle 1). Check `logs\stage0_scheduler.log` for:
  ```
  Stage0 job complete — scanned=N new=M sent=M failed=0
  ```
  where `M >= 1` for a new lead.
- [ ] Open `automation_stage0_status`. Confirm the lead's row has:
  - `Email wysłany` filled with a timestamp.
  - `Status emaila = SENT`.
  - `Follow-up od` filled with `sent_at + 3 days`.
  - `Wymaga follow-upu = NO` (not yet due).
- [ ] Confirm the lead received the email at their real address (or at
  `TEST_RECIPIENT_EMAIL` in test mode).
- [ ] Trigger manual run again (cycle 2). Confirm in log:
  ```
  Stage0 job complete — scanned=N new=0 sent=0 failed=0
  ```
  `new=0` confirms idempotency — no duplicate send.
- [ ] Trigger a third run (cycle 3). Confirm `new=0` again. No new rows in the status
  sheet for the already-processed lead.

---

#### Phase 2 — Scheduled-run stability (cycles 4–7)

- [ ] Let the task run automatically for at least 4 scheduled cycles without manual
  intervention.
- [ ] After 4 cycles, open `logs\stage0_scheduler.log` and count the `Stage0 job complete` lines.
  There should be exactly 4 new lines, each with `new=0 sent=0 failed=0` (assuming no
  new leads arrived).
- [ ] Confirm no duplicate entries appear in `automation_stage0_status` for any existing
  lead.

---

#### Phase 3 — Follow-up flag verification (cycle 8)

- [ ] Locate a row in `automation_stage0_status` where `Follow-up od` is in the past
  (i.e. the lead was sent the auto-reply more than 3 days ago).
- [ ] Trigger a manual run and confirm the log shows:
  ```
  Stage0 follow-up step complete — updated=1
  ```
  (or higher, depending on how many leads are past due).
- [ ] In `automation_stage0_status`, confirm the lead's row now shows:
  - `Wymaga follow-upu = YES`.
- [ ] Simulate completion: manually enter a timestamp in `Follow-up wykonany` for that
  row.
- [ ] Trigger another run (cycle 9) and confirm:
  - Log: `Stage0 follow-up step complete — updated=1`.
  - Sheet: `Wymaga follow-upu = NO`.

---

#### Phase 4 — Stable state (cycle 10)

- [ ] With no new leads and all follow-ups resolved, trigger a final run (cycle 10).
- [ ] Confirm in log:
  ```
  Stage0 job complete — scanned=N new=0 sent=0 failed=0
  Stage0 follow-up step complete — updated=0
  ```
  Both counters at zero confirms the system is in a stable, fully-processed state.
- [ ] Confirm no new rows or changes appear in the status sheet.

---

**Checklist complete.** The system is verified for correct first-send, idempotency,
follow-up scheduling, follow-up completion, and stable-state behaviour on Windows.
