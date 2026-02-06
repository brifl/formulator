"""Tokenized prompt template helpers."""

from __future__ import annotations

import re
from typing import Mapping

SUPPORTED_TOKENS: tuple[str, ...] = (
    "OUTCOME",
    "REQUIREMENTS",
    "SPECIAL_RESOURCES",
    "FORMAT",
    "PHASE_RULES",
    "CURRENT_OUTPUT",
    "ITERATION_INDEX",
    "PHASE_NAME",
)
_SUPPORTED_TOKEN_SET = set(SUPPORTED_TOKENS)
_TOKEN_PATTERN = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

ADDITIVE_TEMPLATE = ""
REDUCTIVE_TEMPLATE = ""


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
