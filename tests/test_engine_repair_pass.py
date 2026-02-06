"""Conditional repair-pass tests for checkpoint 8.2."""

from __future__ import annotations

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.engine import run_next_step
from prompt_iteration_workbench.llm_client import LLMResponse
from prompt_iteration_workbench.models import (
    HISTORY_EVENT_PHASE_STEP,
    HISTORY_EVENT_REPAIR,
    ProjectState,
    format_history_label,
)
from prompt_iteration_workbench.validators import validate_json


def _install_fake_llm(monkeypatch, outputs: list[str]) -> None:
    import prompt_iteration_workbench.engine as engine_module

    monkeypatch.setattr(
        engine_module,
        "get_config",
        lambda: AppConfig(
            openai_api_key="test-key",
            premium_model="test-premium",
            budget_model="test-budget",
        ),
    )

    counter = {"index": 0}

    def fake_generate_text(
        self,
        *,
        tier,
        user_text,
        system_text="",
        temperature=0.2,
        max_output_tokens=512,
        model_override=None,
    ):
        del self, tier, user_text, system_text, temperature, max_output_tokens, model_override
        idx = counter["index"]
        counter["index"] += 1
        return LLMResponse(text=outputs[idx], model_used="test-budget-model")

    monkeypatch.setattr(engine_module.LLMClient, "generate_text", fake_generate_text)


def test_run_next_step_attempts_and_records_repair_for_invalid_json(monkeypatch) -> None:
    _install_fake_llm(monkeypatch, outputs=['{"broken":', '{"fixed": true}'])

    state = ProjectState(
        output_format="JSON",
        additive_prompt_template="{{CURRENT_OUTPUT}}\nReturn JSON.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nReturn JSON.",
    )

    next_state = run_next_step(state)

    assert len(next_state.history) == 2
    assert next_state.history[0].event_type == HISTORY_EVENT_PHASE_STEP
    assert next_state.history[1].event_type == HISTORY_EVENT_REPAIR
    assert format_history_label(next_state.history[1]) == "repair event - structural validation retry"
    assert validate_json(next_state.current_output).ok is True


def test_run_next_step_skips_repair_when_initial_output_is_valid(monkeypatch) -> None:
    _install_fake_llm(monkeypatch, outputs=['{"ok": true}'])

    state = ProjectState(
        output_format="JSON",
        additive_prompt_template="{{CURRENT_OUTPUT}}\nReturn JSON.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nReturn JSON.",
    )

    next_state = run_next_step(state)

    assert len(next_state.history) == 1
    assert next_state.history[0].event_type == HISTORY_EVENT_PHASE_STEP
    assert validate_json(next_state.current_output).ok is True
