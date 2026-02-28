# Stage 0 — Operational Runbook

This document is the day-to-day operations reference for Stage 0 of the sales automation
system. It is written for operators who are not familiar with the codebase. For architecture
and developer documentation see [README.md](README.md).

---

## 1. Purpose

Stage 0 provides automated first-touch email handling for inbound sales leads.

**What it does:**

- Reads new leads from the `automation_stage0_input` tab in Google Sheets.
- Sends each new lead a Polish-language auto-reply email with 3 PDF attachments and a
  calendar booking link.
- Records the send result in the `automation_stage0_status` tab (timestamp + status).
- After 3 days without a human response, marks the lead as requiring follow-up
  (`followup_required = YES`) so the sales team can act.

**What it does not do:**

- It does not send follow-up emails automatically — only flags them for humans.
- It does not write to the input sheet.
- It never sends to real leads while test mode is active.

---

## 2. Preconditions

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

| Column header | Notes |
|---|---|
| `email` | Lead email address (key — must be unique per row) |
| `auto_email_sent_at` | Filled by the system on successful send |
| `auto_email_status` | Filled by the system on every run attempt |
| `followup_due_at` | Filled by the system 3 days after successful send |
| `followup_required` | `YES` / `NO` — managed by the system |
| `followup_completed_at` | Filled manually by the sales team when follow-up is done |

Create this tab manually before the first run. The system creates rows automatically but
will fail if the tab or its headers do not exist.

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

## 3. Environment Variables

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

## 4. How to Run Locally

### Setup

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

### Run the job (test mode — recommended for first run)

```bash
# Set STAGE0_TEST_MODE=1 and TEST_RECIPIENT_EMAIL in .env, then:
python -m src.stage0.job
```

Or pass vars inline (Linux / macOS):

```bash
STAGE0_TEST_MODE=1 TEST_RECIPIENT_EMAIL=you@yourcompany.com python -m src.stage0.job
```

Check your inbox at `TEST_RECIPIENT_EMAIL` to confirm delivery. Check the status tab in
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

## 5. Scheduler Operation

The intended scheduler target is:

```bash
python -m src.stage0.job
```

### Idempotency guarantee

The job is safe to run multiple times. Once `auto_email_sent_at` is written for a lead,
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

## 6. Status Fields and Interpretation

All status information is in the `automation_stage0_status` tab.

### `auto_email_sent_at`

| Value | Meaning |
|---|---|
| Empty | Email has not been successfully delivered yet. Lead is eligible for processing. |
| `YYYY-MM-DD HH:MM` | Email was confirmed delivered at this timestamp (Europe/Warsaw). Lead will not be processed again. |

### `auto_email_status`

| Value | Meaning |
|---|---|
| Empty | No send attempt has been made yet. |
| `SENT` | Email delivered successfully. |
| `ERROR: <message>` | Last send attempt failed. `auto_email_sent_at` is empty — lead will be retried on next run. |

A lead with `auto_email_sent_at` set is **never retried**, even if `auto_email_status`
shows `ERROR`. Both fields being set simultaneously is an edge case that is handled
conservatively (no retry).

### `followup_due_at`

Set automatically to `sent_at + 3 days` after a successful send. Empty means the email
has not been sent yet, or the follow-up logic has not run since the send.

### `followup_required`

| Value | Meaning |
|---|---|
| `YES` | The 3-day window has passed; the sales team should follow up manually. |
| `NO` | Follow-up is either not yet due, or has already been completed. |

The sales team sets `followup_completed_at` manually when the follow-up is done. The
system then sets `followup_required = NO` on the next run.

### Typical row lifecycle

```
[lead appears in input sheet]
    auto_email_sent_at = ""    auto_email_status = ""
    followup_due_at = ""       followup_required = ""

[job runs — send succeeds]
    auto_email_sent_at = "2025-03-10 09:15"
    auto_email_status  = "SENT"
    followup_due_at    = "2025-03-13 09:15"
    followup_required  = "NO"     <- scheduled, not yet due

[job runs — 3 days pass, now >= followup_due_at]
    followup_required  = "YES"    <- sales team should follow up

[sales team follows up -> sets followup_completed_at manually]
[next job run]
    followup_required  = "NO"

[job runs — send fails]
    auto_email_sent_at = ""
    auto_email_status  = "ERROR: [Errno 111] Connection refused"
    (lead will be retried on next run)
```

---

## 7. Troubleshooting

### Missing environment variable

**Symptom:** Job exits immediately with a message like `KeyError: 'SMTP_HOST'` or
`ValueError: GOOGLE_SHEET_ID is required`.

**Fix:** Check that `.env` exists, is in the working directory, and contains all required
variables. Re-read section 3.

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
2. The column headers in `automation_stage0_status` match the names listed in section 2.

---

### SMTP error

**Symptom:** `SMTPAuthenticationError`, `ConnectionRefusedError`, or `TimeoutError` during
send. The lead's row will show `auto_email_status = ERROR: <message>`.

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
non-zero, check the `auto_email_status` column in the status tab for `ERROR:` entries —
the error message is written there.

---

## 8. Safe Change Procedure

### Switching from a test sheet to the production sheet

1. Confirm the production spreadsheet has both required tabs with correct headers (section 2).
2. Confirm the service account has Sheets Editor access on the production sheet.
3. Update `GOOGLE_SHEET_ID` in `.env` to the production spreadsheet ID.
4. Update `GOOGLE_SHEET_TAB_INPUT` and `GOOGLE_SHEET_TAB_STATUS` if the tab names differ.
5. Run one job cycle in test mode against the production sheet first:
   - Set `STAGE0_TEST_MODE=1` and `TEST_RECIPIENT_EMAIL=<your address>`.
   - Run `python -m src.stage0.job`.
   - Confirm the status tab received rows and the test inbox received emails.
