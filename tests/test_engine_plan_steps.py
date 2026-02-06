"""Iteration planning semantics tests for checkpoint 7.0."""

from __future__ import annotations

from prompt_iteration_workbench.engine import RunOptions, build_run_plan, plan_steps
from prompt_iteration_workbench.models import ProjectState


def test_plan_steps_orders_additive_then_reductive_for_each_iteration() -> None:
    state = ProjectState(iterations=3)

    steps = plan_steps(state)

    assert [step.phase_name for step in steps] == [
        "additive",
        "reductive",
        "additive",
        "reductive",
        "additive",
        "reductive",
    ]


def test_plan_steps_populates_iteration_and_phase_step_indexes() -> None:
    state = ProjectState(iterations=3)

    steps = plan_steps(state)

    assert [(step.iteration_index, step.phase_step_index) for step in steps] == [
        (1, 1),
        (1, 2),
        (2, 3),
        (2, 4),
        (3, 5),
        (3, 6),
    ]


def test_build_run_plan_applies_iteration_override() -> None:
    state = ProjectState(iterations=1)

    run_plan = build_run_plan(state, RunOptions(iterations_override=2))

    assert run_plan.state.iterations == 2
    assert len(run_plan.steps) == 4
