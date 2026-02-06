"""Iteration engine planning semantics for additive/reductive loops."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from prompt_iteration_workbench.config import get_config
from prompt_iteration_workbench.formats import get_format_guidance
from prompt_iteration_workbench.llm_client import LLMClient, ModelTier
from prompt_iteration_workbench.models import (
    HISTORY_EVENT_PHASE_STEP,
    IterationRecord,
    ProjectState,
    make_repair_event,
)
from prompt_iteration_workbench.prompt_templates import build_context, render_template
from prompt_iteration_workbench.validators import validate_for_format

PHASE_SEQUENCE = ("additive", "reductive")


@dataclass(frozen=True)
class RunOptions:
    """Run options for planning and execution stages of the engine."""

    iterations_override: int | None = None


@dataclass(frozen=True)
class RunPlan:
    """Normalized run configuration and planned phase steps."""

    state: ProjectState
    steps: tuple[IterationRecord, ...]


@dataclass(frozen=True)
class RunIterationsResult:
    """Result for multi-step iteration runs."""

    state: ProjectState
    steps_completed: int
    cancelled: bool


def normalize_iterations(state: ProjectState, options: RunOptions | None = None) -> int:
    """Resolve iteration count from state + options and enforce minimum value."""
    if options is not None and options.iterations_override is not None:
        iterations_raw = options.iterations_override
    else:
        iterations_raw = state.iterations
    iterations = int(iterations_raw)
    if iterations < 1:
        raise ValueError("Iterations must be >= 1.")
    return iterations


def apply_run_options(state: ProjectState, options: RunOptions | None = None) -> ProjectState:
    """Return a copy of ProjectState with normalized run options applied."""
    normalized_iterations = normalize_iterations(state, options)
    return ProjectState(
        schema_version=state.schema_version,
        outcome=state.outcome,
        requirements_constraints=state.requirements_constraints,
        special_resources=state.special_resources,
        iterations=normalized_iterations,
        output_format=state.output_format,
        additive_phase_allowed_changes=state.additive_phase_allowed_changes,
        reductive_phase_allowed_changes=state.reductive_phase_allowed_changes,
        additive_prompt_template=state.additive_prompt_template,
        reductive_prompt_template=state.reductive_prompt_template,
        current_output=state.current_output,
        history=[IterationRecord(**record.__dict__) for record in state.history],
    )


def plan_steps(state: ProjectState, options: RunOptions | None = None) -> list[IterationRecord]:
    """Plan phase steps for the configured number of iterations.

    Semantics:
    - One iteration equals two phase steps: additive, then reductive.
    - Iterations = N always plans 2N phase steps in that fixed order.
    - iteration_index is the 1-based pair number.
    - phase_step_index is the 1-based global phase-step number across the run.
    """
    planned_state = apply_run_options(state, options)
    steps: list[IterationRecord] = []
    phase_step_index = 0
    for iteration_index in range(1, planned_state.iterations + 1):
        for phase_name in PHASE_SEQUENCE:
            phase_step_index += 1
            steps.append(
                IterationRecord(
                    event_type=HISTORY_EVENT_PHASE_STEP,
                    iteration_index=iteration_index,
                    pair_index=iteration_index,
                    phase_step_index=phase_step_index,
                    phase_name=phase_name,
                )
            )
    return steps


def build_run_plan(state: ProjectState, options: RunOptions | None = None) -> RunPlan:
    """Build a normalized run plan from project state and run options."""
    normalized_state = apply_run_options(state, options)
    return RunPlan(state=normalized_state, steps=tuple(plan_steps(normalized_state)))


def phase_step_history(records: list[IterationRecord]) -> list[IterationRecord]:
    """Return additive/reductive phase-step records in stored order."""
    return [
        record
        for record in records
        if record.event_type == HISTORY_EVENT_PHASE_STEP and record.phase_name in PHASE_SEQUENCE
    ]


def _next_phase_metadata(state: ProjectState) -> tuple[str, int, int]:
    phase_records = phase_step_history(state.history)
    next_phase_step_index = len(phase_records) + 1
    next_iteration_index = (next_phase_step_index + 1) // 2
    next_phase_name = PHASE_SEQUENCE[(next_phase_step_index - 1) % len(PHASE_SEQUENCE)]
    return next_phase_name, next_iteration_index, next_phase_step_index


def _template_for_phase(state: ProjectState, phase_name: str) -> str:
    if phase_name == "additive":
        template_text = str(state.additive_prompt_template or "")
    elif phase_name == "reductive":
        template_text = str(state.reductive_prompt_template or "")
    else:
        raise ValueError(f"Unsupported phase name: {phase_name}")

    if not template_text.strip():
        raise ValueError(f"{phase_name.title()} prompt template is empty.")
    return template_text


def _template_mentions_format(template_text: str, output_format: str) -> bool:
    normalized_template = template_text.upper()
    normalized_format = str(output_format or "").strip().upper()
    if "{{FORMAT}}" in normalized_template or "{{FORMAT_GUIDANCE}}" in normalized_template:
        return True
    if normalized_format and normalized_format in normalized_template:
        return True
    return False


def _build_repair_prompt(*, output_text: str, output_format: str, validation_message: str) -> str:
    normalized_format = str(output_format or "TEXT").strip() or "TEXT"
    guidance = get_format_guidance(normalized_format)
    return (
        "The output below failed structural validation.\n"
        f"Target format: {normalized_format}\n"
        f"Validation error: {validation_message}\n\n"
        "Rewrite the output to preserve the same content intent while fixing structure.\n"
        "Return only the repaired output.\n\n"
        f"{guidance}\n\n"
        "Original output:\n"
        f"{output_text}"
    )


def _attempt_structural_repair(
    *,
    client: LLMClient,
    output_text: str,
    output_format: str,
    validation_message: str,
) -> tuple[str, IterationRecord]:
    repair_prompt = _build_repair_prompt(
        output_text=output_text,
        output_format=output_format,
        validation_message=validation_message,
    )
    repair_result = client.generate_text(
        tier="budget",
        system_text="",
        user_text=repair_prompt,
        temperature=0.1,
        max_output_tokens=1200,
    )
    repaired_validation = validate_for_format(repair_result.text, output_format)
    if repaired_validation.ok:
        note = f"Repair succeeded: {repaired_validation.message}"
        return (
            repair_result.text,
            make_repair_event(
                model_used=repair_result.model_used,
                note_summary=note,
                prompt_rendered=repair_prompt,
                output_snapshot=repair_result.text,
            ),
        )
    note = (
        "Repair attempted but output is still invalid: "
        f"{repaired_validation.message}"
    )
    return (
        output_text,
        make_repair_event(
            model_used=repair_result.model_used,
            note_summary=note,
            prompt_rendered=repair_prompt,
            output_snapshot=repair_result.text,
        ),
    )


def run_next_step(state: ProjectState, *, tier: ModelTier = "budget") -> ProjectState:
    """Execute one phase step and append the resulting history record."""
    phase_name, iteration_index, phase_step_index = _next_phase_metadata(state)
    template_text = _template_for_phase(state, phase_name)
    context = build_context(state=state, phase_name=phase_name, iteration_index=iteration_index)
    prompt_rendered = render_template(template_text, context)
    if not _template_mentions_format(template_text, state.output_format):
        prompt_rendered = f"{get_format_guidance(state.output_format)}\n\n{prompt_rendered}"

    client = LLMClient(get_config())
    result = client.generate_text(
        tier=tier,
        system_text="",
        user_text=prompt_rendered,
        temperature=0.2,
        max_output_tokens=1200,
    )
    validation = validate_for_format(result.text, state.output_format)

    next_state = apply_run_options(state)
    next_state.current_output = result.text
    next_state.history.append(
        IterationRecord(
            event_type=HISTORY_EVENT_PHASE_STEP,
            iteration_index=iteration_index,
            pair_index=iteration_index,
            phase_step_index=phase_step_index,
            phase_name=phase_name,
            model_used=result.model_used,
            note_summary=validation.message if validation.applicable else "",
            prompt_rendered=prompt_rendered,
            output_snapshot=result.text,
        )
    )
    if validation.applicable and not validation.ok:
        repaired_output, repair_event = _attempt_structural_repair(
            client=client,
            output_text=result.text,
            output_format=state.output_format,
            validation_message=validation.message,
        )
        next_state.current_output = repaired_output
        next_state.history.append(repair_event)
    return next_state


def run_iterations(
    state: ProjectState,
    *,
    iterations: int | None = None,
    tier: ModelTier = "budget",
    should_stop: Callable[[], bool] | None = None,
) -> RunIterationsResult:
    """Run up to N iterations (2N phase steps) with cooperative cancellation."""
    target_iterations = int(state.iterations if iterations is None else iterations)
    if target_iterations < 1:
        raise ValueError("iterations must be >= 1")

    steps_target = target_iterations * len(PHASE_SEQUENCE)
    current_state = apply_run_options(state)
    current_state.iterations = target_iterations
    steps_completed = 0

    for _ in range(steps_target):
        if should_stop is not None and should_stop():
            return RunIterationsResult(
                state=current_state,
                steps_completed=steps_completed,
                cancelled=True,
            )
        current_state = run_next_step(current_state, tier=tier)
        steps_completed += 1

    return RunIterationsResult(
        state=current_state,
        steps_completed=steps_completed,
        cancelled=False,
    )


def run_iteration() -> None:
    """Backward-compatible placeholder retained for earlier scripts."""
    return None
