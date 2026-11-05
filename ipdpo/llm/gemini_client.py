"""Gemini API client adapter using official google-genai SDK."""
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field
from ipdpo.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiRefinementResult(BaseModel):
    refined_prompt: str = Field(description="The polished, highly-structured prompt.")
    weaknesses_identified: list[str] = Field(default_factory=list, description="Weaknesses detected in original draft.")
    improvements_made: list[str] = Field(default_factory=list, description="Explicit enhancements applied.")


class GeminiClient:
    """
    Adapter encapsulating Google Gemini API interactions.
    Provides graceful fallbacks when offline or unconfigured.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self.model_name = model_name if model_name else GEMINI_MODEL
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI Client: {e}")
                self._client = None

    def is_available(self) -> bool:
        """Returns True only if an API key is present and SDK initialized."""
        return self._client is not None

    def refine_prompt(
        self,
        draft_prompt: str,
        task_type: str,
        context_summary: str = "",
    ) -> Tuple[bool, Optional[GeminiRefinementResult], str, int]:
        """
        Submits prompt to Gemini for structured ambiguity detection and refinement.
        Returns: (success: bool, result: Optional[GeminiRefinementResult], error_or_notes: str, latency_ms: int)
        """
        if not self.is_available():
            return (
                False,
                None,
                "Gemini API key is not configured or client failed to initialize. Set GEMINI_API_KEY in .env.",
                0,
            )

        system_instruction = (
            "You are an expert prompt engineer specializing in software engineering prompts. "
            "Your goal is to critique and refine the supplied software development prompt. "
            "Sharpen its instructions, ensure role boundaries are clear, structure requirements logically, "
            "and strengthen negative constraints and expected output contracts. "
            "Do NOT remove or alter factual project context. "
            "Output MUST be structured JSON conforming to the schema with: "
            "refined_prompt, weaknesses_identified, and improvements_made."
        )

        user_content = (
            f"TASK CATEGORY: {task_type}\n\n"
            f"DRAFT PROMPT TO REFINE:\n\"\"\"\n{draft_prompt}\n\"\"\"\n\n"
            f"Refine this prompt for maximum clarity, actionable constraints, and exact deliverables."
        )

        start_time = time.time()
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                    "response_schema": GeminiRefinementResult,
                    "temperature": 0.2,
                },
            )
            latency_ms = int((time.time() - start_time) * 1000)

            # Parse response
            raw_text = response.text
            data = json.loads(raw_text)
            parsed = GeminiRefinementResult(**data)
            return True, parsed, "Successfully refined by Gemini", latency_ms

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            err_msg = str(e)
            logger.error(f"Gemini refinement failed: {err_msg}")
            return False, None, f"Gemini API Error: {err_msg}", latency_ms
