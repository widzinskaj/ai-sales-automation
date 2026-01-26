# AI Sales Automation

Privacy-first, Python-based sales automation framework for small service businesses.

This project focuses on automating the **first response to customer inquiries**
while keeping humans in control and respecting data protection principles
(GDPR / RODO).

## Project goal

The main goal is to reduce manual work in the first stage of sales by:
- collecting inquiries from multiple sources in one place,
- sending immediate, professional auto-replies,
- preparing the ground for scheduling meetings,
- without automating pricing or decision-making.

## What this project IS

- a modular, Python-first automation framework
- designed for real business use, not demos
- privacy-first by design (data minimization, easy deletion)
- suitable for gradual, stage-based development
- portfolio-grade architecture

## What this project IS NOT

- a CRM system
- a fully autonomous AI sales agent
- a system that generates prices or binding offers
- a repository containing real client data or credentials

## Privacy-first approach

This repository contains:
- core logic
- data models
- example workflows
- example configuration

It does NOT contain:
- real customer data
- production credentials
- email inboxes
- calendar accounts

All sensitive data is expected to be provided via environment variables
or external configuration and never committed to the repository.

## Project stages

- **Stage 0** – Lead intake, minimal storage, auto-reply, calendar link  
- **Stage 1** – Lead categorization, follow-ups, contact history  
- **Stage 2** – AI-assisted draft responses (human-approved)  
- **Stage 3** – Advanced automation and analytics (optional)

Only Stage 0 is implemented as the initial foundation.
Further stages are intentionally planned, not rushed.

## Tech stack (initial)

- Python 3.11+
- Pydantic
- SQLite or Google Sheets (as simple storage options)
- SMTP / email API for notifications

## Status

This project is under active, iterative development.
