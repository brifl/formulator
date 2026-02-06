"""Run-next-step engine behavior tests for checkpoint 7.1."""

from __future__ import annotations

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.engine import run_next_step
from prompt_iteration_workbench.llm_client import LLMResponse
from prompt_iteration_workbench.models import (
    HISTORY_EVENT_PROMPT_ARCHITECT,
    IterationRecord,
    ProjectState,
)


def _install_fake_llm(monkeypatch) -> None:
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
        del self, system_text, temperature, max_output_tokens, model_override
        return LLMResponse(text=f"{tier}:{user_text.splitlines()[-1]}", model_used="test-budget-model")

    monkeypatch.setattr(engine_module.LLMClient, "generate_text", fake_generate_text)


def test_run_next_step_starts_with_additive_then_reductive(monkeypatch) -> None:
    _install_fake_llm(monkeypatch)

    state = ProjectState(
        outcome="Test",
        requirements_constraints="Return OK only.",
        output_format="Text",
        additive_prompt_template="{{CURRENT_OUTPUT}}\nWrite additive OK.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nKeep only reductive OK.",
        current_output="",
    )

    step1 = run_next_step(state)
    assert step1.history[-1].phase_name == "additive"
    assert step1.history[-1].iteration_index == 1
    assert step1.history[-1].phase_step_index == 1
    assert step1.history[-1].model_used == "test-budget-model"

    step2 = run_next_step(step1)
    assert step2.history[-1].phase_name == "reductive"
    assert step2.history[-1].iteration_index == 1
    assert step2.history[-1].phase_step_index == 2
    assert [r.phase_name for r in step2.history[-2:]] == ["additive", "reductive"]


def test_run_next_step_ignores_non_phase_history_events(monkeypatch) -> None:
    _install_fake_llm(monkeypatch)

    state = ProjectState(
        additive_prompt_template="{{CURRENT_OUTPUT}}\nAdd.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nReduce.",
        history=[
            IterationRecord(
                event_type=HISTORY_EVENT_PROMPT_ARCHITECT,
                model_used="gpt-5",
                note_summary="Templates generated.",
            )
        ],
    )

    next_state = run_next_step(state)

    assert next_state.history[-1].phase_name == "additive"
    assert next_state.history[-1].iteration_index == 1
    assert next_state.history[-1].phase_step_index == 1
