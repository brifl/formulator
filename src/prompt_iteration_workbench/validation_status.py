"""UI-friendly formatting for validation status text."""

from __future__ import annotations

from prompt_iteration_workbench.validators import validate_for_format


def describe_validation_state(output_text: str, output_format: str) -> tuple[str, str]:
    """Return UI-ready validation status and message text for current output."""
    result = validate_for_format(output_text, output_format)
    if not result.applicable:
        return "Validation status: Not applicable", "Validation message: (not applicable for selected format)"
    if result.ok:
        return "Validation status: Valid", "Validation message: None"
    return "Validation status: Invalid", f"Validation message: {result.message}"

