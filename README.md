# AI Sales Automation

A Python-based foundation for building end-to-end sales automation systems
for small and medium service businesses.

This project is designed as a **modular skeleton** for automated customer handling,
covering the full journey from first inquiry to follow-ups and sales support.
Artificial Intelligence is introduced gradually and deliberately — not by default.

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

## Core idea

**ai-sales-automation is not an AI assistant.**

It is a **system-level foundation** that:
- defines how data enters the system,
- orchestrates sales-related workflows,
- enforces privacy and human oversight,
- enables safe introduction of AI at later stages.

AI is treated as an **optional capability**, not as the core of the system.

---

## Architecture principles

- **Automation-first, AI-second**  
  Workflows and data boundaries come before intelligence.

- **Stage-based evolution**  
  Each stage delivers independent business value and can be stopped or extended.

- **Privacy by design (GDPR / RODO)**  
  Minimal data processing, clear purposes, easy deletion, no hidden flows.

- **Human-in-the-loop by default**  
  No automated pricing, offers or decisions.

- **Python-first, transparent design**  
  No black-box platforms, no vendor lock-in.

---

## Project stages

### Stage 0 — Foundation (no AI)

Stage 0 delivers the minimum viable automation layer:
- a single, well-defined lead intake channel,
- immediate automated confirmation response,
- lightweight status tracking in the source of truth,
- human-controlled follow-up markers.

The concrete Stage 0 specification (binding scope, data schema, and run commands)
lives in `docs/stage0.md`.

---

### Stage 1 — Structured automation
- structured lead categorization,
- contact history,
- follow-up workflows,
- basic prioritization rules.

AI may be introduced optionally as a helper, not a decision-maker.

---

### Stage 2 — AI-assisted sales support
- AI-generated draft responses,
- information extraction from inquiries,
- always reviewed and approved by a human.

---

### Stage 3 — Advanced automation (optional)
- analytics,
- optimization of workflows,
- extended AI support for internal decision-making.

---

## What this project IS

- a reusable sales automation framework
- a system-level foundation for AI-enabled sales tools
- a privacy-first architecture example
- a real-world, portfolio-grade project

## What this project IS NOT

- a CRM system
- a chatbot
- an autonomous AI sales agent
- a repository containing real customer data or credentials

---

## Privacy and data handling

This repository contains **no real customer data** and **no production secrets**.

All sensitive information is expected to be provided externally via environment
variables or deployment-specific configuration and is never committed to version
control.

The system is designed so that customer data can be:
- minimized by default,
- easily inspected,
- easily removed.

---

## Technology (initial)

- Python 3.11+
- Google Sheets as a lightweight source of truth and status board
- SMTP for outbound email delivery
- Pydantic for data validation

---

## Status

This project is under active, iterative development.
It serves both as a production-ready foundation and as a long-term portfolio project.
