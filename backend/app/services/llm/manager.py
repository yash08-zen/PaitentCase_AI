"""
services/llm/manager.py
-----------------------
LLM Service Manager coordinating provider dispatch (hosted, local, mock),
de-identification before external calls, prompt versioning, per-call
logging and graceful degradation when the LLM is unavailable.

Per-call log line: provider, model, prompt version, task, encounter id,
token usage and latency. Clinical text and keys are never logged.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.llm.hosted_provider import HostedLLMProvider
from app.services.llm.interface import BaseLLMProvider, LLMUnavailableError
from app.services.llm.local_provider import LocalLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.prompts import PROMPT_VERSION
from app.services.llm.scrubber import TextScrubber

logger = logging.getLogger("app.services.llm.manager")

CURRENT_PROMPT_VERSION = PROMPT_VERSION

HOSTED_CONSENT_LINE = (
    "Hosted AI mode sends de-identified clinical text (and page images for the handwriting "
    "path) to the configured provider. Use synthetic data only."
)


class LLMServiceManager:
    """Central entry point for all AI Clinical Insights generation."""

    def __init__(self):
        self._mock = MockLLMProvider()
        self._hosted = HostedLLMProvider()
        self._local = LocalLLMProvider()

    @property
    def mode(self) -> str:
        mode = (settings.LLM_PROVIDER or "hosted").lower()
        return mode if mode in ("hosted", "local", "mock") else "mock"

    @property
    def mock(self) -> MockLLMProvider:
        return self._mock

    def get_provider(self) -> BaseLLMProvider:
        return {"mock": self._mock, "local": self._local, "hosted": self._hosted}[self.mode]

    @property
    def is_external(self) -> bool:
        return self.mode == "hosted"

    @property
    def vision_available(self) -> bool:
        return self.mode in ("hosted", "mock")

    async def is_available(self) -> bool:
        health = await self.get_provider().health_check()
        return bool(health.get("available", health.get("status") == "healthy"))

    def model_for(self, task: str) -> str:
        provider = self.get_provider()
        if isinstance(provider, HostedLLMProvider):
            return provider.select_model(task)
        return getattr(provider, "model_name", "unknown")

    async def get_status(self) -> Dict[str, Any]:
        """Operational metadata and active provider health (never the key)."""
        health = await self.get_provider().health_check()
        available = bool(health.get("available", health.get("status") == "healthy"))
        return {
            "active_mode": self.mode,
            "processing_label": {"hosted": "hosted", "local": "local", "mock": "mock (offline fixtures)"}[self.mode],
            "available": available,
            "state": "available" if available else "llm_unavailable",
            "capability": "reduced" if self.mode == "local" else "full",
            "vision_available": self.vision_available and available,
            "summary_languages": ["en", "hi", "mr"] if self.mode == "hosted" else ["en"],
            "prompt_version": CURRENT_PROMPT_VERSION,
            "air_gapped_compatible": self.mode in ("local", "mock"),
            "external_calls": self.is_external,
            "followups_enabled": settings.AI_FOLLOWUPS_ENABLED,
            "provider_health": health,
            "synthetic_data_notice": "Research prototype configured for synthetic evaluation only. No real PHI.",
            "consent_statement": (
                HOSTED_CONSENT_LINE if self.is_external else
                "Clinician-assisted AI review. Output is unverified until accepted by a licensed practitioner."
            ),
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
        patient_name: Optional[str] = None,
        patient_identifiers: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Run one structured LLM call.
        Returns (validated_output, metadata). metadata carries provider, model,
        prompt version, token usage, latency and whether the call left the machine.
        Raises LLMUnavailableError when the provider cannot be reached.
        """
        provider = self.get_provider()
        is_external = self.is_external

        token_map: Dict[str, str] = {}
        content = user_content
        if is_external:
            content, token_map = TextScrubber(patient_name, patient_identifiers).scrub(user_content)

        start = time.perf_counter()
        try:
            raw = await provider.generate(
                task=task,
                system_prompt=system_prompt,
                user_content=content,
                json_schema=json_schema,
                images=images,
                encounter_id=encounter_id,
            )
        except LLMUnavailableError:
            logger.warning(
                "[LLM call] provider=%s task=%s encounter_id=%s status=unavailable",
                self.mode, task, encounter_id,
            )
            raise
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        usage = raw.pop("_usage", None) or {}
        result = self._deep_reattach(raw, token_map) if token_map else raw
        metadata = {
            "provider": self.mode,
            "task": task,
            "model_name": usage.get("model") or self.model_for(task),
            "prompt_version": CURRENT_PROMPT_VERSION,
            "latency_ms": latency_ms,
            "input_tokens": int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(usage.get("output_tokens", 0) or 0),
            "deidentified": bool(token_map) or is_external,
            "is_external": is_external,
            "encounter_id": encounter_id,
        }
        logger.info(
            "[LLM call] provider=%s model=%s prompt_version=%s task=%s encounter_id=%s "
            "tokens_in=%s tokens_out=%s latency_ms=%s",
            metadata["provider"], metadata["model_name"], CURRENT_PROMPT_VERSION, task,
            encounter_id, metadata["input_tokens"], metadata["output_tokens"], latency_ms,
        )
        return result, metadata

    def _deep_reattach(self, obj: Any, token_map: Dict[str, str]) -> Any:
        """Recursively restore scrubbed tokens across nested structures."""
        if isinstance(obj, str):
            return TextScrubber.reattach(obj, token_map)
        if isinstance(obj, dict):
            return {k: self._deep_reattach(v, token_map) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_reattach(item, token_map) for item in obj]
        return obj


llm_service = LLMServiceManager()
