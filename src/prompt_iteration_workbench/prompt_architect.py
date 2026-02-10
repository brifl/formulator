"""Prompt Architect template generation using the premium LLM tier."""

from __future__ import annotations

import re

from prompt_iteration_workbench.config import AppConfig, get_config
from prompt_iteration_workbench.llm_client import LLMClient, LLMError
from prompt_iteration_workbench.models import ProjectState

PROMPT_ARCHITECT_TIER = "premium"
PROMPT_ARCHITECT_TEMPERATURE = 0.1
PROMPT_ARCHITECT_MAX_OUTPUT_TOKENS = 1200
PROMPT_ARCHITECT_RESPONSE_LAYOUT = (
    "<ADDITIVE_TEMPLATE>\n...\n</ADDITIVE_TEMPLATE>\n"
    "<REDUCTIVE_TEMPLATE>\n...\n</REDUCTIVE_TEMPLATE>\n"
    "<NOTES>\n...\n</NOTES>"
)


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


def _truncate_for_prompt(text: str, *, max_chars: int = 1000) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars].rstrip()} ...[truncated]"


def _build_system_text() -> str:
    return (
        "You are Prompt Architect for an adversarial two-phase iteration workflow.\n"
        "Your job is to produce production-ready prompt templates that drive high-quality outputs.\n\n"
        "Workflow semantics:\n"
        "- Additive phase: expand coverage, strengthen completeness, add concrete details.\n"
        "- Reductive phase: simplify, de-duplicate, tighten, and improve practical usability.\n"
        "- Both phases must preserve critical requirements and selected output format.\n\n"
        "Output contract (strict):\n"
        f"{PROMPT_ARCHITECT_RESPONSE_LAYOUT}\n\n"
        "Hard requirements:\n"
        "1) Return ONLY those 3 tagged sections. No markdown fences. No preface.\n"
        "2) Each template must be a direct instruction prompt for another LLM.\n"
        "3) Both templates must include tokens {{CURRENT_OUTPUT}} and {{PHASE_RULES}}.\n"
        "4) Templates should also leverage {{OUTCOME}}, {{REQUIREMENTS}}, {{SPECIAL_RESOURCES}}, "
        "{{FORMAT}}, {{ITERATION_INDEX}}, and {{PHASE_NAME}}.\n"
        "5) Keep templates actionable and specific; avoid generic motivational language.\n"
        "6) NOTES must be brief and explain major design choices for each phase."
    )


def _build_user_text(state: ProjectState, format_target: str) -> str:
    outcome = str(state.outcome or "No outcome provided.")
    requirements = str(state.requirements_constraints or "No explicit requirements provided.")
    resources = str(state.special_resources or "No explicit special resources provided.")
    additive_rules = str(state.additive_phase_allowed_changes or "(none provided)")
    reductive_rules = str(state.reductive_phase_allowed_changes or "(none provided)")
    current_output_preview = _truncate_for_prompt(str(state.current_output or "(empty)"))
    return (
        "Create additive and reductive prompt templates for this specific project.\n\n"
        f"Outcome:\n{outcome}\n\n"
        f"Requirements and constraints:\n{requirements}\n\n"
        f"Special resources:\n{resources}\n\n"
        f"Additive phase allowed changes:\n{additive_rules}\n\n"
        f"Reductive phase allowed changes:\n{reductive_rules}\n\n"
        f"Target output format:\n{format_target}\n\n"
        "Current output preview (can be empty; used for context only):\n"
        f"{current_output_preview}\n\n"
        "Important: make the additive template aggressively expand useful detail, "
        "and make the reductive template aggressively improve clarity and concision while "
        "preserving correctness and constraints."
    )


def _generate_architect_text(
    *,
    client: LLMClient,
    system_text: str,
    user_text: str,
) -> str:
    # Prompt Architect is always premium regardless of phase-tier runtime settings.
    result = client.generate_text(
        tier=PROMPT_ARCHITECT_TIER,
        system_text=system_text,
        user_text=user_text,
        temperature=PROMPT_ARCHITECT_TEMPERATURE,
        max_output_tokens=PROMPT_ARCHITECT_MAX_OUTPUT_TOKENS,
    )
    return result.text


def _normalize_to_tagged_layout(*, client: LLMClient, raw_text: str) -> str:
    system_text = (
        "Normalize assistant output into an exact 3-section tagged layout.\n"
        f"{PROMPT_ARCHITECT_RESPONSE_LAYOUT}\n"
        "Return only tagged sections. Do not add explanations."
    )
    user_text = (
        "Rewrite the following content into the required tagged layout.\n"
        "Preserve intent and details.\n\n"
        "Original content:\n"
        f"{raw_text}"
    )
    return _generate_architect_text(client=client, system_text=system_text, user_text=user_text)


def resolve_prompt_architect_model() -> str:
    """Resolve the configured model name used for prompt architect generation."""
    return LLMClient(get_config()).resolve_model(PROMPT_ARCHITECT_TIER)


def _build_prompt_architect_config(base: AppConfig) -> AppConfig:
    return AppConfig(
        openai_api_key=base.openai_api_key,
        premium_model=base.premium_model,
        budget_model=base.budget_model,
        premium_reasoning_effort=None,
        budget_reasoning_effort=base.budget_reasoning_effort,
        add_llm_temp=base.add_llm_temp,
        red_llm_temp=base.red_llm_temp,
    )


def generate_templates(state: ProjectState) -> tuple[str, str, str]:
    """Generate additive/reductive templates and notes using premium LLM routing."""
    format_target = str(state.output_format or "Markdown")
    system_text = _build_system_text()
    user_text = _build_user_text(state, format_target)

    config = get_config()
    client = LLMClient(_build_prompt_architect_config(config))
    try:
        raw_text = _generate_architect_text(
            client=client,
            system_text=system_text,
            user_text=user_text,
        )
    except LLMError as exc:
        raise PromptArchitectError(
            f"Prompt Architect generation failed ({exc.category}): {exc.message}"
        ) from exc

    additive_raw = _extract_tagged_section(raw_text, "ADDITIVE_TEMPLATE")
    reductive_raw = _extract_tagged_section(raw_text, "REDUCTIVE_TEMPLATE")
    notes_raw = _extract_tagged_section(raw_text, "NOTES")

    if additive_raw is None or reductive_raw is None:
        try:
            normalized_text = _normalize_to_tagged_layout(client=client, raw_text=raw_text)
        except LLMError as exc:
            raise PromptArchitectError(
                "Prompt Architect returned an invalid response format and normalization failed "
                f"({exc.category}): {exc.message}"
            ) from exc

        additive_raw = _extract_tagged_section(normalized_text, "ADDITIVE_TEMPLATE")
        reductive_raw = _extract_tagged_section(normalized_text, "REDUCTIVE_TEMPLATE")
        notes_raw = _extract_tagged_section(normalized_text, "NOTES")

    if additive_raw is None or reductive_raw is None:
        raw_preview = _truncate_for_prompt(raw_text, max_chars=220)
        raise PromptArchitectError(
            "Prompt Architect returned an invalid response format. "
            "Expected <ADDITIVE_TEMPLATE> and <REDUCTIVE_TEMPLATE> sections. "
            f"Response preview: {raw_preview}"
        )

    additive_template = _normalize_template(additive_raw, format_target)
    reductive_template = _normalize_template(reductive_raw, format_target)
    notes = (notes_raw or "Prompt Architect templates generated.").strip()
    return additive_template, reductive_template, notes
