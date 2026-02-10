"""Live E2E repro for Generate Prompts using saved projects and .env config."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from prompt_iteration_workbench.config import get_config
from prompt_iteration_workbench.persistence import load_project
from prompt_iteration_workbench.prompt_architect import generate_templates

RUN_FLAG = "RUN_LIVE_E2E_GENERATE_PROMPTS"
PROJECT_PATH_ENV = "LIVE_E2E_PROJECT_PATH"
E2E_LOG_PATH = Path("logs/e2e_generate_prompts_live.log")
DOTENV_KEYS = (
    "OPENAI_API_KEY",
    "PREMIUM_LLM_MODEL",
    "BUDGET_LLM_MODEL",
    "PREMIUM_LLM_REASONING_EFFORT",
    "BUDGET_LLM_REASONING_EFFORT",
    "ADD_LLM_TEMP",
    "RED_LLM_TEMP",
)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = raw_value.strip()
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _apply_dotenv_values_to_environment(dotenv_values: dict[str, str]) -> None:
    for key in DOTENV_KEYS:
        if key in dotenv_values:
            os.environ[key] = dotenv_values[key]
        else:
            os.environ.pop(key, None)


def _resolve_project_path() -> Path:
    explicit = os.environ.get(PROJECT_PATH_ENV, "").strip()
    if explicit:
        return Path(explicit)

    candidates = sorted(Path("projects").glob("*.json"))
    if not candidates:
        raise FileNotFoundError("No project files found under projects/*.json.")
    return candidates[-1]


def _configure_loggers(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    e2e_logger = logging.getLogger("prompt_iteration_workbench.e2e.generate_prompts")
    if not e2e_logger.handlers:
        e2e_handler = logging.FileHandler(log_path, encoding="utf-8")
        e2e_handler.setFormatter(formatter)
        e2e_logger.addHandler(e2e_handler)
    e2e_logger.setLevel(logging.INFO)
    e2e_logger.propagate = False

    llm_logger = logging.getLogger("prompt_iteration_workbench.llm_client")
    if not any(
        isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path
        for handler in llm_logger.handlers
    ):
        llm_handler = logging.FileHandler(log_path, encoding="utf-8")
        llm_handler.setFormatter(formatter)
        llm_logger.addHandler(llm_handler)

    return e2e_logger


def test_live_generate_prompts_saved_project() -> None:
    """Run live Prompt Architect generation against a saved project for repro diagnostics."""
    if not _is_truthy(os.environ.get(RUN_FLAG)):
        pytest.skip(f"Set {RUN_FLAG}=1 to run this live E2E test.")

    logger = _configure_loggers(E2E_LOG_PATH)
    logger.info("Starting live E2E Generate Prompts test.")

    dotenv_path = Path(".env")
    if not dotenv_path.exists():
        pytest.fail("Missing .env file for live E2E test.")

    dotenv_values = _load_dotenv_values(dotenv_path)
    _apply_dotenv_values_to_environment(dotenv_values)

    missing_required = [
        key for key in ("OPENAI_API_KEY", "PREMIUM_LLM_MODEL", "BUDGET_LLM_MODEL") if not dotenv_values.get(key, "")
    ]
    if missing_required:
        pytest.fail(f"Missing required .env values for live test: {', '.join(missing_required)}")

    config = get_config()
    logger.info(
        "Config snapshot premium_model=%s budget_model=%s premium_reasoning=%s budget_reasoning=%s add_temp=%s red_temp=%s",
        config.premium_model,
        config.budget_model,
        "set" if config.premium_reasoning_effort else "unset",
        "set" if config.budget_reasoning_effort else "unset",
        config.add_llm_temp,
        config.red_llm_temp,
    )

    project_path = _resolve_project_path()
    if not project_path.exists():
        pytest.fail(f"Saved project not found: {project_path}")

    state = load_project(project_path)
    logger.info(
        "Loaded project path=%s outcome_chars=%d requirements_chars=%d resources_chars=%d format=%s history_entries=%d",
        project_path,
        len(state.outcome),
        len(state.requirements_constraints),
        len(state.special_resources),
        state.output_format,
        len(state.history),
    )

    try:
        additive_template, reductive_template, notes = generate_templates(state)
    except Exception as exc:
        logger.exception("Live generate_templates call failed.")
        pytest.fail(
            "Live generate_templates failed with "
            f"{type(exc).__name__}: {exc}. See {E2E_LOG_PATH} for details."
        )

    logger.info(
        "Live generate_templates succeeded additive_chars=%d reductive_chars=%d notes_chars=%d",
        len(additive_template),
        len(reductive_template),
        len(notes),
    )
    assert additive_template.strip()
    assert reductive_template.strip()
    assert "{{CURRENT_OUTPUT}}" in additive_template
    assert "{{PHASE_RULES}}" in additive_template
    assert "{{CURRENT_OUTPUT}}" in reductive_template
    assert "{{PHASE_RULES}}" in reductive_template
