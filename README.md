# Q&M AI-Powered Enquiry & Enrollment System

This repository contains the active requirements baseline and a working
prototype for course enquiries and conversational enrollment. A React/Vite chat
client calls a Flask REST API. Flask controls the workflow, CrewAI coordinates
three OpenAI-backed agents, and SQLAlchemy preserves conversations and enrollment
drafts across reloads and later days.

The course catalogue uses the latest supplied company reply information. Approved
client intake dates remain empty until staff add them. Three fictional prototype
intakes are stored separately and appear only when `ENABLE_DEMO_INTAKES=true`.
Automated tests use only synthetic identities.

## Current Phase

The current implementation includes:

- Intent classification into `faq`, `enrollment`, or `unclear`
- A grounded FAQ/Enquiry Agent using editable company course information
- An Enrollment Agent that collects identity, contact, intake, payment-option,
  SkillsFuture amount, and PayNow amount details
- Deterministic Python validation and explicit confirmation before saving
- An additive enrollment-schema migration that preserves existing records
- Participant registration, login, protected chat, and account-owned conversations
- Role-protected staff operations and finance workspaces
- Course-date management, payment review, private document delivery, and queued integrations
- SQLite locally, with PostgreSQL support through `DATABASE_URL`
- Database-backed history, browser conversation resumption, and a new-conversation action

External email, WhatsApp and payment-vision actions remain disabled until their
server-side credentials are configured. Payment evidence always requires staff
review unless an approved verification policy is explicitly enabled.

## Main Documentation

- [Active Clifton's requirements](docs/requirements/Cliftons-Requirements.md)
- [Original project proposal](docs/source-materials/proposal/QM_AI_Powered_Enquiry_and_Enrollment_System_V2_4.pdf)
- [Spec-Driven Development PDF](docs/source-materials/proposal/SpecDrivenDevelopment.pdf)
- [Company workflow presentation](docs/source-materials/company-workflow/Agentive%20Workflow%20for%20Dental%20Assisting%20Course%20Administration.pptx)
- [Company workflow email](docs/source-materials/company-workflow/FW_%20Agentive%20Workflow%20for%20Dental%20Assisting%20Course%20Administration.eml)
- [Company reply information](docs/source-materials/company-reply-information/2%20days%20DA%20course%20Reply%20Template.docx)
- [Requirements template](docs/templates/requirements-template.md)
- [Design template](docs/templates/design-template.md)
- [Tasks template](docs/templates/tasks-template.md)

Older requirements material is retained under `docs/archive/` and is not the
current source of truth.

## Architecture

```text
React/Vite chat
      |
      v
Flask REST API ----> SQLAlchemy (SQLite or PostgreSQL)
      |
      v
Application router
      |----> CrewAI Intent Classification Agent
      |----> CrewAI FAQ/Enquiry Agent ----> company course information
      `----> CrewAI Enrollment Agent ----> deterministic validator/state machine
```

The OpenAI model is configured through `OPENAI_MODEL`, allowing it to be changed
without modifying application code. CrewAI 1.15.21 supplies the OpenAI provider
adapter used by all three agents.

## Folder Guide

| Path | Purpose |
|---|---|
| `frontend/` | React components, Vite configuration, styles, and REST client |
| `backend/agents/` | CrewAI agent definitions and Pydantic output contracts |
| `backend/services/` | CrewAI execution, persistence, routing, validation, privacy, enrollment, and catalogue services |
| `backend/models/` | SQLAlchemy models |
| `backend/data/` | Editable company course information and ignored local SQLite data/backups |
| `backend/tests/` | Model-free automated tests plus one opt-in live smoke test |
| `docs/` | Current project documentation and archived drafts |

## Backend Setup

From the project root in PowerShell:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
Set-Location ..
python -m flask --app backend.app run --debug --port 5000
```

Fill `OPENAI_API_KEY` only in `backend/.env`. Never put it in a frontend
variable or commit it. Set a private `FLASK_SECRET_KEY` and
`DATA_ENCRYPTION_KEY` outside development. Staff accounts are supplied as JSON
containing Werkzeug password hashes; plaintext staff passwords do not belong in
the file or repository. Optional backend settings are documented in
`backend/.env.example`.

```dotenv
OPENAI_MODEL=
DATABASE_URL=
CONVERSATION_CONTEXT_MESSAGE_LIMIT=20
FLASK_SECRET_KEY=change-me
FLASK_PORT=5000
ENABLE_DEMO_INTAKES=false
```

`ENABLE_DEMO_INTAKES` defaults to `false` and must remain disabled in production.
Set it to `true` only for a local prototype demonstration. The displayed October,
November and December 2026 dates are fictional, are visibly marked as demo dates,
and are not confirmed Q&M course intakes.

An empty `DATABASE_URL` uses `backend/data/qm_chatbot.db`. Production may use a
PostgreSQL URL such as `postgresql://...`; credentials belong only in the ignored
local/hosting environment.

## Frontend Setup

In a second terminal:

```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend uses only:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5000
```

Participants register or sign in at `/`. Staff use `/staff`.

## API Summary

- `POST /api/auth/register`, `/api/auth/login`, and `/api/auth/logout` manage participant sessions.
- `POST /api/conversations` creates a conversation owned by the signed-in participant.
- `GET /api/conversations/<conversation_id>/messages` reloads its masked history.
- `POST /api/chat` accepts `{"conversation_id": "...", "message": "..."}`.
- `/api/staff/*` routes require a configured staff account and enforce role boundaries.
- `GET /health` reports process health without returning configuration or secrets.

The chat response includes `conversation_id`, an assistant `message`, development
`routing` metadata, and non-sensitive enrollment state. NRIC/FIN values are masked
in API-rendered history and confirmation summaries.

Confirmed enrollments are rebuilt into the private
`backend/data/private/Master_Invoice_List.xlsx` export. The directory and all
generated workbooks are Git-ignored and downloads require an accounting/admin
staff session.

## Verification

Normal tests mock the AI boundary, so they are deterministic and incur no API use:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm run build
```

The live-provider smoke test is skipped unless explicitly enabled:

```powershell
$env:RUN_REAL_OPENAI_TEST="1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_real_openai.py -q
Remove-Item Env:RUN_REAL_OPENAI_TEST
```

That opt-in command uses the backend API key and may incur provider usage. Do not
run it in routine CI.
