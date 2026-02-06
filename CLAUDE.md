# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python 3.11+ sales automation framework for small/medium service businesses. Currently in **Stage 0** — all directories contain empty `__init__.py` files with no implementation code yet.

Key technologies (Stage 0): Python 3.11+, Pydantic, Google Sheets API, SMTP (outbound only).

## Stage 0 Scope (Binding)

These constraints are hard requirements for Stage 0. Do not introduce anything outside this list.

- **Single lead source**: Google Sheets — populated externally by Meta Lead Ads export. No Meta API integration, no direct form ingestion, no other lead sources.
- **No database**: No SQLite, no PostgreSQL, no local DB. Google Sheets is the only data store.
- **No AI**: Zero AI/ML involvement. No LLM calls, no NLP, no classification models.
- **Outbound email only**: System sends auto-reply to new leads. Email contains exactly 3 fixed PDF attachments + a calendar booking link. No inbound email parsing.
- **Follow-up**: After 3 days without response, the lead row in Google Sheets is marked (flag/status column). No follow-up email is sent automatically.
- **No pricing or offer logic**: No automated decisions, quotes, or dynamic content.
- **Privacy (GDPR/RODO)**: Minimal data processing, clear purposes, easy deletion. No data copied outside Google Sheets except transient email sending.

## Build & Development Commands

No build tooling is configured yet (no `pyproject.toml`, `requirements.txt`, `Makefile`, or CI/CD). These need to be set up as part of Stage 0 implementation.

## Architecture

Layered, domain-driven structure:

- **domain/** — Entity models (leads, inquiries)
- **core/** — Business logic and orchestration
- **api/** — External-facing endpoints
- **storage/** — Google Sheets integration (read/write leads)
- **integrations/** — SMTP email sending, calendar link handling
- **workflows/** — Lead intake auto-reply, 3-day follow-up marking
- **ai/** — Reserved for Stage 2+. Empty in Stage 0.
- **tests/** — Test suite

## Design Principles

- **Automation-first, AI-second**: Workflows and data boundaries before intelligence. AI is optional, not core.
- **Stage-based evolution**: Stage 0 (foundation, no AI) → Stage 1 (structured automation) → Stage 2 (AI-assisted, human-reviewed) → Stage 3 (analytics/optimization).
- **Human-in-the-loop by default**: No automated pricing, offers, or autonomous decisions.
- **Privacy by design (GDPR/RODO)**: Minimal data processing, clear purposes, easy deletion.
- **No vendor lock-in**: No black-box platforms.

## Environment Configuration

Copy `.env.example` to `.env`. Key variables: `APP_ENV`, `EMAIL_PROVIDER`, `SMTP_HOST/PORT/USER/PASSWORD`, `CALENDAR_LINK`, `STORAGE_TYPE`, `STORAGE_PATH`.

Customer data and `.env` files are never committed (excluded via `.gitignore`). Local data lives in `data/` (also gitignored).
