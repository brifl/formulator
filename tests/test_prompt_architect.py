"""Prompt Architect behavior tests."""

from __future__ import annotations

import re

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.llm_client import LLMError, LLMResponse
from prompt_iteration_workbench.models import ProjectState
from prompt_iteration_workbench.prompt_architect import generate_template_for_phase, generate_templates


def _tokens(template_text: str) -> set[str]:
    return set(re.findall(r"\{\{\s*([A-Z0-9_]+)\s*\}\}", template_text))


def test_generate_templates_uses_premium_tier_for_both_phases(monkeypatch) -> None:
    import prompt_iteration_workbench.prompt_architect as architect_module

    monkeypatch.setattr(
        architect_module,
        "get_config",
        lambda: AppConfig(
            openai_api_key="test-key",
            premium_model="test-premium",
            budget_model="test-budget",
        ),
    )

    tiers_seen: list[str] = []

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
        tiers_seen.append(tier)
        if "phase: additive" in user_text.lower():
            text = (
                "Adopt the strongest role profile for this objective. "
                "Create two to four high-impact improvements.\n"
                "If {{CURRENT_OUTPUT}} is empty, write the first draft.\n"
                "If {{CURRENT_OUTPUT}} is non-empty, revise it.\n\n"
                "{{CURRENT_OUTPUT}}"
            )
        else:
            text = (
                "Adopt the strongest role profile for this objective. "
                "Improve by simplifying and rebalancing.\n"
                "If {{CURRENT_OUTPUT}} is empty, write the first draft.\n"
                "If {{CURRENT_OUTPUT}} is non-empty, revise it.\n\n"
                "{{CURRENT_OUTPUT}}"
            )
        return LLMResponse(text=text, model_used="test-premium-model")

    monkeypatch.setattr(architect_module.LLMClient, "generate_text", fake_generate_text)

    state = ProjectState(
        outcome="Outcome",
        requirements_constraints="Requirements",
        special_resources="Resources",
        output_format="Markdown",
    )
    additive_template, reductive_template, notes = generate_templates(state)

    assert tiers_seen == ["premium", "premium"]
    assert "{{CURRENT_OUTPUT}}" in additive_template
    assert "{{CURRENT_OUTPUT}}" in reductive_template
    assert _tokens(additive_template) <= {"CURRENT_OUTPUT"}
    assert _tokens(reductive_template) <= {"CURRENT_OUTPUT"}
    assert "if {{current_output}} is empty" not in additive_template.lower()
    assert "if {{current_output}} is non-empty" not in additive_template.lower()
    assert "if {{current_output}} is empty" not in reductive_template.lower()
    assert "if {{current_output}} is non-empty" not in reductive_template.lower()
    assert "additive: generated" in notes
    assert "reductive: generated" in notes


def test_generate_templates_falls_back_on_low_quality_or_llm_error(monkeypatch) -> None:
    import prompt_iteration_workbench.prompt_architect as architect_module

    monkeypatch.setattr(
        architect_module,
        "get_config",
        lambda: AppConfig(
            openai_api_key="test-key",
            premium_model="test-premium",
            budget_model="test-budget",
        ),
    )

    calls = {"count": 0}

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
        calls["count"] += 1
        if calls["count"] == 1:
            return LLMResponse(
                text="Original content missing. Paste the content to rewrite.",
                model_used="test-premium-model",
            )
        raise LLMError("network issue", "network")

    monkeypatch.setattr(architect_module.LLMClient, "generate_text", fake_generate_text)

    state = ProjectState(
        outcome="Ultimate chili recipe",
        requirements_constraints="Must serve 6 and stay under 60 minutes.",
        special_resources="Pressure cooker",
        output_format="Markdown",
    )
    additive_template, reductive_template, notes = generate_templates(state)

    assert "Original content missing" not in additive_template
    assert "Original content missing" not in reductive_template
    assert "Ultimate chili recipe" in additive_template
    assert "Ultimate chili recipe" in reductive_template
    assert "{{CURRENT_OUTPUT}}" in additive_template
    assert "{{CURRENT_OUTPUT}}" in reductive_template
    assert _tokens(additive_template) <= {"CURRENT_OUTPUT"}
    assert _tokens(reductive_template) <= {"CURRENT_OUTPUT"}
    assert "reductive: fallback (network)" in notes


def test_generate_template_for_phase_only_calls_llm_once(monkeypatch) -> None:
    import prompt_iteration_workbench.prompt_architect as architect_module

    monkeypatch.setattr(
        architect_module,
        "get_config",
        lambda: AppConfig(
            openai_api_key="test-key",
            premium_model="test-premium",
            budget_model="test-budget",
        ),
    )

    calls = {"count": 0}
    tiers_seen: list[str] = []

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
        del self, user_text, system_text, temperature, max_output_tokens, model_override
        calls["count"] += 1
        tiers_seen.append(tier)
        return LLMResponse(
            text="Use a role fitted to the task and improve the draft.\n\n{{CURRENT_OUTPUT}}",
            model_used="test-premium-model",
        )

    monkeypatch.setattr(architect_module.LLMClient, "generate_text", fake_generate_text)

    state = ProjectState(
        outcome="Outcome",
        requirements_constraints="Requirements",
        special_resources="Resources",
        output_format="Markdown",
    )
    template, note = generate_template_for_phase(state, "additive")

    assert calls["count"] == 1
    assert tiers_seen == ["premium"]
    assert "{{CURRENT_OUTPUT}}" in template
    assert _tokens(template) <= {"CURRENT_OUTPUT"}
    assert note == "additive: generated"
