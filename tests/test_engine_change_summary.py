"""Change-summary generation tests for checkpoint 9.2."""

from __future__ import annotations

import pytest

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.engine import generate_change_summary_for_record
from prompt_iteration_workbench.llm_client import LLMResponse
from prompt_iteration_workbench.models import IterationRecord, ProjectState


def _install_fake_summary_llm(monkeypatch, *, summary_text: str, captured: dict[str, str]) -> None:
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
        del self, tier, system_text, temperature, max_output_tokens, model_override
        captured["user_text"] = user_text
        return LLMResponse(text=summary_text, model_used="test-budget-model")

    monkeypatch.setattr(engine_module.LLMClient, "generate_text", fake_generate_text)


def _sample_state() -> ProjectState:
    state = ProjectState(output_format="Text")
    state.history = [
        IterationRecord(
            phase_name="additive",
            iteration_index=1,
            pair_index=1,
            phase_step_index=1,
            output_snapshot="alpha\nbeta\n",
        ),
        IterationRecord(
            phase_name="reductive",
            iteration_index=1,
            pair_index=1,
            phase_step_index=2,
            output_snapshot="alpha\ngamma\n",
        ),
    ]
    return state


def test_generate_change_summary_stores_summary_without_mutating_snapshot(monkeypatch) -> None:
    captured: dict[str, str] = {}
    summary_text = "Paragraph.\n- one\n- two\n- three"
    _install_fake_summary_llm(monkeypatch, summary_text=summary_text, captured=captured)

    state = _sample_state()
    before_snapshot = state.history[1].output_snapshot

    next_state = generate_change_summary_for_record(state, record_index=1)

    assert next_state.history[1].change_summary == summary_text
    assert next_state.history[1].output_snapshot == before_snapshot
    assert state.history[1].change_summary == ""
    assert "Previous output:" in captured["user_text"]
    assert "Current output:" in captured["user_text"]


def test_generate_change_summary_first_record_uses_no_previous_marker(monkeypatch) -> None:
    captured: dict[str, str] = {}
    _install_fake_summary_llm(monkeypatch, summary_text="Paragraph.\n- one\n- two", captured=captured)

    state = _sample_state()
    next_state = generate_change_summary_for_record(state, record_index=0)

    assert next_state.history[0].change_summary
    assert "(no previous output available)" in captured["user_text"]


def test_generate_change_summary_invalid_index_raises() -> None:
    with pytest.raises(IndexError):
        generate_change_summary_for_record(_sample_state(), record_index=99)
