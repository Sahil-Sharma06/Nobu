# Nobu

Voice-driven job-outreach agent for freshers. Full spec: [docs/PROJECT.md](docs/PROJECT.md). Decisions: [docs/DECISIONS.md](docs/DECISIONS.md).

## Local development (Windows / PowerShell)

1. Start Docker Desktop, then the database: `docker compose up -d db`
2. Backend:
   ```powershell
   cd backend
   python -m venv .venv; .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   copy ..\.env.example ..\.env
   alembic upgrade head
   uvicorn nobu.api.app:app --reload
   ```
3. Frontend: `cd frontend; npm install; npm run dev`

## Checks

```powershell
cd backend; ruff check .; ruff format --check .; mypy nobu; pytest
cd frontend; npm run lint; npm run build
```

Tests use SQLite and the stub LLM: offline, free, deterministic.

## Using it (Phase 1)

1. Set a real model in `.env` (see `.env.example`), e.g. `NOBU_LLM_PROVIDER=openai_compat` with
   `NOBU_LLM_BASE_URL`, `NOBU_LLM_MODEL`, `NOBU_LLM_API_KEY`.
2. Open http://localhost:5173, upload your resume once, check the fact bank and profile.
3. Type a command: *"Reach out to Acme (acme.dev) for the backend intern role"*.
   If anything is missing or unclear, Nobu asks before researching.
4. Review the card: recipient + confidence, chosen facts + why, draft, critic flags, sources.
   Edit, regenerate with an instruction, resolve flags, approve.
5. Send. In dry-run (the default, and the only mode in Phase 1) the email is written to
   `data/outbox/*.eml` and nothing leaves your machine.

## How it works

`parse_command -> research_company -> match_facts -> find_contact -> draft_email -> critic -> review`

- Every node writes its inputs, outputs and source URLs to `audit_step`.
- Claims about you must cite a fact id; claims about the company must cite a fetched URL.
  The critic checks this in code, then an LLM pass checks the body itself.
- A draft with unresolved flags cannot be approved or sent. Daily cap, 60-day dedupe and the
  suppression list are enforced in code at send time.
Dry-run is the default; no real email is ever sent unless explicitly enabled (and Phase 1 has no real sender at all).
