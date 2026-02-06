"""Run-iterations engine behavior tests for checkpoint 7.3."""

from __future__ import annotations

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.engine import run_iterations
from prompt_iteration_workbench.llm_client import LLMResponse
from prompt_iteration_workbench.models import ProjectState


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


def test_run_iterations_executes_two_phase_steps_per_iteration(monkeypatch) -> None:
    _install_fake_llm(monkeypatch)

    state = ProjectState(
        iterations=2,
        additive_prompt_template="{{CURRENT_OUTPUT}}\nWrite additive.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nWrite reductive.",
        current_output="",
    )

    result = run_iterations(state, iterations=2)

    assert result.cancelled is False
    assert result.steps_completed == 4
    assert [record.phase_name for record in result.state.history] == [
        "additive",
        "reductive",
        "additive",
        "reductive",
    ]
    assert [record.phase_step_index for record in result.state.history] == [1, 2, 3, 4]


def test_run_iterations_stops_between_steps_when_cancel_requested(monkeypatch) -> None:
    _install_fake_llm(monkeypatch)

    state = ProjectState(
        iterations=2,
        additive_prompt_template="{{CURRENT_OUTPUT}}\nWrite additive.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nWrite reductive.",
        current_output="",
    )

    stop_requested = {"value": False}

    def should_stop() -> bool:
        return stop_requested["value"]

    def request_stop_after_first_step():
        stop_requested["value"] = True

    import prompt_iteration_workbench.engine as engine_module

    original_run_next_step = engine_module.run_next_step

    def wrapped_run_next_step(*args, **kwargs):
        next_state = original_run_next_step(*args, **kwargs)
        if len(next_state.history) == 1:
            request_stop_after_first_step()
        return next_state

    monkeypatch.setattr(engine_module, "run_next_step", wrapped_run_next_step)

    result = run_iterations(state, iterations=2, should_stop=should_stop)

    assert result.cancelled is True
    assert result.steps_completed == 1
    assert len(result.state.history) == 1
    assert result.state.history[0].phase_name == "additive"
