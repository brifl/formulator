"""Canonical project and iteration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IterationRecord:
    """Canonical history entry for one generated phase step."""

    pair_index: int = 0
    phase_step_index: int = 0
    phase_name: str = ""
    model_used: str = ""
    prompt_rendered: str = ""
    output_snapshot: str = ""
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass
class ProjectState:
    """Canonical in-memory representation of project inputs and history."""

    outcome: str = ""
    requirements_constraints: str = ""
    special_resources: str = ""
    iterations: int = 1
    output_format: str = "Markdown"
    additive_phase_allowed_changes: str = ""
    reductive_phase_allowed_changes: str = ""
    additive_prompt_template: str = ""
    reductive_prompt_template: str = ""
    current_output: str = ""
    history: list[IterationRecord] = field(default_factory=list)


# Backward-compatible alias for earlier checkpoints.
PromptIterationState = ProjectState
