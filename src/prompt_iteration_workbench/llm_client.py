"""LLM client contract and tier-based model routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_iteration_workbench.config import AppConfig

ModelTier = Literal["budget", "premium"]


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response contract for generation calls."""

    text: str
    model_used: str


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
        """
        Return a normalized placeholder response while API integration is pending.

        This method intentionally returns deterministic local output in checkpoint 4.0.
        """
        _ = system_text
        _ = temperature
        _ = max_output_tokens
        resolved_model = self.resolve_model(tier=tier, model_override=model_override)
        placeholder = f"[stub:{tier}] {user_text}".strip()
        return LLMResponse(text=placeholder, model_used=resolved_model)
