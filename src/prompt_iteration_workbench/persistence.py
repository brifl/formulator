"""JSON persistence helpers for ProjectState."""

from __future__ import annotations

import json
from pathlib import Path

from prompt_iteration_workbench.models import IterationRecord, ProjectState

SUPPORTED_SCHEMA_VERSIONS = {1}


def _serialize_state(state: ProjectState) -> dict[str, object]:
    return {
        "schema_version": state.schema_version,
        "project_title": state.project_title,
        "outcome": state.outcome,
        "requirements_constraints": state.requirements_constraints,
        "special_resources": state.special_resources,
        "iterations": state.iterations,
        "output_format": state.output_format,
        "additive_phase_model_tier": state.additive_phase_model_tier,
        "reductive_phase_model_tier": state.reductive_phase_model_tier,
        "additive_phase_allowed_changes": state.additive_phase_allowed_changes,
        "reductive_phase_allowed_changes": state.reductive_phase_allowed_changes,
        "additive_prompt_template": state.additive_prompt_template,
        "reductive_prompt_template": state.reductive_prompt_template,
        "current_output": state.current_output,
        "history": [record.__dict__ for record in state.history],
    }


def _deserialize_state(payload: dict[str, object]) -> ProjectState:
    if "schema_version" not in payload:
        raise ValueError("Project file is missing required field: schema_version")

    schema_version = int(payload["schema_version"])
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise ValueError(f"Unsupported schema_version={schema_version}; supported versions: {supported}")

    raw_history = payload.get("history", [])
    if not isinstance(raw_history, list):
        raise ValueError("Project file field 'history' must be a list")

    history: list[IterationRecord] = []
    for item in raw_history:
        if not isinstance(item, dict):
            raise ValueError("Each history item must be an object")
        history.append(IterationRecord(**item))

    return ProjectState(
        schema_version=schema_version,
        project_title=str(payload.get("project_title", "")),
        outcome=str(payload.get("outcome", "")),
        requirements_constraints=str(payload.get("requirements_constraints", "")),
        special_resources=str(payload.get("special_resources", "")),
        iterations=int(payload.get("iterations", 1)),
        output_format=str(payload.get("output_format", "Markdown")),
        additive_phase_model_tier=str(payload.get("additive_phase_model_tier", "budget")),
        reductive_phase_model_tier=str(payload.get("reductive_phase_model_tier", "budget")),
        additive_phase_allowed_changes=str(payload.get("additive_phase_allowed_changes", "")),
        reductive_phase_allowed_changes=str(payload.get("reductive_phase_allowed_changes", "")),
        additive_prompt_template=str(payload.get("additive_prompt_template", "")),
        reductive_prompt_template=str(payload.get("reductive_prompt_template", "")),
        current_output=str(payload.get("current_output", "")),
        history=history,
    )


def save_project(state: ProjectState, path: str | Path) -> None:
    """Serialize ProjectState to a JSON file."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialize_state(state)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_project(path: str | Path) -> ProjectState:
    """Load ProjectState from a JSON file with schema validation."""
    target = Path(path).expanduser()
    return load_project_from_text(target.read_text(encoding="utf-8"))


def load_project_from_text(text: str) -> ProjectState:
    """Load ProjectState from a JSON text payload with schema validation."""
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Project file root must be an object")
    return _deserialize_state(payload)
