"""
services/llm/manager.py
-----------------------
LLM Service Manager coordinating provider dispatch (hosted, local, mock),
de-identification scrubbing for external calls, prompt versioning, structured audit
logging, and graceful fallback when LLMs are offline or unavailable.
"""
import time
import logging
from typing import Dict, Any, Optional, List, Tuple

from app.core.config import settings
from app.services.llm.interface import BaseLLMProvider, LLMUnavailableError, LLMProviderError
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.hosted_provider import HostedLLMProvider
from app.services.llm.local_provider import LocalLLMProvider
from app.services.llm.scrubber import TextScrubber

logger = logging.getLogger("app.services.llm.manager")

CURRENT_PROMPT_VERSION = "2026.10.clinical-insights-v1"


class LLMServiceManager:
    """Central entry point for all AI Clinical Insights generation."""

    def __init__(self):
        self.provider_mode = settings.LLM_PROVIDER
        self._mock = MockLLMProvider()
        self._hosted = HostedLLMProvider()
        self._local = LocalLLMProvider()

    def get_provider(self) -> BaseLLMProvider:
        """Select active provider based on configuration."""
        mode = (settings.LLM_PROVIDER or "hosted").lower()
        if mode == "mock":
            return self._mock
        elif mode == "local":
            return self._local
        elif mode == "hosted":
            return self._hosted
        return self._mock

    async def get_status(self) -> Dict[str, Any]:
        """Expose operational metadata and active provider health."""
        provider = self.get_provider()
        health = await provider.health_check()

        return {
            "active_mode": settings.LLM_PROVIDER,
            "prompt_version": CURRENT_PROMPT_VERSION,
            "air_gapped_compatible": (settings.LLM_PROVIDER in ("local", "mock")),
            "followups_enabled": settings.AI_FOLLOWUPS_ENABLED,
            "provider_health": health,
            "synthetic_data_notice": "Research prototype configured for synthetic evaluation only. No real PHI.",
            "consent_statement": "Clinician-assisted AI review. Output is unverified until accepted by a licensed practitioner."
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
        Execute structured LLM inference with automated scrubbing and provenance tracking.
        Returns:
            (validated_output, metadata_dict)
        """
        provider = self.get_provider()
        is_external = (settings.LLM_PROVIDER == "hosted")

        token_map = {}
        scrubbed_content = user_content

        # Enforce patient de-identification before ANY external outbound call
        if is_external:
            scrubber = TextScrubber(patient_name, patient_identifiers)
            scrubbed_content, token_map = scrubber.scrub(user_content)

        start_time = time.perf_counter()

        try:
            raw_result = await provider.generate(
                task=task,
                system_prompt=system_prompt,
                user_content=scrubbed_content,
                json_schema=json_schema,
                images=images,
                encounter_id=encounter_id,
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Re-attach identity if external call used token mapping
            final_result = raw_result
            if token_map:
                final_result = self._deep_reattach(raw_result, token_map)

            metadata = {
                "provider": settings.LLM_PROVIDER,
                "model_name": getattr(provider, "model_name", "claude-family" if is_external else "unknown"),
                "prompt_version": CURRENT_PROMPT_VERSION,
                "latency_ms": elapsed_ms,
                "deidentified": bool(token_map),
                "is_external": is_external,
            }

            return final_result, metadata

        except LLMUnavailableError as unavail_err:
            logger.warning(f"LLM provider unavailable: {unavail_err}")
            raise

    def _deep_reattach(self, obj: Any, token_map: Dict[str, str]) -> Any:
        """Recursively restore scrubbed tokens across nested dictionary/list structures."""
        if isinstance(obj, str):
            return TextScrubber.reattach(obj, token_map)
        elif isinstance(obj, dict):
            return {k: self._deep_reattach(v, token_map) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_reattach(item, token_map) for item in obj]
        return obj


llm_service = LLMServiceManager()

