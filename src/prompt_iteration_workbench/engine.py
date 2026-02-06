"""Iteration engine planning semantics for additive/reductive loops."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_iteration_workbench.models import HISTORY_EVENT_PHASE_STEP, IterationRecord, ProjectState

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


def run_iteration() -> None:
    """Backward-compatible placeholder retained for early checkpoints."""
    return None
