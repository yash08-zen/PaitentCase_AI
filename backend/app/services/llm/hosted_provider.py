"""
services/llm/hosted_provider.py
-------------------------------
Anthropic Claude API provider implementation supporting tool-enforced JSON schemas,
multimodal image input for handwriting OCR verification, timeouts, and exponential backoff.
"""
import os
import json
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
import httpx

from app.core.config import settings
from app.services.llm.interface import BaseLLMProvider, LLMUnavailableError, LLMProviderError, LLMValidationError

logger = logging.getLogger("app.services.llm.hosted")


class HostedLLMProvider(BaseLLMProvider):
    """Hosted Anthropic provider implementing Claude structured output generation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.extraction_model = settings.ANTHROPIC_EXTRACTION_MODEL
        self.reasoning_model = settings.ANTHROPIC_REASONING_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.max_retries = settings.LLM_MAX_RETRIES
        self.max_tokens = settings.LLM_MAX_TOKENS

    def _select_model(self, task: str) -> str:
        """Select appropriate model based on task complexity."""
        if task in ("document_classification", "document_extraction", "followup_questions"):
            return self.extraction_model
        return self.reasoning_model

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "unconfigured",
                "provider": "hosted",
                "error": "ANTHROPIC_API_KEY is not set in environment.",
                "available": False
            }
        return {
            "status": "configured",
            "provider": "hosted",
            "extraction_model": self.extraction_model,
            "reasoning_model": self.reasoning_model,
            "available": True
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

        model_name = self._select_model(task)

        # Build tool definition for strict JSON schema enforcement
        tool_name = "clinical_structured_output"
        tools = [
            {
                "name": tool_name,
                "description": f"Outputs verified structured data for task '{task}'",
                "input_schema": json_schema,
            }
        ]

        # Construct message content
        content_items: List[Dict[str, Any]] = []

        if images:
            for img in images:
                content_items.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/png"),
                        "data": img["base64_data"]
                    }
                })

        content_items.append({
            "type": "text",
            "text": user_content
        })

        payload = {
            "model": model_name,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": content_items
                }
            ],
            "tools": tools,
            "tool_choice": {"type": "tool", "name": tool_name}
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        # Try with official SDK if installed, or fallback to direct httpx async client
        backoff = 1.0
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        json=payload,
                        headers=headers
                    )

                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if response.status_code == 200:
                    resp_json = response.json()
                    usage = resp_json.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)

                    # Log structured audit metadata without exposing clinical text or keys
                    logger.info(
                        f"[LLM hosted call] task={task} encounter_id={encounter_id} "
                        f"model={model_name} latency={latency_ms}ms "
                        f"tokens_in={input_tokens} tokens_out={output_tokens}"
                    )

                    # Extract the tool use content
                    for block in resp_json.get("content", []):
                        if block.get("type") == "tool_use" and block.get("name") == tool_name:
                            input_data = block.get("input")
                            if isinstance(input_data, dict):
                                return input_data
                            elif isinstance(input_data, str):
                                return json.loads(input_data)

                    raise LLMValidationError("Response did not contain valid tool_use structured output")

                elif response.status_code in (429, 500, 502, 503, 529):
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue
                else:
                    raise LLMProviderError(f"Anthropic API returned error {response.status_code}: {response.text}")

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = str(net_err)
                if attempt < self.max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise LLMUnavailableError(f"Hosted LLM unavailable after {self.max_retries} attempts: {last_error}")
            except Exception as e:
                logger.error(f"Error during hosted LLM call: {type(e).__name__}")
                raise

        raise LLMUnavailableError(f"Hosted LLM retry limit exceeded: {last_error}")

