# AI Sales Automation – Stage 0

## Overview

Automated first-touch email handling for inbound leads from Meta Instant Forms.
Leads land in Google Sheets (manually exported from Meta); the system sends an
immediate Polish auto-reply email and flags leads for human follow-up after 3 days.

Design constraints:
- **Deterministic and idempotent** — safe to run multiple times per day.
- **Google Sheets as the only datastore** — no database, no CRM, no external queue.
- **No AI, no ML** — every decision is a rule that can be read and audited.
- **Privacy by design (GDPR / RODO)** — minimal data processing, no PII in logs.

---

## Deployment Model

Stage 0 runs on a **dedicated client host** (a Windows machine or server) managed by a
**technical operator**. The business user has no access to the host, repository, code,
`.env` file, or secrets.

| Role | Responsibilities |
|---|---|
| **Technical operator** | Deploy the repository, configure `.env`, set up the scheduler, monitor logs, apply updates, handle incidents. |
| **Business user** | Work exclusively in Google Sheets — review the status tab and mark follow-ups complete. |

**What the business user never touches:**
- The host machine or its file system.
- The repository or any code.
- The `.env` file or any secrets.
- SMTP credentials or the Google service account.

**Runtime boundary:** The scheduler, the Python process, and all credentials live on
the client host. Google Sheets is the only interface the business user interacts with.

---

## Architecture

```
Scheduler (Task Scheduler / cron — runs on client host)
    |
    v
run_stage0_job()                       src/stage0/job.py
    |
    +-- load config                    src/core/config.py
    |
    +-- SheetsClient                   src/storage/sheets.py
    |     +-- ensure_status_rows_exist()
    |     +-- get_new_leads()
    |           +-- is_eligible_for_send()   new lead | ERROR + no sent_at
    |
    +-- resolve_recipient_email()      src/stage0/test_mode.py
    |     +-- test mode hard lock
    |
    +-- send_email_draft()             src/integrations/email_sender.py
    |     +-- SMTP / STARTTLS
    |
    +-- SheetsClient.update_row()      write sent_at + status
    |
    +-- log summary (no PII)

Domain logic (pure, no I/O):
    src/stage0/followup.py             apply_followup_logic()
    src/core/lead_helpers.py           is_new_lead(), followup helpers
```

Module responsibilities:

| Module | Responsibility |
|---|---|
| `src/stage0/job.py` | Scheduler entrypoint — config load, SheetsClient init, orchestration, logging |
| `src/stage0/process.py` | Core pipeline — loop over leads, build draft, send, update status |
| `src/stage0/test_mode.py` | Recipient resolver — hard guard against sending to real addresses in test mode |
| `src/stage0/followup.py` | Follow-up scheduling domain logic — pure functions, idempotent |
| `src/storage/sheets.py` | SheetsClient — column-name-based read/write, eligibility predicate |
| `src/core/config.py` | Environment loader — typed settings, lazy import pattern |
| `src/integrations/email_sender.py` | SMTP sender — EmailDraft over STARTTLS |
| `src/email/template_stage0.py` | Email template builder — static Polish body + 3 PDF attachments |
| `src/core/lead_helpers.py` | Pure helpers — date arithmetic, follow-up predicates |

---

## Operational Flow

1. **Load config** — env vars validated at startup; missing required vars raise immediately.
2. **Sync status rows** — `ensure_status_rows_exist()` creates an empty status row for every
   input email that does not have one yet. Idempotent.
3. **Fetch eligible leads** — `get_new_leads()` returns leads that pass `is_eligible_for_send()`:
   - no status row, or
   - status row with `Status emaila == "ERROR"` and `Email wysłany` empty.
   Leads with `Email wysłany` set are never retried regardless of status.
