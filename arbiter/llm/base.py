"""Provider interface.

Deliberately built on plain HTTP through requests rather than vendor SDKs: one less
dependency to break, and the wire format is visible in the repo for anyone reading it.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..models import Usage

# Free API tiers rate limit aggressively. A long benchmark will hit 429 sooner or later,
# and losing a trial to it would quietly corrupt the results, so retry rather than fail.
RETRY_STATUSES = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 5
BASE_BACKOFF_S = 2.0


def request_with_retry(send: Callable[[], Any], label: str = "") -> Any:
    """Call send(), retrying on rate limits and transient server errors."""
    last = None
    for attempt in range(MAX_ATTEMPTS):
        response = send()
        if response.status_code not in RETRY_STATUSES:
            return response
        last = response
        if attempt == MAX_ATTEMPTS - 1:
            break
        wait = BASE_BACKOFF_S * (2 ** attempt) + random.uniform(0, 1.0)
        header = response.headers.get("Retry-After") if hasattr(response, "headers") else None
        if header:
            try:
                wait = max(wait, float(header))
            except ValueError:
                pass
        print("    [{0}] http {1}, waiting {2:.1f}s (attempt {3}/{4})".format(
            label or "llm", response.status_code, wait, attempt + 1, MAX_ATTEMPTS))
        time.sleep(wait)
    return last


class LLMError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    usage: Usage = field(default_factory=Usage)
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMProvider:
    """Every provider takes the same request shape: a system prompt, a user prompt,
    and an optional list of PNG bytes to attach as images."""

    name = "base"

    def __init__(self, model: str, api_key: str = "", timeout: int = 120, temperature: float = 0.2):
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature

    def complete(self, system: str, user: str, images: Optional[List[bytes]] = None) -> Reply:
        raise NotImplementedError

    # Providers that record traffic override these so runs can be replayed offline.
    def start_scope(self, scope: str) -> None:
        pass


def build_provider(provider: str, model: str, api_key: str = "", **kwargs: Any) -> LLMProvider:
    provider = (provider or "").lower().strip()
    if provider == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model, api_key, **kwargs)
    if provider == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(model, api_key, **kwargs)
    if provider == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model, api_key, **kwargs)
    if provider == "mock":
        from .mock import MockProvider
        return MockProvider(model, api_key, **kwargs)
    raise LLMError("unknown provider {0!r}, expected one of: gemini, openai, anthropic, mock".format(provider))


def env_key(*names: str) -> str:
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""
