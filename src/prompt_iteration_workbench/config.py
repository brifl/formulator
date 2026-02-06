"""Runtime configuration loading from environment and optional .env file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

REQUIRED_ENV_VARS = ("OPENAI_API_KEY", "PREMIUM_LLM_MODEL", "BUDGET_LLM_MODEL")


@dataclass(frozen=True)
class AppConfig:
    """Application config contract for model and API settings."""

    openai_api_key: str
    premium_model: str
    budget_model: str

    def __repr__(self) -> str:
        return (
            "AppConfig("
            "openai_api_key='***REDACTED***', "
            f"premium_model={self.premium_model!r}, "
            f"budget_model={self.budget_model!r})"
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
        raise SystemExit(
            "Configuration error: missing required environment variables: "
            f"{missing_text}. Set them in your shell or in `.env`."
        )

    return AppConfig(
        openai_api_key=values["OPENAI_API_KEY"],
        premium_model=values["PREMIUM_LLM_MODEL"],
        budget_model=values["BUDGET_LLM_MODEL"],
    )
