"""LLM client contract, model routing, and normalized API errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_iteration_workbench.config import AppConfig

ModelTier = Literal["budget", "premium"]
ErrorCategory = Literal["auth", "rate_limit", "network", "invalid_request", "unknown"]


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response contract for generation calls."""

    text: str
    model_used: str


class LLMError(Exception):
    """Normalized error carrying a user-readable message and category."""

    def __init__(self, message: str, category: ErrorCategory) -> None:
        super().__init__(message)
        self.message = message
        self.category = category


class LLMClient:
    """Primary LLM client interface with deterministic model routing."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def resolve_model(self, tier: ModelTier, model_override: str | None = None) -> str:
        """Resolve a model name from tier selection and optional override."""
        if model_override:
            return model_override
        if tier == "budget":
            return self.config.budget_model
        if tier == "premium":
            return self.config.premium_model
        raise ValueError(f"Unsupported tier: {tier}")

    def generate_text(
        self,
        *,
        tier: ModelTier,
        user_text: str,
        system_text: str = "",
        temperature: float = 0.2,
        max_output_tokens: int = 512,
        model_override: str | None = None,
    ) -> LLMResponse:
        """Generate text with OpenAI and return normalized response data."""
        resolved_model = self.resolve_model(tier=tier, model_override=model_override)

        try:
            from openai import (
                APIConnectionError,
                APITimeoutError,
                AuthenticationError,
                BadRequestError,
                OpenAI,
                RateLimitError,
            )
        except ModuleNotFoundError as exc:
            raise LLMError(
                "OpenAI client dependency is missing. Install project requirements.",
                "unknown",
            ) from exc

        client = OpenAI(api_key=self.config.openai_api_key)

        messages: list[dict[str, str]] = []
        if system_text.strip():
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

        try:
            completion = client.chat.completions.create(
                model=resolved_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_output_tokens,
            )
            text = completion.choices[0].message.content or ""
            return LLMResponse(text=text, model_used=resolved_model)
        except AuthenticationError as exc:
            raise LLMError(
                "Authentication failed. Check OPENAI_API_KEY and model access.",
                "auth",
            ) from exc
        except RateLimitError as exc:
            raise LLMError("Rate limit reached. Retry in a moment.", "rate_limit") from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMError("Network error while contacting OpenAI.", "network") from exc
        except BadRequestError as exc:
            raise LLMError("Invalid request sent to OpenAI.", "invalid_request") from exc
        except Exception as exc:
            raise LLMError("Unexpected LLM request failure.", "unknown") from exc
