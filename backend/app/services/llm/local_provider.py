"""
services/llm/local_provider.py
------------------------------
Local / air-gapped Ollama provider pointing to OpenAI-compatible endpoint.
Enforces single-concurrency queue, zero temperature, max context window <= 4096,
and graceful degradation when local daemon is not running.
"""
import json
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
import httpx

from app.core.config import settings
from app.services.llm.interface import BaseLLMProvider, LLMUnavailableError, LLMProviderError, LLMValidationError
from app.services.llm.prompts import MAX_TOKENS

logger = logging.getLogger("app.services.llm.local")


class LocalLLMProvider(BaseLLMProvider):
    """Local air-gapped LLM provider interfacing with Ollama."""

    # Hardware safety lock: strictly 1 inference job at a time to prevent OOM
    _concurrency_lock = asyncio.Semaphore(1)

    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.OLLAMA_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/models")
                if res.status_code == 200:
                    return {
                        "status": "healthy",
                        "provider": "local",
                        "endpoint": self.base_url,
                        "model": self.model_name,
                        "available": True,
                        "vision_capable": False  # Documented limitation of lightweight 3B local model
                    }
        except Exception:
            pass

        return {
            "status": "offline",
            "provider": "local",
            "endpoint": self.base_url,
            "model": self.model_name,
            "available": False,
            "vision_capable": False
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
        # Vision limitation check
        if images:
            raise LLMUnavailableError(
                "Local 3B model does not support image/vision processing. "
                "Handwritten documents must be routed to manual doctor review."
            )

        schema_instruction = (
            f"\n\nCRITICAL: You MUST reply ONLY with valid JSON complying with this schema:\n"
            f"{json.dumps(json_schema, indent=2)}\n"
            f"Do not include markdown codeblocks or conversational text outside the JSON object."
        )

        full_system = f"{system_prompt}\n{schema_instruction}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0,
            "max_tokens": min(MAX_TOKENS.get(task, 1024), 1024),
            "response_format": {"type": "json_object"},
            "options": {
                "num_ctx": 4096,
                "temperature": 0.0
            }
        }

        # Single concurrency lock
        async with self._concurrency_lock:
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload
                    )

                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if res.status_code == 200:
                    data = res.json()
                    raw_content = data["choices"][0]["message"]["content"]

                    logger.info(
                        f"[LLM local call] task={task} encounter_id={encounter_id} "
                        f"model={self.model_name} latency={latency_ms}ms"
                    )

                    try:
                        parsed = json.loads(raw_content)
                    except json.JSONDecodeError as je:
                        raise LLMValidationError(f"Local LLM returned malformed JSON: {je}")
                    if not isinstance(parsed, dict):
                        raise LLMValidationError("Local LLM returned non-object JSON")
                    usage = data.get("usage") or {}
                    parsed["_usage"] = {
                        "model": self.model_name,
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                    }
                    return parsed

                else:
                    raise LLMProviderError(f"Local LLM returned HTTP {res.status_code}")

            except (httpx.TimeoutException, httpx.NetworkError) as err:
                raise LLMUnavailableError(
                    f"Local LLM daemon ({self.base_url}) unreachable or timed out: {err}"
                )

