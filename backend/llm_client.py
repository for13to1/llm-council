"""LLM client supporting multiple providers."""

import os
from typing import Any

import httpx

from .config import PROVIDERS, model_display_name


def resolve_provider(model: dict[str, str]) -> dict[str, Any]:
    """
    Resolve API endpoint, key, and headers for a model.

    Args:
        model: Dict with 'provider' (key into PROVIDERS) and 'model' (model id)

    Returns:
        Dict with url, api_key, model_id, extra_headers, api_format
    """
    provider_name = model["provider"]
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")

    provider = PROVIDERS[provider_name]
    api_key_env = provider.get("api_key_env", "")
    api_key = os.getenv(api_key_env, "") if api_key_env else ""

    return {
        "url": provider["base_url"],
        "api_key": api_key,
        "model_id": model["model"],
        "extra_headers": provider.get("extra_headers", {}),
        "api_format": provider.get("api_format", "openai"),
    }


def _build_anthropic_payload(model_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    """Convert OpenAI-style messages to Anthropic Messages API format."""
    system_parts = []
    anthropic_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append(msg["content"])
        else:
            # Merge consecutive same-role messages (Anthropic requires strict alternation)
            if anthropic_messages and anthropic_messages[-1]["role"] == msg["role"]:
                anthropic_messages[-1]["content"] += "\n\n" + msg["content"]
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

    # Anthropic requires at least one message starting with user role
    if not anthropic_messages:
        anthropic_messages.append({"role": "user", "content": "Continue."})

    payload: dict[str, Any] = {
        "model": model_id,
        "messages": anthropic_messages,
        "max_tokens": 8192,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    return payload


def _parse_anthropic_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse Anthropic Messages API response into OpenAI-like format."""
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return {"content": "\n".join(text_blocks), "reasoning_details": None}


async def query_model(
    model: dict[str, str], messages: list[dict[str, str]], timeout: float = 120.0
) -> dict[str, Any] | None:
    """
    Query a single model via its provider API.

    Args:
        model: Dict with 'provider' and 'model' keys
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    try:
        provider = resolve_provider(model)
    except ValueError as e:
        print(f"Config error for model {model_display_name(model)}: {e}")
        return None

    api_format = provider["api_format"]

    headers = {"Content-Type": "application/json"}

    if api_format == "anthropic":
        if provider["api_key"]:
            headers["x-api-key"] = provider["api_key"]
        headers.update(provider["extra_headers"])
        payload = _build_anthropic_payload(provider["model_id"], messages)
    else:
        if provider["api_key"]:
            headers["Authorization"] = f"Bearer {provider['api_key']}"
        headers.update(provider["extra_headers"])
        payload = {
            "model": provider["model_id"],
            "messages": messages,
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(provider["url"], headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()

            if api_format == "anthropic":
                return _parse_anthropic_response(data)

            message = data["choices"][0]["message"]
            return {"content": message.get("content"), "reasoning_details": message.get("reasoning_details")}

    except Exception as e:
        print(f"Error querying model {model_display_name(model)}: {e}")
        return None


async def query_models_parallel(
    models: list[dict[str, str]], messages: list[dict[str, str]]
) -> dict[str, dict[str, Any] | None]:
    """
    Query multiple models in parallel.

    Args:
        models: List of model dicts
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model display name to response dict (or None if failed)
    """
    import asyncio

    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)

    return {model_display_name(model): response for model, response in zip(models, responses, strict=True)}
