"""LLM client contract, model routing, and normalized API errors."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Literal

from prompt_iteration_workbench.config import AppConfig

ModelTier = Literal["budget", "premium"]
ErrorCategory = Literal["auth", "rate_limit", "network", "invalid_request", "server", "unknown"]

LOGGER = logging.getLogger("prompt_iteration_workbench.llm_client")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response contract for generation calls."""

    text: str
    model_used: str
    request_id: str | None = None
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None


class LLMError(Exception):
    """Normalized error carrying a user-readable message and category."""

    def __init__(self, message: str, category: ErrorCategory) -> None:
        super().__init__(message)
        self.message = message
        self.category = category


class LLMClient:
    """Primary LLM client interface with deterministic model routing."""

    def __init__(self, config: AppConfig, timeout_seconds: float = 30.0, max_retries: int = 2) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)

    def resolve_model(self, tier: ModelTier, model_override: str | None = None) -> str:
        """Resolve a model name from tier selection and optional override."""
        if model_override:
            return model_override
        if tier == "budget":
            return self.config.budget_model
        if tier == "premium":
            return self.config.premium_model
        raise ValueError(f"Unsupported tier: {tier}")

    def resolve_reasoning_effort(self, tier: ModelTier) -> str | None:
        """Resolve reasoning effort for the selected tier."""
        if tier == "budget":
            return self.config.budget_reasoning_effort
        if tier == "premium":
            return self.config.premium_reasoning_effort
        raise ValueError(f"Unsupported tier: {tier}")

    @staticmethod
    def _supports_chat_web_search(model: str) -> bool:
        """Best-effort detection for Chat Completions web-search models."""
        normalized = model.strip().lower()
        return normalized == "gpt-5-search-api" or normalized.endswith("-search-preview")

    def _log_request(
        self,
        *,
        tier: ModelTier,
        model: str,
        system_text: str,
        user_text: str,
        outcome: Literal["success", "error"],
        error_category: ErrorCategory | None,
    ) -> None:
        system_chars = len(system_text)
        user_chars = len(user_text)
        LOGGER.info(
            "llm_request tier=%s model=%s prompt_chars=%d system_chars=%d user_chars=%d outcome=%s error_category=%s",
            tier,
            model,
            system_chars + user_chars,
            system_chars,
            user_chars,
            outcome,
            error_category or "none",
        )

    @staticmethod
    def _extract_token_count(usage: object, primary_key: str, fallback_key: str) -> int | None:
        if usage is None:
            return None
        value = getattr(usage, primary_key, None)
        if value is None:
            value = getattr(usage, fallback_key, None)
        return value if isinstance(value, int) else None

    @staticmethod
    def _compact_error_message(error: BaseException, *, max_chars: int = 320) -> str:
        compact = " ".join(str(error).split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 3]}..."

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
        reasoning_effort = self.resolve_reasoning_effort(tier=tier)

        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
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

        client = OpenAI(api_key=self.config.openai_api_key, timeout=self.timeout_seconds)

        messages: list[dict[str, str]] = []
        if system_text.strip():
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

        for attempt in range(self.max_retries + 1):
            try:
                token_field = "max_completion_tokens"
                include_temperature = True
                include_web_search_options = self._supports_chat_web_search(resolved_model)
                completion = None
                for _ in range(4):
                    request_base: dict[str, object] = {
                        "model": resolved_model,
                        "messages": messages,
                    }
                    if include_web_search_options:
                        request_base["web_search_options"] = {}
                    if reasoning_effort is not None:
                        request_base["reasoning_effort"] = reasoning_effort
                    if include_temperature:
                        request_base["temperature"] = temperature
                    request_base[token_field] = max_output_tokens

                    try:
                        completion = client.chat.completions.create(**request_base)
                        break
                    except BadRequestError as retry_exc:
                        message = str(retry_exc)
                        message_lower = message.lower()
                        changed = False

                        if token_field == "max_completion_tokens" and "max_completion_tokens" in message:
                            token_field = "max_tokens"
                            changed = True
                        elif token_field == "max_tokens" and "max_tokens" in message and "max_completion_tokens" in message:
                            token_field = "max_completion_tokens"
                            changed = True

                        if include_temperature and "temperature" in message and "default (1)" in message:
                            include_temperature = False
                            changed = True

                        if include_web_search_options and "web_search_options" in message_lower:
                            include_web_search_options = False
                            changed = True

                        if not changed:
                            raise
                    except TypeError as retry_exc:
                        message_lower = str(retry_exc).lower()
                        if include_web_search_options and "web_search_options" in message_lower:
                            include_web_search_options = False
                            continue
                        raise
                if completion is None:
                    raise LLMError("Unable to prepare a compatible OpenAI request.", "invalid_request")

                text = completion.choices[0].message.content or ""
                request_id_raw = getattr(completion, "id", None)
                request_id = str(request_id_raw) if request_id_raw is not None else None
                usage = getattr(completion, "usage", None)
                usage_input_tokens = self._extract_token_count(usage, "prompt_tokens", "input_tokens")
                usage_output_tokens = self._extract_token_count(usage, "completion_tokens", "output_tokens")
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="success",
                    error_category=None,
                )
                return LLMResponse(
                    text=text,
                    model_used=resolved_model,
                    request_id=request_id,
                    usage_input_tokens=usage_input_tokens,
                    usage_output_tokens=usage_output_tokens,
                )
            except AuthenticationError as exc:
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category="auth",
                )
                raise LLMError(
                    "Authentication failed. Check OPENAI_API_KEY and model access.",
                    "auth",
                ) from exc
            except BadRequestError as exc:
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category="invalid_request",
                )
                detail = self._compact_error_message(exc)
                raise LLMError(
                    f"Invalid request sent to OpenAI: {detail}",
                    "invalid_request",
                ) from exc
            except RateLimitError as exc:
                if attempt < self.max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category="rate_limit",
                )
                raise LLMError("Rate limit reached. Retry in a moment.", "rate_limit") from exc
            except (APIConnectionError, APITimeoutError) as exc:
                if attempt < self.max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category="network",
                )
                raise LLMError("Network or timeout error while contacting OpenAI.", "network") from exc
            except APIStatusError as exc:
                status_code = getattr(exc, "status_code", None)
                if status_code is not None and status_code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(0.4 * (attempt + 1))
                        continue
                    self._log_request(
                        tier=tier,
                        model=resolved_model,
                        system_text=system_text,
                        user_text=user_text,
                        outcome="error",
                        error_category="server",
                    )
                    raise LLMError("OpenAI server error.", "server") from exc
                detail = self._compact_error_message(exc)
                if status_code is not None and 400 <= status_code < 500:
                    self._log_request(
                        tier=tier,
                        model=resolved_model,
                        system_text=system_text,
                        user_text=user_text,
                        outcome="error",
                        error_category="invalid_request",
                    )
                    raise LLMError(
                        f"OpenAI API error (status {status_code}): {detail}",
                        "invalid_request",
                    ) from exc
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category="unknown",
                )
                if status_code is not None:
                    raise LLMError(
                        f"OpenAI API error (status {status_code}): {detail}",
                        "unknown",
                    ) from exc
                raise LLMError(f"Unexpected OpenAI API error: {detail}", "unknown") from exc
            except LLMError as exc:
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category=exc.category,
                )
                raise
            except Exception as exc:
                self._log_request(
                    tier=tier,
                    model=resolved_model,
                    system_text=system_text,
                    user_text=user_text,
                    outcome="error",
                    error_category="unknown",
                )
                raise LLMError("Unexpected LLM request failure.", "unknown") from exc

        self._log_request(
            tier=tier,
            model=resolved_model,
            system_text=system_text,
            user_text=user_text,
            outcome="error",
            error_category="unknown",
        )
        raise LLMError("Unexpected LLM request failure.", "unknown")
