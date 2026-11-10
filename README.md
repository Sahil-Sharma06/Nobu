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
Dry-run is the default; no real email is ever sent unless explicitly enabled (and Phase 1 has no real sender at all).
