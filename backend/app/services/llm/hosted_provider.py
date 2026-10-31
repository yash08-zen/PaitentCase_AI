"""
services/llm/hosted_provider.py
-------------------------------
Hosted provider built on the official `anthropic` Python SDK.

- Structured outputs (`output_config.format` with a JSON schema) so every
  response is schema-valid JSON. Forced tool_choice is not used: current
  Sonnet models reject it.
- Base64 image input for the handwriting vision path.
- Timeouts and retries with exponential backoff are delegated to the SDK
  (`timeout`, `max_retries`), which retries connection errors, 408, 409, 429
  and 5xx.
- The API key is read from settings (.env) only and never logged or returned.
"""
import json
import logging
from typing import Any, Dict, List, Optional

import anthropic

from app.core.config import settings
from app.services.llm.interface import (
    BaseLLMProvider, LLMProviderError, LLMUnavailableError, LLMValidationError,
)
from app.services.llm.prompts import EXTRACTION_TASKS, MAX_TOKENS

logger = logging.getLogger("app.services.llm.hosted")


class HostedLLMProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key_override = api_key
        self._client: Optional[anthropic.AsyncAnthropic] = None

    @property
    def api_key(self) -> str:
        return self._api_key_override or settings.ANTHROPIC_API_KEY

    @property
    def model_name(self) -> str:
        return settings.ANTHROPIC_REASONING_MODEL

    def select_model(self, task: str) -> str:
        if task in EXTRACTION_TASKS:
            return settings.ANTHROPIC_EXTRACTION_MODEL
        return settings.ANTHROPIC_REASONING_MODEL

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                timeout=float(settings.LLM_TIMEOUT_SECONDS),
                max_retries=settings.LLM_MAX_RETRIES,
            )
        return self._client

    async def health_check(self) -> Dict[str, Any]:
        configured = bool(self.api_key)
        return {
            "status": "configured" if configured else "unconfigured",
            "provider": "hosted",
            "extraction_model": settings.ANTHROPIC_EXTRACTION_MODEL,
            "reasoning_model": settings.ANTHROPIC_REASONING_MODEL,
            "available": configured,
            "vision_capable": True,
            "error": None if configured else "ANTHROPIC_API_KEY is not set in .env.",
        }

    async def generate(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        json_schema: Dict[str, Any],
        *,
        images: Optional[List[Dict[str, Any]]] = None,
        encounter_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMUnavailableError("ANTHROPIC_API_KEY is not configured in .env")

        model = self.select_model(task)
        content: List[Dict[str, Any]] = []
        for img in images or []:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("media_type", "image/png"),
                    "data": img["base64_data"],
                },
            })
        content.append({"type": "text", "text": user_content})

        max_tokens = min(MAX_TOKENS.get(task, settings.LLM_MAX_TOKENS), settings.LLM_MAX_TOKENS)
        try:
            response = await self._get_client().messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
                output_config={"format": {"type": "json_schema", "schema": json_schema}},
            )
        except (anthropic.APIConnectionError, anthropic.RateLimitError,
                anthropic.InternalServerError, anthropic.AuthenticationError,
                anthropic.PermissionDeniedError) as exc:
            # Message text only; never the request body or headers
            raise LLMUnavailableError(f"Hosted LLM unavailable ({type(exc).__name__})") from exc
        except anthropic.APIStatusError as exc:
            raise LLMProviderError(f"Hosted LLM error HTTP {exc.status_code}") from exc

        if response.stop_reason == "refusal":
            raise LLMValidationError("Hosted LLM declined the request (refusal)")
        if response.stop_reason == "max_tokens":
            raise LLMValidationError(f"Hosted LLM output truncated at {max_tokens} tokens")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise LLMValidationError("Hosted LLM returned no JSON text block")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMValidationError("Hosted LLM returned malformed JSON") from exc

        usage = response.usage
        data["_usage"] = {
            "model": model,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        }
        return data
