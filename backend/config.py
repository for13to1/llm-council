"""Configuration for the LLM Council."""

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Provider mode: "openrouter" (all via OpenRouter) or "direct" (each provider's own API)
PROVIDER_MODE = os.getenv("PROVIDER_MODE", "openrouter")

# --- OpenRouter mode config ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- Direct mode provider configs ---
# Each provider needs: base_url, api_key_env (empty string = no auth), optional extra_headers
DIRECT_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/chat/completions",
        "api_key_env": "ANTHROPIC_API_KEY",
        "extra_headers": {"anthropic-version": "2023-06-01"},
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
        "api_key_env": "",  # Ollama doesn't need auth
    },
}

# --- Model definitions ---
# OpenRouter mode: list of strings like "openai/gpt-5.1"
# Direct mode: list of dicts like {"provider": "openai", "model": "gpt-5.1"}
#
# --- Default (OpenRouter) ---
COUNCIL_MODELS: list[str | dict[str, str]] = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL: str | dict[str, str] = "google/gemini-3-pro-preview"

TITLE_MODEL: str | dict[str, str] = "google/gemini-2.5-flash"

# --- Local Ollama example (set PROVIDER_MODE=direct in .env to use) ---
# COUNCIL_MODELS = [
#     {"provider": "ollama", "model": "qwen3:8b"},
#     {"provider": "ollama", "model": "gemma3:12b"},
# ]
# CHAIRMAN_MODEL = {"provider": "ollama", "model": "qwen3:8b"}
# TITLE_MODEL = {"provider": "ollama", "model": "qwen3:8b"}

# Data directory for conversation storage
DATA_DIR = "data/conversations"


def model_display_name(model: str | dict[str, str]) -> str:
    """Convert a model identifier to a display-friendly string."""
    if isinstance(model, dict):
        return f"{model['provider']}/{model['model']}"
    return model
