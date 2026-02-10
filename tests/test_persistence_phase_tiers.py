"""Persistence tests for per-phase model tier settings."""

from __future__ import annotations

from prompt_iteration_workbench.models import ProjectState
from prompt_iteration_workbench.persistence import load_project, save_project


def test_save_load_preserves_phase_model_tiers(tmp_path) -> None:
    state = ProjectState(
        additive_phase_model_tier="premium",
        reductive_phase_model_tier="budget",
        additive_prompt_template="Add {{CURRENT_OUTPUT}}",
        reductive_prompt_template="Reduce {{CURRENT_OUTPUT}}",
    )
    path = tmp_path / "phase-tier-roundtrip.json"

    save_project(state, path)
    loaded = load_project(path)

    assert loaded.additive_phase_model_tier == "premium"
    assert loaded.reductive_phase_model_tier == "budget"
