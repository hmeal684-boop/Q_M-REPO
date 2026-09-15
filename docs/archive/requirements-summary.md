# Requirements Summary

## Status and Authority

- **System:** Q&M AI-Powered Enquiry & Enrollment System
- **Archived requirements draft:** [requirements.md](requirements.md), version 1.1 dated 2026-09-11
- **Status:** Draft updated after supervisor clarification; Q&M baseline approval remains pending

The complete requirements file is the source of truth. This summary is a navigation aid and does not replace its acceptance criteria, constraints or unresolved-question register.

## Confirmed Working Direction

- Flask provides the initial conversational web prototype.
- CrewAI coordinates an Intent Classification Agent and the FAQ/Enquiry, Enrollment and Payment Verification specialist agents.
- Natural-language conversation is the main participant interaction. Slash commands are optional testing shortcuts only.
- Modules A and B use database-backed memory across messages, process restarts and previous days within the eventual approved retention window.
- Conversational enrollment collects course, full name, NRIC, DOB, email and preferred intake date, validates them, displays a confirmation summary and stores only the participant-confirmed enrollment.
- NRIC and DOB are collected only after enrollment starts and the approved privacy prerequisites are satisfied.
- The initial MVP supports the 2-Day Basic Certificate in Dental Assisting. Course/intake/content/financial records must support later courses without redesigning the core schema or workflow.
- Payment screenshots are accepted through WhatsApp and email subject to platform limits, with no extra business submission quotas.
- Mismatched or unreadable screenshots always require staff review and never automatically establish Paid status.
- A verified WhatsApp sender association is sufficient for normal status, invoice and receipt requests; no additional OTP or participant login is required.
- The exact language and vision models remain configurable.

## Target Capability by Module

| Module | Required capability |
|---|---|
| Shared workflow | Authenticate/normalize inbound events, classify intent, route through CrewAI, persist context and handle ambiguity safely |
| Module A | Approved FAQ/course/funding answers, quick replies, lead context, follow-ups and human escalation |
| Module B | Guided six-field enrollment, deterministic validation, confirmation/storage, invoices, email instructions and status tracking |
| Module C | WhatsApp/email evidence intake, AI-assisted extraction/comparison, approved automatic matches, mandatory exception review, payments, receipts and accounting workflows |
| Staff functions | Operations dashboard, escalation/content work, Accountant portal, reports, receipt actions and credit-note approval |
| Delivery/operations | Security and privacy controls, deployment, monitoring, backup/restore, documentation, training, handover and support evidence |

## Initial Flask Prototype Boundary

The prototype demonstrates the conversational channel, CrewAI routing contracts, persistent Module A/B context and enrollment flow using synthetic data. It is not production WhatsApp acceptance and must not use real personal data, official fees/intakes or financial templates until Q&M supplies and approves them.

## Explicit Exclusions

- Direct Singpass or SkillsFuture API access and automated personal claim submission
- Bank/payment-gateway integration or automated funds movement
- Integration with Q&M's existing accounting systems
- Native participant mobile applications or a mandatory participant enrollment form
- Clinical advice, job guarantees, LMS/course delivery and unsupported payment methods
- Additional live courses in the initial release

## Pending Q&M Inputs

Q01–Q17 remain open in the [requirements register](requirements.md#unresolved-questions). They cover official course/intake content, validation and duplicate rules, fees/funding, escalation/reminder operation, financial and message templates, email/evidence intake, payment/reconciliation/credit-note policies, privacy/retention/masking, staff access, reporting, service targets, KPI evidence, infrastructure, ownership/training/support and UI/accessibility profiles.

All unresolved values are **TBD - Pending Q&M confirmation**. No course fee, live date, Q&M template, credential, retention period, payment threshold or legal policy may be inferred from proposal examples.
