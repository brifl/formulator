"""Runtime configuration loading from environment and optional .env file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

REQUIRED_ENV_VARS = ("OPENAI_API_KEY", "PREMIUM_LLM_MODEL", "BUDGET_LLM_MODEL")


class ConfigError(Exception):
    """Configuration loading error with user-facing message text."""


@dataclass(frozen=True)
class AppConfig:
    """Application config contract for model and API settings."""

    openai_api_key: str
    premium_model: str
    budget_model: str
    premium_reasoning_effort: str | None = None
    budget_reasoning_effort: str | None = None
    add_llm_temp: float | None = None
    red_llm_temp: float | None = None

    def __repr__(self) -> str:
        return (
            "AppConfig("
            "openai_api_key='***REDACTED***', "
            f"premium_model={self.premium_model!r}, "
            f"budget_model={self.budget_model!r}, "
            f"premium_reasoning_effort={self.premium_reasoning_effort!r}, "
            f"budget_reasoning_effort={self.budget_reasoning_effort!r}, "
            f"add_llm_temp={self.add_llm_temp!r}, "
            f"red_llm_temp={self.red_llm_temp!r})"
        )


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
        return None

    if value and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return key, value


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    raise KeyError(name)


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _optional_float_env(name: str) -> float | None:
    value = _optional_env(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(
            f"Configuration error: {name} must be a valid float, got {value!r}."
        ) from exc


def get_config() -> AppConfig:
    """Load config from environment variables and `.env` in repo root."""
    _load_dotenv(Path(".env"))

    missing: list[str] = []
    values: dict[str, str] = {}
    for var_name in REQUIRED_ENV_VARS:
        try:
            values[var_name] = _require_env(var_name)
        except KeyError:
            missing.append(var_name)

    if missing:
        missing_text = ", ".join(missing)
        raise ConfigError(
            "Configuration error: missing required environment variables: "
            f"{missing_text}. Set them in your shell or in `.env`."
        )

    return AppConfig(
        openai_api_key=values["OPENAI_API_KEY"],
        premium_model=values["PREMIUM_LLM_MODEL"],
        budget_model=values["BUDGET_LLM_MODEL"],
        premium_reasoning_effort=_optional_env("PREMIUM_LLM_REASONING_EFFORT"),
        budget_reasoning_effort=_optional_env("BUDGET_LLM_REASONING_EFFORT"),
        add_llm_temp=_optional_float_env("ADD_LLM_TEMP"),
        red_llm_temp=_optional_float_env("RED_LLM_TEMP"),
    )
