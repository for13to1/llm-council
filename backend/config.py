"""Configuration for the LLM Council."""

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# --- Provider definitions ---
# Each provider has a base_url and an api_key_env (empty string = no auth).
# base_url can be overridden via env var: {PROVIDER_NAME}_BASE_URL
_PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/messages",
        "api_key_env": "ANTHROPIC_API_KEY",
        "extra_headers": {"anthropic-version": "2023-06-01"},
        "api_format": "anthropic",  # uses x-api-key instead of Bearer, different request/response format
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "api_key_env": "GOOGLE_API_KEY",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1/chat/completions",
        "api_key_env": "XAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1/chat/completions",
        "api_key_env": "",
    },
}

PROVIDERS: dict[str, dict[str, Any]] = {}
for _name, _cfg in _PROVIDER_DEFAULTS.items():
    _env_key = f"{_name.upper()}_BASE_URL"
    PROVIDERS[_name] = {
        **_cfg,
        "base_url": os.getenv(_env_key, _cfg["base_url"]),
    }

# --- Model definitions ---
# Each model is a dict with "provider" (key into PROVIDERS) and "model" (model id sent to the API).
# Examples:
#   {"provider": "openrouter", "model": "openai/gpt-5.1"}   — via OpenRouter
#   {"provider": "openai", "model": "gpt-4o"}                — direct to OpenAI
#   {"provider": "ollama", "model": "qwen3:8b"}              — local Ollama
COUNCIL_MODELS: list[dict[str, str]] = [
    {"provider": "openrouter", "model": "openai/gpt-5.5"},
    {"provider": "openrouter", "model": "google/gemini-3.5-flash"},
    {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"},
    {"provider": "openrouter", "model": "x-ai/grok-4.3"},
]

CHAIRMAN_MODEL: dict[str, str] = {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"}

TITLE_MODEL: dict[str, str] = {"provider": "openrouter", "model": "google/gemini-3.5-flash"}

# Data directory for conversation storage
DATA_DIR = "data/conversations"


def model_display_name(model: dict[str, str]) -> str:
    """Convert a model identifier to a display-friendly string like 'provider/model'."""
    provider = model["provider"]
    model_id = model["model"]
    # Strip routing prefix from model id (e.g. "openai/gpt-5.1" → "gpt-5.1")
    if "/" in model_id:
        model_id = model_id.split("/", 1)[1]
    return f"{provider}/{model_id}"
