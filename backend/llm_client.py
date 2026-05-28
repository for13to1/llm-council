"""LLM client supporting multiple provider modes."""

import os
from typing import Any

import httpx

from .config import (
    DIRECT_PROVIDERS,
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    PROVIDER_MODE,
    model_display_name,
)


def resolve_provider(model: str | dict[str, str]) -> dict[str, Any]:
    """
    Resolve API endpoint, key, and headers for a model.

    Args:
        model: String (openrouter) or dict with 'provider'/'model' keys (direct)

    Returns:
        Dict with url, api_key, model_id, extra_headers
    """
    if PROVIDER_MODE == "openrouter":
        return {
            "url": OPENROUTER_API_URL,
            "api_key": OPENROUTER_API_KEY,
            "model_id": model if isinstance(model, str) else f"{model['provider']}/{model['model']}",
            "extra_headers": {},
        }
    else:
        if isinstance(model, str):
            raise ValueError(
                f"Direct mode requires dict model identifiers, got string: {model}. "
                f'Use {{"provider": "...", "model": "..."}} format.'
            )
        provider_name = model["provider"]
        if provider_name not in DIRECT_PROVIDERS:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(DIRECT_PROVIDERS.keys())}")

        provider = DIRECT_PROVIDERS[provider_name]
        api_key_env = provider.get("api_key_env", "")
        api_key = os.getenv(api_key_env, "") if api_key_env else ""

        return {
            "url": provider["base_url"],
            "api_key": api_key,
            "model_id": model["model"],
            "extra_headers": provider.get("extra_headers", {}),
        }


async def query_model(
    model: str | dict[str, str], messages: list[dict[str, str]], timeout: float = 120.0
) -> dict[str, Any] | None:
    """
    Query a single model via its provider API.

    Args:
        model: Model identifier (string for openrouter, dict for direct)
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

    headers = {
        "Content-Type": "application/json",
    }
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
            message = data["choices"][0]["message"]

            return {"content": message.get("content"), "reasoning_details": message.get("reasoning_details")}

    except Exception as e:
        print(f"Error querying model {model_display_name(model)}: {e}")
        return None


async def query_models_parallel(
    models: list[str | dict[str, str]], messages: list[dict[str, str]]
) -> dict[str, dict[str, Any] | None]:
    """
    Query multiple models in parallel.

    Args:
        models: List of model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model display name to response dict (or None if failed)
    """
    import asyncio

    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)

    return {model_display_name(model): response for model, response in zip(models, responses, strict=True)}
