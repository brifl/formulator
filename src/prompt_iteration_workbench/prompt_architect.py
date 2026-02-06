"""Prompt Architect template generation using the premium LLM tier."""

from __future__ import annotations

import re

from prompt_iteration_workbench.config import get_config
from prompt_iteration_workbench.llm_client import LLMClient, LLMError
from prompt_iteration_workbench.models import ProjectState


class PromptArchitectError(Exception):
    """UI-safe prompt architect failure with normalized message text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _extract_tagged_section(text: str, tag: str) -> str | None:
    pattern = re.compile(rf"<{tag}>\s*(.*?)\s*</{tag}>", flags=re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _normalize_template(template_text: str, format_target: str) -> str:
    cleaned = template_text.strip()
    if not cleaned:
        cleaned = "Template generation returned empty content."
    if format_target.lower() not in cleaned.lower():
        cleaned = f"Target output format: {format_target}\n\n{cleaned}"
    if "{{PHASE_RULES}}" not in cleaned:
        cleaned = f"{cleaned}\n\nAllowed phase changes:\n{{{{PHASE_RULES}}}}"
    if "{{CURRENT_OUTPUT}}" not in cleaned:
        cleaned = f"{cleaned}\n\nCurrent output draft:\n{{{{CURRENT_OUTPUT}}}}"
    return cleaned


def generate_templates(state: ProjectState) -> tuple[str, str, str]:
    """Generate additive/reductive templates and notes using premium LLM routing."""
    format_target = str(state.output_format or "Markdown")
    outcome = str(state.outcome or "No outcome provided.")
    requirements = str(state.requirements_constraints or "No explicit requirements provided.")
    resources = str(state.special_resources or "No explicit special resources provided.")

    system_text = (
        "You are Prompt Architect. Return ONLY tagged sections in this exact layout:\n"
        "<ADDITIVE_TEMPLATE>\n...\n</ADDITIVE_TEMPLATE>\n"
        "<REDUCTIVE_TEMPLATE>\n...\n</REDUCTIVE_TEMPLATE>\n"
        "<NOTES>\n...\n</NOTES>\n\n"
        "Both templates must include tokens {{CURRENT_OUTPUT}} and {{PHASE_RULES}}. "
        "Also use tokens {{OUTCOME}}, {{REQUIREMENTS}}, {{SPECIAL_RESOURCES}}, "
        "{{FORMAT}}, {{ITERATION_INDEX}}, and {{PHASE_NAME}} where appropriate."
    )
    user_text = (
        "Create additive and reductive prompt templates for this project.\n"
        f"Outcome: {outcome}\n"
        f"Requirements and constraints: {requirements}\n"
        f"Special resources: {resources}\n"
        f"Target output format: {format_target}\n"
        "Keep templates concise, practical, and immediately usable."
    )

    client = LLMClient(get_config())
    try:
        result = client.generate_text(
            tier="premium",
            system_text=system_text,
            user_text=user_text,
            temperature=0.2,
            max_output_tokens=1200,
        )
    except LLMError as exc:
        raise PromptArchitectError(
            f"Prompt Architect generation failed ({exc.category}): {exc.message}"
        ) from exc

    additive_raw = _extract_tagged_section(result.text, "ADDITIVE_TEMPLATE")
    reductive_raw = _extract_tagged_section(result.text, "REDUCTIVE_TEMPLATE")
    notes_raw = _extract_tagged_section(result.text, "NOTES")

    if additive_raw is None or reductive_raw is None:
        raise PromptArchitectError(
            "Prompt Architect returned an invalid response format. "
            "Expected <ADDITIVE_TEMPLATE> and <REDUCTIVE_TEMPLATE> sections."
        )

    additive_template = _normalize_template(additive_raw, format_target)
    reductive_template = _normalize_template(reductive_raw, format_target)
    notes = (notes_raw or "Prompt Architect templates generated.").strip()
    return additive_template, reductive_template, notes
