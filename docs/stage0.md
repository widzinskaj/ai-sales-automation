# Stage 0 — Foundation (Binding Scope)

Stage 0 delivers the minimum viable automation layer with **zero AI involvement**.
Its only job is to reliably respond to incoming leads and flag stale ones for human
follow-up.

This document describes the production-ready Stage 0 scope. For operational procedures
see [RUNBOOK.md](../RUNBOOK.md). For architecture and module details see
[README.md](../README.md).

---

## Deployment Model

Stage 0 runs on a **dedicated client host** managed by a **technical operator**.

| Role | Responsibilities |
|---|---|
| **Technical operator** | Deploy the runtime, configure `.env`, maintain the scheduler, monitor logs, handle incidents. |
| **Business user** | Work exclusively in Google Sheets — review lead status and mark follow-ups complete. |

The business user has no access to the host, repository, code, `.env` file, or secrets.
Google Sheets is the only interface they use.

---

## Lead Source

Leads arrive in a **Google Sheets spreadsheet** after a manual export from
**Meta Lead Ads**. The system reads this sheet — it never calls the Meta API directly.

### Google Sheets schema

The spreadsheet uses two tabs.

#### automation_stage0_input (read-only)

Populated externally by manual Meta Lead Ads export. Not written by this application.

| Column | Type | Description |
|---|---|---|
| `Imię i nazwisko / Firma` | string | Lead full name or company |
| `Email` | string | Lead email address |
| `Telefon dodatkowy` | string | Additional phone number (not processed) |

#### automation_stage0_status (read-write)

Managed by the application. Only system-controlled columns are written. The
`followup_completed_at` column is filled manually by the sales team.

| Column | Type | Description |
|---|---|---|
| `email` | string | Lead email (key, normalised to lowercase) |
| `auto_email_sent_at` | datetime | Timestamp of confirmed delivery (`YYYY-MM-DD HH:MM`, Europe/Warsaw) |
| `auto_email_status` | string | `SENT` \| `ERROR: <message>` \| empty |
| `followup_due_at` | datetime | When follow-up becomes due (sent_at + 3 days) |
| `followup_required` | string | `YES` \| `NO` |
| `followup_completed_at` | datetime | Timestamp when follow-up was marked done (written by sales team) |

### Idempotency

The system uses `auto_email_sent_at` as the single source of truth for whether
a lead has been processed. A row is picked up only if `auto_email_sent_at` is
empty. Re-running the workflow is safe — already-processed rows are skipped without
any side effects.

---

## Workflow

```
Google Sheets (new lead row added by manual Meta Lead Ads export)
        │
        ▼
  python -m src.stage0.job
  ├── Read rows where auto_email_sent_at is empty
  │         │
  │         ▼
  │   Send auto-reply email
  │   ├── 3 fixed PDF attachments
  │   └── calendar booking link (CALENDAR_URL — static, no Calendar API)
  │         │
  │         ▼
  │   Update row: set auto_email_sent_at, auto_email_status,
  │               compute followup_due_at (sent_at + 3 days),
  │               followup_required = NO
  │
  └── Check rows where followup_due_at has passed
              │
              ▼
        Update row: set followup_required → YES
```

**No follow-up email is sent.** The flag is informational — the sales team decides
what to do next.

---

## Outbound Email

Each auto-reply contains:

1. A short, fixed plain-text body in Polish (no dynamic content beyond the lead's name).
2. Three PDF attachments stored locally in `assets/attachments/`.
3. A calendar booking link from the `CALENDAR_URL` environment variable.

Stage 0 does not integrate with any Calendar API. `CALENDAR_URL` is a static link
configured in `.env`.

The system uses SMTP/STARTTLS for sending. No inbound email parsing.

---

## Test Mode

Test mode redirects all outbound emails to a single internal address, making it safe
to run the full pipeline against the production sheet without contacting real leads.

`STAGE0_TEST_MODE=1` must be set during all development, testing, and pre-production
verification. It is a required safeguard, not an optional feature.

| Variable | Description |
|---|---|
| `STAGE0_TEST_MODE` | `1` = test mode active, `0` = production mode. |
| `TEST_RECIPIENT_EMAIL` | Required when `STAGE0_TEST_MODE=1`. All emails are delivered here instead of to real leads. |

When test mode is active, the system still writes to the real status sheet — so test runs
are fully observable without any risk to real recipients.

---

## What Stage 0 Explicitly Excludes

- Meta (Facebook) API integration
- Any database (SQLite, PostgreSQL, etc.)
- AI / ML / LLM of any kind
- Inbound email parsing
- Automated follow-up emails
- Pricing, offers, or dynamic content generation
- Multi-channel ingestion
- CRM integration

---

## Privacy

- This repository contains **no real customer data** and **no production credentials**.
- All secrets (SMTP credentials, Google Sheets service account) are provided
  via environment variables or files listed in `.gitignore`.
- Customer data lives only in Google Sheets. The system reads it transiently to send
  an email and writes back only status metadata.
- No PII (names, emails, phone numbers) appears in any log line.
- Data can be inspected and deleted directly in the spreadsheet at any time (GDPR/RODO).

---

## Running the Job (Technical Operator)

These steps are performed by the technical operator. The business user is not involved.

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd ai-sales-automation

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Fill in SMTP_*, CALENDAR_URL, and Google Sheets credentials

# 5. Place PDF attachments
# Put the 3 PDF files in assets/attachments/

# 6. Run in test mode first (mandatory before any production run)
# Set STAGE0_TEST_MODE=1 and TEST_RECIPIENT_EMAIL in .env, then:
python -m src.stage0.job

# 7. Run in production mode after test mode verification
# Set STAGE0_TEST_MODE=0 in .env, then:
python -m src.stage0.job
```

Full setup, scheduler configuration, and operational procedures:
**[RUNBOOK.md](../RUNBOOK.md)**
