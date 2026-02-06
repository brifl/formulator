"""Tokenized prompt template helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from prompt_iteration_workbench.formats import get_format_guidance
from prompt_iteration_workbench.models import ProjectState

SUPPORTED_TOKENS: tuple[str, ...] = (
    "OUTCOME",
    "REQUIREMENTS",
    "SPECIAL_RESOURCES",
    "FORMAT",
    "FORMAT_GUIDANCE",
    "PHASE_RULES",
    "CURRENT_OUTPUT",
    "ITERATION_INDEX",
    "PHASE_NAME",
)
_SUPPORTED_TOKEN_SET = set(SUPPORTED_TOKENS)
_TOKEN_PATTERN = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

ADDITIVE_TEMPLATE = ""
REDUCTIVE_TEMPLATE = ""


@dataclass(frozen=True)
class TemplateValidationResult:
    """Validation result for a template string."""

    unknown: set[str]
    missing_required: set[str]


def find_tokens(template_text: str) -> set[str]:
    """Return all token names detected in `{{TOKEN}}` placeholders."""
    return {match.group(1) for match in _TOKEN_PATTERN.finditer(template_text)}


def validate_template(
    template_text: str,
    allowed_tokens: Iterable[str],
    required_tokens: Iterable[str],
) -> TemplateValidationResult:
    """Validate template tokens against allowed and required token sets."""
    found = find_tokens(template_text)
    allowed = set(allowed_tokens)
    required = set(required_tokens)
    unknown = {token for token in found if token not in allowed}
    missing_required = {token for token in required if token not in found}
    return TemplateValidationResult(unknown=unknown, missing_required=missing_required)


def build_context(state: ProjectState, phase_name: str, iteration_index: int) -> dict[str, object]:
    """Build a canonical render context from state and phase metadata."""
    normalized_phase = str(phase_name or "")
    if normalized_phase == "additive":
        phase_rules = str(state.additive_phase_allowed_changes or "")
    elif normalized_phase == "reductive":
        phase_rules = str(state.reductive_phase_allowed_changes or "")
    else:
        phase_rules = ""

    context: dict[str, object] = {token: "" for token in SUPPORTED_TOKENS}
    context.update(
        {
            "OUTCOME": str(state.outcome or ""),
            "REQUIREMENTS": str(state.requirements_constraints or ""),
            "SPECIAL_RESOURCES": str(state.special_resources or ""),
            "FORMAT": str(state.output_format or ""),
            "FORMAT_GUIDANCE": get_format_guidance(str(state.output_format or "Text")),
            "PHASE_RULES": phase_rules,
            "CURRENT_OUTPUT": str(state.current_output or ""),
            "ITERATION_INDEX": int(iteration_index),
            "PHASE_NAME": normalized_phase,
        }
    )
    return context


def render_template(template_text: str, context: Mapping[str, object]) -> str:
    """Render known tokens from context and leave unknown tokens unchanged."""

    def replace(match: re.Match[str]) -> str:
        token_name = match.group(1)
        if token_name not in _SUPPORTED_TOKEN_SET:
            return match.group(0)
        value = context.get(token_name, "")
        if value is None:
            return ""
        return str(value)

    return _TOKEN_PATTERN.sub(replace, template_text)
