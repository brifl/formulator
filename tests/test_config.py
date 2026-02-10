"""Configuration parsing tests."""

from __future__ import annotations

import pytest

from prompt_iteration_workbench.config import ConfigError, get_config


def _set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("PREMIUM_LLM_MODEL", "test-premium")
    monkeypatch.setenv("BUDGET_LLM_MODEL", "test-budget")


def _clear_optional_env(monkeypatch) -> None:
    for name in (
        "PREMIUM_LLM_REASONING_EFFORT",
        "BUDGET_LLM_REASONING_EFFORT",
        "ADD_LLM_TEMP",
        "RED_LLM_TEMP",
        "VERBOSE_LLM_LOGGING",
        "VERBOSE_LLM_LOG_MAX_CHARS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_get_config_defaults_verbose_logging_flags(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)
    _clear_optional_env(monkeypatch)

    config = get_config()

    assert config.verbose_llm_logging is False
    assert config.verbose_llm_log_max_chars == 4000


def test_get_config_reads_verbose_logging_flags(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)
    _clear_optional_env(monkeypatch)
    monkeypatch.setenv("VERBOSE_LLM_LOGGING", "true")
    monkeypatch.setenv("VERBOSE_LLM_LOG_MAX_CHARS", "1234")

    config = get_config()

    assert config.verbose_llm_logging is True
    assert config.verbose_llm_log_max_chars == 1234


def test_get_config_rejects_invalid_verbose_bool(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)
    _clear_optional_env(monkeypatch)
    monkeypatch.setenv("VERBOSE_LLM_LOGGING", "maybe")

    with pytest.raises(ConfigError, match="VERBOSE_LLM_LOGGING"):
        get_config()


@pytest.mark.parametrize("value", ["abc", "99"])
def test_get_config_rejects_invalid_verbose_max_chars(monkeypatch, tmp_path, value: str) -> None:
    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)
    _clear_optional_env(monkeypatch)
    monkeypatch.setenv("VERBOSE_LLM_LOG_MAX_CHARS", value)

    with pytest.raises(ConfigError, match="VERBOSE_LLM_LOG_MAX_CHARS"):
        get_config()
