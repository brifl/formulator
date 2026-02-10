"""Persistence tests for per-phase model tier settings."""

from __future__ import annotations

import json

from prompt_iteration_workbench.models import ProjectState
from prompt_iteration_workbench.persistence import load_project, load_project_from_text, save_project


def test_save_load_preserves_phase_model_tiers(tmp_path) -> None:
    state = ProjectState(
        project_title="My Test Project",
        additive_phase_model_tier="premium",
        reductive_phase_model_tier="budget",
        additive_prompt_template="Add {{CURRENT_OUTPUT}}",
        reductive_prompt_template="Reduce {{CURRENT_OUTPUT}}",
    )
    path = tmp_path / "phase-tier-roundtrip.json"

    save_project(state, path)
    loaded = load_project(path)

    assert loaded.project_title == "My Test Project"
    assert loaded.additive_phase_model_tier == "premium"
    assert loaded.reductive_phase_model_tier == "budget"


def test_load_project_from_text_supports_title_and_defaults() -> None:
    payload = {
        "schema_version": 1,
        "project_title": "Picked Project",
        "outcome": "Goal",
        "history": [],
    }
    loaded = load_project_from_text(json.dumps(payload))

    assert loaded.project_title == "Picked Project"
    assert loaded.outcome == "Goal"
    assert loaded.output_format == "Markdown"