6. Proceed to the next section to disable test mode.

### Disabling test mode (pre-production checklist)

Work through this list in order before removing `STAGE0_TEST_MODE`:

- [ ] `GOOGLE_SHEET_ID` points to the production spreadsheet.
- [ ] `GOOGLE_SHEET_TAB_INPUT` and `GOOGLE_SHEET_TAB_STATUS` match the production tab names.
- [ ] A test-mode run against the production sheet completed without errors (step 5 above).
- [ ] The service account has Sheets Editor access on the production sheet.
- [ ] SMTP credentials are valid and the sending quota is sufficient.
- [ ] PDF attachments exist at the configured paths.
- [ ] `CALENDAR_URL` is the correct production booking link.
- [ ] Set `STAGE0_TEST_MODE=0` (or remove the variable entirely).
- [ ] Confirm `TEST_RECIPIENT_EMAIL` is empty or absent.
- [ ] Run `python -m src.stage0.job` once manually and observe logs.
- [ ] Confirm `auto_email_status = SENT` appears in the status tab for the expected leads.

### Rollback procedure

If a production run produces unexpected results:

1. **Immediately enable test mode** to prevent further sends to real leads:
   set `STAGE0_TEST_MODE=1` in `.env` and restart/redeploy the scheduler.
2. If you switched to the wrong spreadsheet, revert `GOOGLE_SHEET_ID` to the previous value.
3. To reset a specific lead (so it will be re-processed on the next run):
   - In the `automation_stage0_status` tab, clear the `auto_email_sent_at` and
     `auto_email_status` cells for that lead's row.
   - Do **not** modify the `automation_stage0_input` tab.
4. Investigate the root cause before re-running in production mode.

---

## 9. Emergency Stop

### Stop the scheduler

The job has no persistent process — it exits after each run. To stop future runs:
- **Cron:** comment out or remove the cron entry (`crontab -e`), or set `STAGE0_TEST_MODE=1`.
- **Cloud scheduler:** pause or disable the schedule in your cloud console.
- **Systemd timer:** `systemctl stop <timer-name> && systemctl disable <timer-name>`.

### Prevent sending immediately (without stopping the scheduler)

Set `STAGE0_TEST_MODE=1` in the environment and restart/redeploy. This takes effect on
the next run. The job will still execute and write status rows, but all emails will be
redirected to `TEST_RECIPIENT_EMAIL` instead of real leads. No sends to real addresses
will occur while this flag is set.

This is the safest and fastest way to halt outbound email without fully disabling the
scheduler.

### Confirm the stop took effect

After the next scheduled run, check the log for:

```
[INFO] src.stage0.job — TEST MODE active — all outbound emails go to test recipient
```

And confirm that `auto_email_status` in the status tab shows `SENT` only for rows
processed during the test-mode run (verify by checking the `auto_email_sent_at`
timestamp).

---

## 10. Windows Task Scheduler Setup

This section is for operators running Stage 0 on a Windows machine without access to
cron or cloud schedulers. No knowledge of the codebase is required.

---

### 10.1 Prerequisites

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
   (see section 3). The `.env` file must be at `C:\apps\ai-sales-automation\.env`.

5. **`secrets\service_account.json`** present at the path set in
   `GOOGLE_SERVICE_ACCOUNT_JSON`.

6. **PDF attachments** present at the paths set in `STAGE0_PDF_1/2/3`.

7. **`logs\` directory created** inside the repository root (Task Scheduler will not
   create it automatically):
   ```
   mkdir C:\apps\ai-sales-automation\logs
   ```

---

### 10.2 Creating the Task (Create Task, not Basic Task)

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

### 10.3 Ensuring `.env` is Loaded

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
3. The `.env` file contains all required variables (section 3).

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

### 10.4 Operational Procedures

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

### 10.5 Emergency Stop Drill on Windows (Test Mode)

Use this procedure to verify that the system can be safely switched to test mode before
disabling it completely, or whenever you need to stop real sends without stopping the job.

**Step 1 — Set test mode in `.env`:**

Open `C:\apps\ai-sales-automation\.env` and set:

```
STAGE0_TEST_MODE=1
TEST_RECIPIENT_EMAIL=operator@yourcompany.com
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
- `auto_email_sent_at` should contain a timestamp.
- `auto_email_status` should be `SENT`.

The status sheet is written even in test mode, so the drill is a full end-to-end
verification of the pipeline (credentials, SMTP, Sheets write) with zero risk to real
leads.

**Step 6 — Restore production mode:**

When ready to resume production sends, set `STAGE0_TEST_MODE=0` (or remove the line)
in `.env` and save. The next job run will send to real leads.

---

### 10.6 Ten-Cycle Operational Verification (Windows)

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
  - `auto_email_sent_at` filled with a timestamp.
  - `auto_email_status = SENT`.
  - `followup_due_at` filled with `sent_at + 3 days`.
  - `followup_required = NO` (not yet due).
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

- [ ] Locate a row in `automation_stage0_status` where `followup_due_at` is in the past
  (i.e. the lead was sent the auto-reply more than 3 days ago).
- [ ] Trigger a manual run and confirm the log shows:
  ```
  Stage0 follow-up step complete — updated=1
  ```
  (or higher, depending on how many leads are past due).
- [ ] In `automation_stage0_status`, confirm the lead's row now shows:
  - `followup_required = YES`.
- [ ] Simulate completion: manually enter a timestamp in `followup_completed_at` for that
  row.
- [ ] Trigger another run (cycle 9) and confirm:
  - Log: `Stage0 follow-up step complete — updated=1`.
  - Sheet: `followup_required = NO`.

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
