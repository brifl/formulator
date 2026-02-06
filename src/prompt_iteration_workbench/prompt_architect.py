"""Prompt Architect contract for additive and reductive template generation."""

from __future__ import annotations

from prompt_iteration_workbench.models import ProjectState


def generate_templates(state: ProjectState) -> tuple[str, str, str]:
    """Return additive template, reductive template, and optional design notes."""
    format_target = str(state.output_format or "Markdown")
    outcome_summary = str(state.outcome or "No outcome provided.")
    requirements_summary = str(state.requirements_constraints or "No explicit requirements provided.")
    resources_summary = str(state.special_resources or "No explicit special resources provided.")

    additive_template = "\n".join(
        [
            "You are in the additive phase.",
            "Target output format: " + format_target,
            "",
            "Outcome:",
            "{{OUTCOME}}",
            "",
            "Requirements and constraints:",
            "{{REQUIREMENTS}}",
            "",
            "Special resources:",
            "{{SPECIAL_RESOURCES}}",
            "",
            "Allowed phase changes:",
            "{{PHASE_RULES}}",
            "",
            "Current output draft:",
            "{{CURRENT_OUTPUT}}",
            "",
            "Iteration pair index: {{ITERATION_INDEX}}",
            "Phase label: {{PHASE_NAME}}",
            "",
            "Apply additive improvements while preserving valid prior structure.",
        ]
    )

    reductive_template = "\n".join(
        [
            "You are in the reductive phase.",
            "Target output format: " + format_target,
            "",
            "Outcome:",
            "{{OUTCOME}}",
            "",
            "Requirements and constraints:",
            "{{REQUIREMENTS}}",
            "",
            "Special resources:",
            "{{SPECIAL_RESOURCES}}",
            "",
            "Allowed phase changes:",
            "{{PHASE_RULES}}",
            "",
            "Current output draft:",
            "{{CURRENT_OUTPUT}}",
            "",
            "Iteration pair index: {{ITERATION_INDEX}}",
            "Phase label: {{PHASE_NAME}}",
            "",
            "Perform reductive simplification while preserving core correctness.",
        ]
    )

    notes = (
        "Prompt Architect baseline generated. "
        f"Outcome summary: {outcome_summary} "
        f"Requirements summary: {requirements_summary} "
        f"Resources summary: {resources_summary} "
        f"Format target: {format_target}."
    )

    return additive_template, reductive_template, notes