4. **Resolve recipient** — `resolve_recipient_email()` enforces the test mode guard before
   the address reaches the SMTP layer (see [Test Mode](#test-mode)).
5. **Send email** — `send_email_draft()` delivers via SMTP/STARTTLS with 3 fixed PDF
   attachments and a calendar booking link.
6. **Update status** —
   - Success: writes `Email wysłany` (Europe/Warsaw, `YYYY-MM-DD HH:MM`) and
     `Status emaila = SENT`.
   - Failure: writes a user-friendly `Status emaila` value starting with `ERROR:`,
     e.g. `ERROR: OCZEKUJE NA PONOWIENIE: limit wysyłki SMTP` for SMTP rate limits,
     `ERROR: WYMAGA DZIAŁANIA: wiadomość przekracza limit rozmiaru` for oversized
     messages, or `ERROR: <raw message>` for other technical failures. `Email wysłany`
     is intentionally left empty so the lead remains eligible for retry.
7. **Log summary** — `run_stage0_job()` logs `scanned / new / sent / failed` counters
   after the loop. No email addresses or names appear in logs.

---

## Test Mode

Test mode redirects all outbound emails to a single internal address, making it safe
to run the full pipeline against the production sheet without contacting real leads.

| Variable | Description |
|---|---|
| `STAGE0_TEST_MODE` | Set to `1` to enable. Default `0`. |
| `TEST_RECIPIENT_EMAIL` | Required when `STAGE0_TEST_MODE=1`. All emails go here. |

Behaviour:
- `run_stage0_job()` checks the flag before any I/O and raises `RuntimeError` immediately
  if `STAGE0_TEST_MODE=1` and `TEST_RECIPIENT_EMAIL` is missing or blank.
- `resolve_recipient_email()` replaces `to_email` with `TEST_RECIPIENT_EMAIL` in every
  call to `send_email_draft()`. The lead's real address never reaches the SMTP layer.
- Logs record `"TEST MODE active"` but do not log the test recipient address.
- Status writes (`Email wysłany`, `Status emaila`) still happen against the real
  sheet, so test runs are fully observable without sending to real recipients.

---

## Safety Guarantees

- **Idempotent execution** — running the job multiple times in a row produces no duplicate
  sends. Once `Email wysłany` is set the lead is never re-processed.
- **Retry only on unconfirmed failure** — a lead with `Status emaila` starting with
  `ERROR:` and an empty `Email wysłany` is re-attempted. A lead with `Email wysłany`
  set is never retried, regardless of the status value.
- **No duplicate sends** — `Email wysłany` is written only after a confirmed SMTP
  delivery. A process crash between send and write leaves the lead retryable, not silently
  dropped.
- **No PII in logs** — lead email addresses, names, and phone numbers do not appear in any
  log line produced by this codebase.
- **Test mode hard lock** — `resolve_recipient_email()` makes it structurally impossible
  to reach a real lead address while `STAGE0_TEST_MODE=1`. The guard lives in the single
  send path and cannot be bypassed by callers.

---

## Google Sheets Schema

### automation_stage0_input (read-only)

Populated externally by Meta Instant Forms export. Not written by this application.

| Column | Type | Description |
|---|---|---|
| `Imię i nazwisko / Firma` | string | Lead full name or company |
| `Email` | string | Lead email address (normalised to lowercase) |
| `Telefon dodatkowy` | string | Additional phone number (not processed) |

### automation_stage0_status (read-write)

Managed by the application. `Lead` and `Email` are set at row creation and never
overwritten. The remaining columns are system-managed. `Follow-up wykonany` is
filled manually by the sales team.

| Column | Type | Description |
|---|---|---|
| `Lead` | string | Lead full name or company (copied from input tab at row creation) |
| `Email` | string | Lead email (logical key, normalised to lowercase) |
| `Email wysłany` | datetime | Timestamp of confirmed delivery (`YYYY-MM-DD HH:MM`, Europe/Warsaw) |
| `Status emaila` | string | `SENT` \| `ERROR: OCZEKUJE NA PONOWIENIE: limit wysyłki SMTP` \| `ERROR: WYMAGA DZIAŁANIA: wiadomość przekracza limit rozmiaru` \| `ERROR: <message>` \| empty |
| `Follow-up od` | datetime | When follow-up becomes due (Email wysłany + 3 days) |
| `Wymaga follow-upu` | string | `YES` \| `NO` |
| `Follow-up wykonany` | datetime | Timestamp when follow-up was marked done (written by sales team) |

**Status transitions:**

```
[new lead] --> Email wysłany="", Status emaila=""
    |
    +-- send OK  --> Email wysłany=<ts>, Status emaila="SENT"
    |                    |
    |                    +--> Follow-up od=<ts+3d>, Wymaga follow-upu="NO"
    |                    |                    (scheduled, not yet due)
    |                    |
    |                    +--> [3 days pass] --> Wymaga follow-upu="YES"
    |                    |                    (now >= Follow-up od)
    |                    |
    |                    +--> [human follows up] --> Follow-up wykonany=<ts>,
    |                                                Wymaga follow-upu="NO"
    |
    +-- send ERR --> Status emaila="ERROR: OCZEKUJE NA PONOWIENIE: limit wysyłki SMTP"
    |               (or "ERROR: WYMAGA DZIAŁANIA: ..." / "ERROR: <msg>")
    |               Email wysłany=""  → eligible for retry
```

---

## Setup (Technical Operator)

These steps are performed by the technical operator during initial deployment.
The business user is not involved in any of these steps.

### Prerequisites

```bash
git clone <repo-url> && cd ai-sales-automation
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

### Required ENV

Copy `.env.example` to `.env` and fill in all values.

```
# Google Sheets
GOOGLE_SHEET_ID=
GOOGLE_SHEET_TAB_INPUT=automation_stage0_input
GOOGLE_SHEET_TAB_STATUS=automation_stage0_status
GOOGLE_SERVICE_ACCOUNT_JSON=secrets/service_account.json

# SMTP
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=

# Runtime
CALENDAR_URL=
STAGE0_PDF_1=assets/attachments/a.pdf
STAGE0_PDF_2=assets/attachments/b.pdf
STAGE0_PDF_3=assets/attachments/c.pdf

# Test mode (set to 1 for local testing)
STAGE0_TEST_MODE=0
TEST_RECIPIENT_EMAIL=
```

Place the Google Cloud service account JSON at the path configured in
`GOOGLE_SERVICE_ACCOUNT_JSON`. The `secrets/` directory is gitignored.

Place the 3 PDF attachments at the paths configured in `STAGE0_PDF_1/2/3`.
The `assets/attachments/` directory is gitignored.

### Run the job

```bash
# Test mode — sends only to TEST_RECIPIENT_EMAIL (use before any production run)
STAGE0_TEST_MODE=1 TEST_RECIPIENT_EMAIL=operator@example.com python -m src.stage0.job

# Production mode — sends to real leads
python -m src.stage0.job
```

### Run tests

```bash
pytest                          # full suite
pytest tests/stage0/ -q         # stage 0 only
pytest -k test_idempotent -q    # single scenario
```

---

## Scheduler Integration

The scheduler target is the command `python -m src.stage0.job`. This invokes
`run_stage0_job()` internally — that function is not a public API.

- Safe to run multiple times per day — idempotent by design.
- Each invocation processes only leads that have not yet received an email.
- Recommended schedule: every 15–60 minutes, depending on lead volume.

### Recommended deployment for this project

The intended deployment is a **dedicated client host** running Windows Task Scheduler.
The wrapper script `scripts\run_stage0_job.cmd` is invoked by the task; log output
accumulates in `logs\stage0_scheduler.log`. Full Task Scheduler setup instructions
are in **[RUNBOOK.md § 14](RUNBOOK.md#14-windows-task-scheduler-setup)**.

**The scheduler is enabled only after a successful manual production run** (see
[Production Considerations](#production-considerations) below). This ensures
credentials, Sheets access, and SMTP are verified before automated sends begin.

### Alternative schedulers

External cron (Linux):
```
*/30 * * * * cd /app && .venv/bin/python -m src.stage0.job >> /var/log/stage0.log 2>&1
```

Cloud schedulers (GCP Cloud Scheduler, AWS EventBridge, etc.) can invoke the same
command. No persistent process or message queue is required.

---

## Production Considerations

### Switching from test to production

1. **Replace Sheet ID** — set `GOOGLE_SHEET_ID` to the production spreadsheet.
   Verify that `GOOGLE_SHEET_TAB_INPUT` and `GOOGLE_SHEET_TAB_STATUS` match the
   exact tab names in the production sheet.
2. **Verify service account access** — the service account needs `Sheets Editor` access
   on the production spreadsheet. `Viewer` access is not sufficient.
3. **Run one cycle in test mode against the production sheet** — set `STAGE0_TEST_MODE=1`
   and `TEST_RECIPIENT_EMAIL` to an internal address, then run `python -m src.stage0.job`.
   Confirm the status tab received rows and the test inbox received emails. This verifies
   Sheets access and SMTP without contacting real leads.

### First manual production run

Before enabling the scheduler, run the job once manually in production mode:

```bash
# Ensure STAGE0_TEST_MODE=0 (or unset) in .env
python -m src.stage0.job
```

Confirm:
- Log shows `Stage0 job complete — scanned=N new=M sent=M failed=0`.
- Status tab shows `Status emaila = SENT` and `Email wysłany` filled for each
  processed lead.
- No `ERROR:` entries in `Status emaila`.

Enable the scheduler only after this run completes without errors.

### First 48 hours

After the scheduler is enabled, monitor the following at least twice daily:

- `logs\stage0_scheduler.log` — confirm repeating `job start` / `job complete` pairs at
  the configured interval. No gaps longer than two intervals indicate a missed run.
- `Status emaila` column in the status tab — any `ERROR:` value requires investigation.
  The affected lead remains retryable; fix the root cause before the next cycle.
- `failed` counter in log summary — a non-zero value on any run is an alert condition.
- SMTP rate limits — confirm the sending account has not been throttled or suspended.

### Ongoing operations

- **Monitor logs** — watch for `ERROR:` values in `Status emaila`. Each error
  leaves the lead retryable (provided `Email wysłany` is empty). Interpretation:
  - `ERROR: OCZEKUJE NA PONOWIENIE:` — temporary SMTP rate limit; the system will
    retry automatically on the next run.
  - `ERROR: WYMAGA DZIAŁANIA:` — operator must act (e.g. reduce PDF size) before
    retry can succeed.
  - Other `ERROR:` — technical failure; inspect the raw message in the log for details.
- **Rollback strategy** — the status sheet is the source of truth. To reset a lead,
  clear `Email wysłany` and `Status emaila` in the status tab. The next
  run will re-process it. Do not modify the input tab.

---

## Runbook

Step-by-step operational instructions (preconditions, env vars, scheduler setup,
status field reference, troubleshooting, safe change procedure, emergency stop):

**[RUNBOOK.md](RUNBOOK.md)**

---

## Repository Layout

```
src/
  core/
    config.py                 .env loader, typed settings
    lead_helpers.py           Pure functions: date arithmetic, follow-up predicates
  email/
    template_stage0.py        EmailDraft builder (Polish body + attachments)
    attachments_stage0.py     Load 3 PDFs from env vars
  integrations/
    email_sender.py           send_email_draft — SMTP/STARTTLS
  stage0/
    job.py                    Scheduler entrypoint — run_stage0_job()
    process.py                Core pipeline — process_new_leads()
    test_mode.py              Recipient resolver — resolve_recipient_email()
    followup.py               Follow-up domain logic — apply_followup_logic()
  storage/
    sheets.py                 SheetsClient, is_eligible_for_send()
tests/
  test_lead_helpers.py        Date helpers, follow-up predicates
  test_email_sender.py        SMTP send path (mocked)
  test_email_template_stage0.py  Template builder, attachment loader
  test_followup_logic.py      apply_followup_logic() domain rules
  stage0/
    test_process.py           process_new_leads() orchestration
    test_retry_logic.py       is_eligible_for_send(), retry scenarios
    test_test_mode.py         resolve_recipient_email(), test mode pipeline
    test_job_entrypoint.py    run_stage0_job() idempotency, logging
```

---

## Technology

- **Python 3.11+**
- **gspread + google-auth** — Google Sheets API access
- **SMTP / STARTTLS** — outbound email only, no inbound parsing
- **tzdata** — required on Windows for `zoneinfo` with `Europe/Warsaw`
- **pytest** — test framework
- **python-dotenv** — `.env` loader

No external services, no message queues, no runtime AI dependencies.
