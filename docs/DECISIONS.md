# Decisions

- **OS / tooling:** Windows 11; plain `venv` + pip (uv not installed). Backend and frontend run natively; only Postgres runs in Docker.
- **Database:** PostgreSQL 16 in docker compose; tests use SQLite in-memory.
- **LLM:** one wrapper (`nobu.llm`), provider chosen by `NOBU_LLM_PROVIDER`: `stub` (deterministic, tests), `ollama` (free, local), `anthropic` (needs `ANTHROPIC_API_KEY`). Model from `NOBU_LLM_MODEL`. The author has no Anthropic key yet, so Ollama is the free real option.
- **Web search:** DuckDuckGo via the free `ddgs` library behind a `SearchProvider` interface; a fake is used in tests.
- **Contacts (Phase 1):** user-supplied contact plus emails found on public company/job pages. A paid contact-data provider is Phase 4, behind the same `ContactProvider` interface.
- **Resume:** uploaded once through the UI, stored in `data/` (gitignored).
- **Sending:** Phase 1 has only a dry-run transport. Guardrails (cap, dedupe, suppression, critic gate) live in code.
