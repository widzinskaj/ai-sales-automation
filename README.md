# AI Sales Automation

A Python-based sales automation system for small and medium service businesses.

Leads arrive via **Meta Instant Forms** (manually exported to Google Sheets).
The system sends an immediate Polish auto-reply email and, after 3 days without
response, flags the lead for human follow-up. No AI, no database, no black-box
platforms.

---

## Why this project exists

Many sales processes fail not because of a lack of AI, but because of:
- fragmented communication channels,
- unclear data ownership,
- manual and error-prone first responses,
- missing structure for future automation.

Before adding intelligence, sales operations need a **reliable, auditable,
and privacy-conscious automation layer**.

This project provides exactly that layer.

---

## Stage 0: What it does

Stage 0 is the foundation layer — **functional and tested**.

**Auto-reply workflow** (`python -m src.stage0.process`):
- Scans Google Sheets for new leads (email non-empty AND `auto_email_sent_at` empty).
- Sends a Polish auto-reply email via SMTP:
  - greeting is personalised with the Polish vocative case via morfeusz2:
    `"Dzień dobry, Anno,"` / `"Dzień dobry, Marku,"`. When the vocative
    cannot be derived (company name, unknown word, or morfeusz2 unavailable)
    the system falls back silently to `"Dzień dobry,"`.
  - attaches 3 fixed PDF files.
  - includes a configurable calendar booking link (static, from `.env`).
- On success: writes `auto_email_sent_at` (Europe/Warsaw, `YYYY-MM-DD HH:MM`), sets `auto_email_status = SENT`.
- On SMTP failure: writes `auto_email_status = ERROR: <description>`, does NOT set `auto_email_sent_at` — lead remains retryable on next run.
- Idempotent: rerunning does not resend emails.

**Follow-up workflow** (`python -m src.workflows.stage0.mark_followups`):
- Marks `followup_required = YES` for leads where 3+ days passed since auto-reply.
- Human reminder only — no automatic follow-up email is sent.

**What Stage 0 does NOT do:**
- No AI / ML / LLM involvement.
- No Meta API integration (leads are manually exported to Sheets).
- No database — Google Sheets is the only datastore.
- No automatic follow-up emails.
- No pricing, quotes, or automated decisions.

---

## Google Sheets schema (key columns)

| Column | Description |
|---|---|
| `email` | Lead email address |
| `Imię i nazwisko / Firma` | Lead full name or company (used for greeting) |
| `auto_email_sent_at` | Timestamp of sent auto-reply (Europe/Warsaw) |
| `auto_email_status` | `SENT` or `ERROR: <description>` |
| `followup_due_at` | Date when follow-up becomes due |
| `followup_required` | `YES` / `NO` |

Full specification: [`docs/stage0.md`](docs/stage0.md).

---

## Repository layout

```
src/
  core/
    config.py         .env loader, typed settings
    lead_helpers.py   Pure functions: new-lead detection, dates, vocative, generate_vocative
  email/
    template_stage0.py  EmailDraft dataclass + build_stage0_email (Polish body template)
    attachments_stage0.py  Load 3 PDFs from env vars
  integrations/
    email_sender.py   send_email_draft — SMTP/STARTTLS, sends EmailDraft
  stage0/
    process.py        process_new_leads orchestration + main() entrypoint
  storage/
    sheets.py         SheetsClient — column-name-based read/write, two-tab architecture
  workflows/
    stage0/
      mark_followups.py  Flag leads awaiting follow-up
tests/                Test suite (pytest)
```

---

## Testing

```bash
pytest                            # run all tests
pytest tests/test_foo.py -k name  # run a single test by name
```

Test modules:
- `tests/test_lead_helpers.py` — new-lead detection, Warsaw dates, follow-up logic, vocative inflection, `generate_vocative`.
- `tests/test_email_sender.py` — `send_email_draft` (SMTP mocked).
- `tests/test_email_template_stage0.py` — email template, attachments loader, greeting integration.
- `tests/stage0/test_process.py` — `process_new_leads` orchestration (send success/failure/idempotency).

---

## Technology

- **Python 3.11+**
- **Google Sheets API** — sole datastore / status board (`gspread`, `google-auth`)
- **SMTP** — outbound email delivery only
- **morfeusz2** — Polish morphological dictionary for vocative-case greeting personalisation (not AI).
  Loaded lazily on first use; if unavailable the system falls back to `"Dzień dobry,"` without crashing.
- **tzdata** — required on Windows for `Europe/Warsaw` timezone (`zoneinfo`)
- **pytest** — test framework

---

## Quickstart

```bash
# 1. Clone and set up
git clone <repo-url> && cd ai-sales-automation
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB_INPUT, GOOGLE_SHEET_TAB_STATUS,
# SMTP_*, CALENDAR_URL, SMTP_FROM_EMAIL/NAME, STAGE0_PDF_1/2/3

# 3. Add Google Cloud service account key
# Place the JSON key file at the path set in GOOGLE_SERVICE_ACCOUNT_JSON
# (secrets/ is gitignored — never commit credentials)

# 4. Add PDF attachments
# Place 3 PDF files and set STAGE0_PDF_1/2/3 in .env
# (assets/attachments/ is gitignored)

# 5. Process new leads (send auto-reply emails)
python -m src.stage0.process

# 6. Mark leads awaiting follow-up (3+ days since auto-reply)
python -m src.workflows.stage0.mark_followups
```

See [`docs/stage0.md`](docs/stage0.md) for the full binding specification.

---

## Architecture principles

- **Automation-first, AI-second** — workflows and data boundaries before intelligence.
- **Stage-based evolution** — each stage delivers independent business value.
- **Privacy by design (GDPR / RODO)** — minimal data processing, clear purposes, easy deletion.
- **Human-in-the-loop by default** — no automated pricing, offers, or decisions.
- **No vendor lock-in** — no black-box platforms.

---

## Project stages

| Stage | Focus | Status |
|---|---|---|
| **0 — Foundation** | Auto-reply, follow-up flags, no AI | Functional, tested |
| 1 — Structured automation | Categorization, contact history, prioritization | Planned |
| 2 — AI-assisted support | Draft responses, extraction, human-reviewed | Planned |
| 3 — Advanced (optional) | Analytics, optimization | Planned |

---

## What this project IS NOT

- a CRM system
- a chatbot or autonomous AI agent
- a repository containing real customer data or credentials

---

## Privacy and data handling

This repository contains **no real customer data** and **no production secrets**.

All sensitive information is provided externally via environment variables and is
never committed to version control. Customer data lives only in Google Sheets and
is not copied elsewhere except transiently during email sending.

---

## Status

Stage 0 is **functional and tested**. The project is under active development.
