"""
services/llm/interface.py
-------------------------
Abstract Base Class and typing definitions for LLM providers.
Enforces the core contract:
    generate(task, system_prompt, user_content, json_schema, *, images=None) -> validated dict
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class LLMProviderError(Exception):
    """Raised when an LLM provider fails permanently or exceeds retry limit."""
    pass


class LLMUnavailableError(LLMProviderError):
    """Raised when the requested LLM service is offline or unreachable."""
    pass


class LLMValidationError(LLMProviderError):
    """Raised when the LLM response fails JSON schema validation."""
    pass


class BaseLLMProvider(ABC):
    """Abstract provider for LLM generation."""

    @abstractmethod
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
        """
        Execute structured LLM generation adhering to json_schema.
        Returns validated python dictionary.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return connectivity and model status."""
        pass

