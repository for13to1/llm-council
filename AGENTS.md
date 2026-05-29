# LLM Council — Agent Instructions

## Quick Start

```bash
uv sync                          # install Python deps
cd frontend && npm install && cd ..  # install frontend deps
cp .env.example .env             # then fill in your API keys
uv run python -m backend.main    # start backend on :8001
cd frontend && npm run dev       # start frontend on :5173
```

## Architecture

- **Backend** (`backend/`): FastAPI app serving both JSON API (`/api/...`) and server-rendered HTML (Jinja2 templates in `backend/templates/`)
- **Frontend** (`frontend/`): React 19 + Vite 7 SPA (alternative UI)
- **Storage**: JSON files in `data/conversations/` (gitignored)
- **Providers**: Unified provider system in `backend/config.py` — OpenRouter, OpenAI, Anthropic, Google, xAI, DeepSeek, Ollama are all just providers. Each model specifies which provider to use.

The backend is the primary interface. It serves HTML pages at `/`, `/new`, `/conversations/{id}` and exposes REST + SSE streaming endpoints.

## Key Files

- `backend/config.py` — `PROVIDERS` dict (provider definitions), `COUNCIL_MODELS` / `CHAIRMAN_MODEL` / `TITLE_MODEL` (all dict format: `{"provider": "...", "model": "..."}`)
- `backend/council.py` — 3-stage orchestration: collect responses → peer ranking → chairman synthesis
- `backend/llm_client.py` — async httpx client, `resolve_provider()` looks up provider config
- `backend/storage.py` — JSON file-based conversation persistence
- `backend/main.py` — FastAPI app, routes, SSE streaming endpoint
- `frontend/src/` — React SPA (alternative to server-rendered backend)

## Commands

| Task | Command |
|------|---------|
| Install backend deps | `uv sync` |
| Install frontend deps | `cd frontend && npm install` |
| Run backend | `uv run python -m backend.main` |
| Run frontend dev | `cd frontend && npm run dev` |
| Lint (Python) | `uv run ruff check .` |
| Format (Python) | `uv run ruff format .` |
| Lint (Frontend) | `cd frontend && npm run lint` |
| Build (Frontend) | `cd frontend && npm run build` |

## Requirements

- **Python 3.14** (specified in `.python-version` and `pyproject.toml`)
- **uv** for Python package management
- **Node.js** + npm for frontend
- At least one provider API key in `.env` (e.g. `OPENROUTER_API_KEY`)

## Provider System

All models use dict format: `{"provider": "name", "model": "model-id"}`. Providers are defined in `PROVIDERS` in `config.py`. Each provider has:
- `base_url` — overridable via `{PROVIDER}_BASE_URL` env var (for relays/proxies)
- `api_key_env` — env var name for the API key
- `extra_headers` — optional extra headers (e.g. Anthropic's `anthropic-version`)
- `api_format` — `"openai"` (default) or `"anthropic"` (uses native Messages API)

Example model configs:
```python
# Via OpenRouter (aggregator)
{"provider": "openrouter", "model": "openai/gpt-5.1"}
# Direct to provider
{"provider": "openai", "model": "gpt-4o"}
# Local Ollama
{"provider": "ollama", "model": "qwen3:8b"}
```

## Gotchas

- The backend and frontend are **independent UIs**. The backend renders HTML via Jinja2; the frontend is a React SPA. Changes to one don't affect the other.
- No test suite exists. Verify changes manually by running the app and submitting a query.
- Ruff is configured with `line-length = 120` and `target-version = "py314"`. Long lines (E501) are ignored.
- Conversations are stored as flat JSON files in `data/conversations/`. This directory is gitignored.
- The `main.py` at the repo root is a placeholder — the real entrypoint is `backend.main`.
- The SSE streaming endpoint (`/api/conversations/{id}/message/stream`) is the primary way the frontend communicates during council runs.
- Display name format is `"provider/model"` (e.g. `"openrouter/gpt-5.1"`). `model_display_name()` in `config.py` converts model dict to this format. `short_model_name()` in `main.py` and `shortModelName()` in frontend strip the provider prefix for UI display (e.g. `"openrouter/gpt-5.1"` → `"gpt-5.1"`).
