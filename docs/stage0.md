# Stage 0 — Foundation (Binding Scope)

Stage 0 delivers the minimum viable automation layer with **zero AI involvement**.
Its only job is to reliably respond to incoming leads and flag stale ones.

---

## Lead Source

Leads arrive in a **Google Sheets spreadsheet** via the native
**Meta Instant Forms → Google Sheets** integration. The system reads this
sheet — it never calls the Meta API directly.

### Expected sheet columns

| Column | Type | Written by | Description |
|---|---|---|---|
| `lead_id` | string | Meta | Unique lead identifier from Meta Instant Forms |
| `created_at` | ISO 8601 datetime | Meta | Timestamp when the lead was captured |
| `full_name` | string | Meta | Lead's full name |
| `email` | string | Meta | Lead's email address |
| `phone` | string | Meta | Phone number (optional) |
| `campaign` | string | Meta | Campaign or ad set name |
| `message` | string | Meta | Free-text from the form (optional). Stored but ignored by Stage 0 logic. |
| `sales_note` | string | Human | Manual note / qualification by salesperson. Never overwritten by the system. |
| `auto_email_sent_at` | ISO 8601 datetime | System | Timestamp when auto-reply was sent |
| `auto_email_status` | string | System | `OK` or `ERROR: <short description>` |
| `followup_due_at` | ISO 8601 datetime | System | Computed as `auto_email_sent_at + 3 days` |
| `followup_required` | boolean | System | Set to `TRUE` when `followup_due_at` has passed |

### Idempotency

The system uses `auto_email_sent_at` as the single source of truth for whether
a lead has been processed. A row is picked up only if `auto_email_sent_at` is
empty. Re-running the workflow is safe — already-processed rows are skipped.

---

## Workflow

```
Google Sheets (new row via Meta Instant Forms integration)
        │
        ▼
  python -m workflows.stage0.run_once
  Read rows where auto_email_sent_at is empty
        │
        ▼
  Send auto-reply email
  ├── 3 fixed PDF attachments
  └── calendar booking link
        │
        ▼
  Update row: set auto_email_sent_at, auto_email_status,
              compute followup_due_at (sent_at + 3 days)
        │
        ▼
  python -m workflows.stage0.mark_followups
  Check rows where followup_due_at has passed
  and followup_required is not TRUE
        │
        ▼
  Update row: set followup_required → TRUE
```

**No follow-up email is sent.** The flag is informational — a human decides
what to do next.

---

## Outbound Email

Each auto-reply contains:

1. A short, fixed plain-text/HTML body (no dynamic content beyond the lead's name).
2. Three PDF attachments stored locally in a configurable directory (e.g. `assets/`).
3. A calendar booking link from the `CALENDAR_LINK` environment variable.

The system uses SMTP for sending. No inbound email parsing.

---

## What Stage 0 Explicitly Excludes

- Meta (Facebook) API integration
- Any database (SQLite, PostgreSQL, etc.)
- AI / ML / LLM of any kind
- Inbound email parsing
- Automated follow-up emails
- Pricing, offers, or dynamic content generation
- Multi-channel ingestion

---

## Privacy

- This repository contains **no real customer data** and **no production credentials**.
- All secrets (SMTP credentials, Google Sheets service account) are provided
  via environment variables or files listed in `.gitignore`.
- Customer data lives only in Google Sheets. The system reads it transiently to send
  an email and writes back only status metadata.
- Data can be inspected and deleted directly in the spreadsheet at any time (GDPR/RODO).

---

## Running Locally

> Prerequisites: Python 3.11+, a Google Cloud service account with Sheets API access,
> SMTP credentials for an outbound email account.

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
# Fill in SMTP_*, CALENDAR_LINK, and Google Sheets credentials

# 5. Place PDF attachments
# Put the 3 PDF files in assets/ (path is configurable)

# 6. Process new leads and send auto-replies
python -m workflows.stage0.run_once

# 7. Mark leads that need follow-up (3 days without action)
python -m workflows.stage0.mark_followups
```
