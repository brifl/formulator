"""Format guidance and context tests for checkpoint 8.0."""

from __future__ import annotations

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.engine import run_next_step
from prompt_iteration_workbench.formats import get_format_guidance
from prompt_iteration_workbench.llm_client import LLMResponse
from prompt_iteration_workbench.models import ProjectState
from prompt_iteration_workbench.prompt_templates import build_context


def _install_capture_llm(monkeypatch):
    import prompt_iteration_workbench.engine as engine_module

    captured: dict[str, str] = {}

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
        return LLMResponse(text='{"ok": true}', model_used="test-budget-model")

    monkeypatch.setattr(engine_module.LLMClient, "generate_text", fake_generate_text)
    return captured


def test_json_guidance_requires_valid_json_without_commentary() -> None:
    guidance = get_format_guidance("JSON")

    assert "valid JSON" in guidance
    assert "Do not include" in guidance


def test_build_context_switches_guidance_by_format() -> None:
    json_state = ProjectState(output_format="JSON")
    markdown_state = ProjectState(output_format="Markdown")

    json_context = build_context(json_state, phase_name="additive", iteration_index=1)
    markdown_context = build_context(markdown_state, phase_name="additive", iteration_index=1)

    assert json_context["FORMAT_GUIDANCE"] == get_format_guidance("JSON")
    assert markdown_context["FORMAT_GUIDANCE"] == get_format_guidance("Markdown")
    assert json_context["FORMAT_GUIDANCE"] != markdown_context["FORMAT_GUIDANCE"]


def test_engine_prepends_guidance_when_template_omits_format(monkeypatch) -> None:
    captured = _install_capture_llm(monkeypatch)

    state = ProjectState(
        output_format="JSON",
        additive_prompt_template="{{CURRENT_OUTPUT}}\nReturn result.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nReturn result.",
    )

    run_next_step(state)

    guidance = get_format_guidance("JSON")
    assert captured["user_text"].startswith(guidance)


def test_engine_does_not_prepend_guidance_when_template_mentions_format(monkeypatch) -> None:
    captured = _install_capture_llm(monkeypatch)

    state = ProjectState(
        output_format="JSON",
        additive_prompt_template="Use JSON format.\n{{CURRENT_OUTPUT}}\nReturn result.",
        reductive_prompt_template="{{CURRENT_OUTPUT}}\nReturn result.",
    )

    run_next_step(state)

    guidance = get_format_guidance("JSON")
    assert captured["user_text"].startswith("Use JSON format.")
    assert not captured["user_text"].startswith(guidance)
