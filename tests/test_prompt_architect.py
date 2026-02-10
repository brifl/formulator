"""Prompt Architect behavior tests."""

from __future__ import annotations

from prompt_iteration_workbench.config import AppConfig
from prompt_iteration_workbench.llm_client import LLMResponse
from prompt_iteration_workbench.models import ProjectState
from prompt_iteration_workbench.prompt_architect import generate_templates


def test_generate_templates_uses_premium_tier_and_normalizes_invalid_layout(monkeypatch) -> None:
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

    responses = [
        "Here is a malformed response without tags.",
        (
            "<ADDITIVE_TEMPLATE>\n"
            "Use {{CURRENT_OUTPUT}} and {{PHASE_RULES}}.\n"
            "</ADDITIVE_TEMPLATE>\n"
            "<REDUCTIVE_TEMPLATE>\n"
            "Tighten {{CURRENT_OUTPUT}} with {{PHASE_RULES}}.\n"
            "</REDUCTIVE_TEMPLATE>\n"
            "<NOTES>\nNormalized output.\n</NOTES>\n"
        ),
    ]
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
        tiers_seen.append(tier)
        return LLMResponse(text=responses.pop(0), model_used="test-premium-model")

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
    assert "{{PHASE_RULES}}" in additive_template
    assert "{{CURRENT_OUTPUT}}" in reductive_template
    assert "{{PHASE_RULES}}" in reductive_template
    assert "infer and adopt the ideal expert role profile" in additive_template.lower()
    assert "infer and adopt the ideal expert role profile" in reductive_template.lower()
    assert "Normalized output." in notes


def test_generate_templates_replaces_low_quality_placeholder_templates(monkeypatch) -> None:
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

    response_text = (
        "<ADDITIVE_TEMPLATE>\n"
        "Original content missing. Paste the content to rewrite.\n"
        "</ADDITIVE_TEMPLATE>\n"
        "<REDUCTIVE_TEMPLATE>\n"
        "Original content missing. Paste the content to rewrite.\n"
        "</REDUCTIVE_TEMPLATE>\n"
        "<NOTES>\nLow quality mock output.\n</NOTES>\n"
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
        del self, tier, user_text, system_text, temperature, max_output_tokens, model_override
        return LLMResponse(text=response_text, model_used="test-premium-model")

    monkeypatch.setattr(architect_module.LLMClient, "generate_text", fake_generate_text)

    state = ProjectState(
        outcome="Outcome",
        requirements_constraints="Requirements",
        special_resources="Resources",
        output_format="Markdown",
    )
    additive_template, reductive_template, _ = generate_templates(state)

    assert "Original content missing" not in additive_template
    assert "Original content missing" not in reductive_template
    assert "{{OUTCOME}}" in additive_template
    assert "{{OUTCOME}}" in reductive_template
    assert "{{FORMAT}}" in additive_template
    assert "{{FORMAT}}" in reductive_template
    assert "infer and adopt the ideal expert role profile" in additive_template.lower()
    assert "infer and adopt the ideal expert role profile" in reductive_template.lower()
