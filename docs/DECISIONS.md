# Decisions

- **OS / tooling:** Windows 11; plain `venv` + pip (uv not installed). Backend and frontend run natively; only Postgres runs in Docker.
- **Database:** PostgreSQL 16 in docker compose; tests use SQLite in-memory.
- **LLM:** one wrapper (`nobu.llm`), provider chosen by `NOBU_LLM_PROVIDER`: `stub` (deterministic, tests), `openai_compat` (NVIDIA build.nvidia.com, Mistral, OpenRouter, ... via `NOBU_LLM_BASE_URL`/`NOBU_LLM_API_KEY`), `ollama` (local), `anthropic`. Model from `NOBU_LLM_MODEL`. Structured output via a forced tool/function call, with a JSON-text fallback.
- **Web search:** DuckDuckGo via the free `ddgs` library behind a `SearchProvider` interface; a fake is used in tests.
- **Contacts (Phase 1):** user-supplied contact plus emails found on public company/job pages. A paid contact-data provider is Phase 4, behind the same `ContactProvider` interface.
- **Resume:** uploaded once through the UI, stored in `data/` (gitignored).
- **Sending:** Phase 1 has only a dry-run transport. Guardrails (cap, dedupe, suppression, critic gate) live in code.
- **Human-in-the-loop:** the LangGraph drafting graph ends at `critic`; the result is stored as an `outreach` row in `drafted`. That row is the durable checkpoint (survives restarts), and review actions are API calls. Sending is a separate guarded step, never part of the graph.
- **Critic:** deterministic checks in code (length, every claim cites a real fact id / fetched URL, a sourced company point exists, recipient present and >= 0.8 confidence) plus an LLM pass. The user may acknowledge a flag explicitly; `no_contact` can only be cleared by adding a recipient.
- **Opt-out:** every email ends with a one-line opt-out, appended in code.
- **Paths:** `data_dir` and `.env` are resolved against the repo, never the working directory, so "delete all my data" can only touch `Nobu/data`.
