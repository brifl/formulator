"""Prompt Architect template generation using the premium LLM tier."""

from __future__ import annotations

import re

from prompt_iteration_workbench.config import AppConfig, get_config
from prompt_iteration_workbench.formats import get_format_guidance
from prompt_iteration_workbench.llm_client import LLMClient, LLMError
from prompt_iteration_workbench.models import ProjectState
from prompt_iteration_workbench.prompt_templates import EMPTY_CURRENT_OUTPUT_PLACEHOLDER

PROMPT_ARCHITECT_TIER = "premium"
PROMPT_ARCHITECT_TEMPERATURE = 0.2
PROMPT_ARCHITECT_MAX_OUTPUT_TOKENS = 1200
LOW_QUALITY_MARKERS = (
    "original content missing",
    "original content was not provided",
    "paste the content to rewrite",
    "paste content to rewrite",
    "paste the text you want rewritten",
    "provide the content to rewrite",
    "text you want rewritten",
    "input missing",
    "tagged layout",
    "template generation returned empty content",
)
TOKEN_PATTERN = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


class PromptArchitectError(Exception):
    """UI-safe prompt architect failure with normalized message text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _truncate_for_prompt(text: str, *, max_chars: int = 1200) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars].rstrip()} ...[truncated]"


def _strip_code_fences(text: str) -> str:
    stripped = str(text or "").strip()
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _contains_low_quality_markers(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in LOW_QUALITY_MARKERS)


def _remove_empty_branching_lines(text: str) -> str:
    blocked_markers = (
        "if {{current_output}} is empty",
        "if {{current_output}} is non-empty",
        "if {{current_output}} is nonempty",
        "if current_output is empty",
        "if current_output is non-empty",
        "if current_output is nonempty",
    )
    kept_lines: list[str] = []
    for line in str(text or "").splitlines():
        lower_line = line.strip().lower()
        if any(marker in lower_line for marker in blocked_markers):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def _phase_rules_for(state: ProjectState, phase_name: str) -> str:
    if phase_name == "additive":
        return str(state.additive_phase_allowed_changes or "").strip()
    if phase_name == "reductive":
        return str(state.reductive_phase_allowed_changes or "").strip()
    raise ValueError(f"Unsupported phase name: {phase_name}")


def _replace_known_tokens(
    *,
    template_text: str,
    state: ProjectState,
    phase_name: str,
    format_target: str,
) -> str:
    replacements = {
        "OUTCOME": str(state.outcome or "").strip(),
        "REQUIREMENTS": str(state.requirements_constraints or "").strip(),
        "SPECIAL_RESOURCES": str(state.special_resources or "").strip(),
        "FORMAT": format_target,
        "FORMAT_GUIDANCE": get_format_guidance(format_target),
        "PHASE_RULES": _phase_rules_for(state, phase_name),
        "PHASE_NAME": phase_name,
    }

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "CURRENT_OUTPUT":
            return match.group(0)
        value = replacements.get(token)
        if value is None:
            return match.group(0)
        return value

    return TOKEN_PATTERN.sub(replace, template_text)


def _build_seed_template(state: ProjectState, phase_name: str, format_target: str) -> str:
    outcome = str(state.outcome or "").strip() or "(No outcome provided.)"
    requirements = str(state.requirements_constraints or "").strip()
    resources = str(state.special_resources or "").strip()
    phase_rules = _phase_rules_for(state, phase_name)

    if phase_name == "additive":
        phase_step = "Suggest two to four of the most significant improvements."
        draft_intro = (
            "The current best draft is below. "
            f"On the first additive run it may be the literal placeholder '{EMPTY_CURRENT_OUTPUT_PLACEHOLDER}'."
        )
    elif phase_name == "reductive":
        phase_step = (
            "Suggest two to four of the most significant improvements by removing, "
            "rebalancing, or simplifying."
        )
        draft_intro = "The current best draft from the additive phase is below."
    else:
        raise ValueError(f"Unsupported phase name: {phase_name}")

    lines = [
        "You are an expert in attaining our desired outcome. We are incrementally working toward perfection on the following:",
        outcome,
    ]

    if requirements:
        lines.extend(
            [
                "",
                "There are requirements and constraints listed below that must be honored in the final result:",
                requirements,
            ]
        )

    if resources:
        lines.extend(
            [
                "",
                "The user called out special resources that may be useful, but they are not mandatory:",
                resources,
            ]
        )

    if phase_rules:
        lines.extend(["", "Allowed changes for this phase:", phase_rules])

    lines.extend(
        [
            "",
            draft_intro,
            phase_step,
            "",
            f"Make sure the output is clean and in the following format: {format_target}",
            get_format_guidance(format_target),
            "Return only the final result in the correct format with no explanatory text.",
            "",
            "{{CURRENT_OUTPUT}}",
        ]
    )

    return "\n".join(lines).strip()


def _build_architect_request(*, seed_template: str, phase_name: str) -> str:
    if phase_name == "additive":
        phase_instruction = (
            "Additive phase: guide the execution model to make two to four high-impact improvements; "
            "creative additions are allowed when clearly justified."
        )
    elif phase_name == "reductive":
        phase_instruction = (
            "Reductive phase: guide the execution model to improve by removing, rebalancing, or simplifying; "
            "avoid net-new additions unless required by constraints. "
            "Assume this phase receives a non-empty draft from the additive step."
        )
    else:
        raise ValueError(f"Unsupported phase name: {phase_name}")

    return (
        "I want you to improve the following prompt template.\n"
        "The execution model should be inspired to creativity and precision by assigning an appropriate role.\n"
        "Make it clear, specific, and well-fitted to the task.\n\n"
        "Hard requirements for your rewritten prompt:\n"
        "1) Keep the literal token {{CURRENT_OUTPUT}} exactly as written.\n"
        "2) Do not include other template tokens like {{OUTCOME}}, {{REQUIREMENTS}}, {{SPECIAL_RESOURCES}}, {{FORMAT}}, or {{PHASE_RULES}}.\n"
        "3) Do not call the role simply 'an expert'; choose the role profile that best fits the objective.\n"
        "4) Do not refer to the deliverable generically as 'outcome'; use domain-appropriate language.\n"
        "5) Runtime will always inject a 'Current draft' block with {{CURRENT_OUTPUT}}. "
        f"If there is no draft yet, it injects the literal placeholder '{EMPTY_CURRENT_OUTPUT_PLACEHOLDER}'.\n"
        "6) Do not add explicit empty/non-empty branching text; keep one clean instruction flow.\n"
        "7) Normalize objective/constraints/resources/phase-rules presentation into cohesive formatting "
        "(consistent casing, heading style, and list style) while preserving meaning.\n"
        f"8) {phase_instruction}\n"
        "9) If tools such as web search are available, instruct the model to use them when it improves correctness.\n"
        "10) Keep the prompt concise and actionable. Avoid boilerplate.\n"
        "11) Return only the rewritten prompt text. No commentary and no markdown fences.\n\n"
        "Prompt template to improve:\n"
        "```text\n"
        f"{seed_template}\n"
        "```"
    )


def _build_fallback_template(state: ProjectState, phase_name: str, format_target: str) -> str:
    outcome = str(state.outcome or "").strip() or "(No outcome provided.)"
    requirements = str(state.requirements_constraints or "").strip()
    resources = str(state.special_resources or "").strip()
    phase_rules = _phase_rules_for(state, phase_name)

    if phase_name == "additive":
        phase_instruction = (
            "Make two to four of the most significant improvements. "
            f"The literal marker '{EMPTY_CURRENT_OUTPUT_PLACEHOLDER}' means there is no prior draft yet."
        )
    else:
        phase_instruction = (
            "Make two to four of the most significant improvements by removing, rebalancing, or simplifying. "
            "Avoid net-new additions unless a constraint requires them. "
            "Assume this phase operates on an existing additive draft."
        )

    lines = [
        "Before writing, infer and adopt the ideal expert role profile for this objective.",
        "Choose the disciplines and depth that best fit the task.",
        "",
        "Objective:",
        outcome,
    ]

    if requirements:
        lines.extend(["", "Requirements and constraints:", requirements])

    if resources:
        lines.extend(["", "Special resources that may help (not mandatory):", resources])

    lines.extend(["", f"Target output format: {format_target}", get_format_guidance(format_target)])

    if phase_rules:
        lines.extend(["", "Allowed changes for this phase:", phase_rules])

    lines.extend(
        [
            "",
            phase_instruction,
            "",
            "Current draft:",
            "{{CURRENT_OUTPUT}}",
            "",
            "Return only the final output in the target format and no explanatory text.",
        ]
    )

    return "\n".join(lines).strip()


def _finalize_generated_template(
    *,
    raw_text: str,
    state: ProjectState,
    phase_name: str,
    format_target: str,
) -> str:
    cleaned = _replace_known_tokens(
        template_text=_strip_code_fences(raw_text),
        state=state,
        phase_name=phase_name,
        format_target=format_target,
    ).strip()
    cleaned = _remove_empty_branching_lines(cleaned)

    if not cleaned or _contains_low_quality_markers(cleaned):
        return _build_fallback_template(state, phase_name, format_target)

    remaining_tokens = {match.group(1) for match in TOKEN_PATTERN.finditer(cleaned)}
    remaining_tokens.discard("CURRENT_OUTPUT")
    if remaining_tokens:
        return _build_fallback_template(state, phase_name, format_target)

    if "{{CURRENT_OUTPUT}}" not in cleaned:
        cleaned = f"{cleaned}\n\nCurrent draft:\n{{{{CURRENT_OUTPUT}}}}"

    return cleaned


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


def _generate_phase_template(
    *,
    client: LLMClient,
    state: ProjectState,
    phase_name: str,
    format_target: str,
) -> str:
    seed_template = _build_seed_template(state, phase_name, format_target)
    user_text = _build_architect_request(seed_template=seed_template, phase_name=phase_name)
    result = client.generate_text(
        tier=PROMPT_ARCHITECT_TIER,
        system_text=(
            "You are a senior prompt engineer. "
            "Return only the rewritten prompt template requested by the user."
        ),
        user_text=user_text,
        temperature=PROMPT_ARCHITECT_TEMPERATURE,
        max_output_tokens=PROMPT_ARCHITECT_MAX_OUTPUT_TOKENS,
    )
    return _finalize_generated_template(
        raw_text=result.text,
        state=state,
        phase_name=phase_name,
        format_target=format_target,
    )


def _generate_phase_template_with_fallback(
    *,
    client: LLMClient,
    state: ProjectState,
    phase_name: str,
    format_target: str,
) -> tuple[str, str]:
    try:
        template = _generate_phase_template(
            client=client,
            state=state,
            phase_name=phase_name,
            format_target=format_target,
        )
        return template, f"{phase_name}: generated"
    except LLMError as exc:
        fallback = _build_fallback_template(state, phase_name, format_target)
        return fallback, f"{phase_name}: fallback ({exc.category})"


def generate_template_for_phase(state: ProjectState, phase_name: str) -> tuple[str, str]:
    """Generate one phase template using premium routing and fallback on LLM errors."""
    if phase_name not in {"additive", "reductive"}:
        raise PromptArchitectError(f"Unsupported phase name: {phase_name}")

    format_target = str(state.output_format or "Markdown")
    config = get_config()
    client = LLMClient(_build_prompt_architect_config(config))
    template, note = _generate_phase_template_with_fallback(
        client=client,
        state=state,
        phase_name=phase_name,
        format_target=format_target,
    )
    if not template.strip():
        raise PromptArchitectError(f"Prompt Architect returned an empty {phase_name} template.")
    return template, note


def generate_templates(state: ProjectState) -> tuple[str, str, str]:
    """Generate additive/reductive templates and notes using premium LLM routing."""
    format_target = str(state.output_format or "Markdown")

    config = get_config()
    client = LLMClient(_build_prompt_architect_config(config))

    additive_template, additive_note = _generate_phase_template_with_fallback(
        client=client,
        state=state,
        phase_name="additive",
        format_target=format_target,
    )
    reductive_template, reductive_note = _generate_phase_template_with_fallback(
        client=client,
        state=state,
        phase_name="reductive",
        format_target=format_target,
    )

    if not additive_template.strip() or not reductive_template.strip():
        raise PromptArchitectError("Prompt Architect returned empty prompt templates.")

    return additive_template, reductive_template, "; ".join([additive_note, reductive_note])
