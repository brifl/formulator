"""Canonical project and iteration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


HISTORY_EVENT_PHASE_STEP = "phase_step"
HISTORY_EVENT_PROMPT_ARCHITECT = "prompt_architect"
HISTORY_EVENT_REPAIR = "repair"


@dataclass
class IterationRecord:
    """Canonical history entry for one generated phase step."""

    event_type: str = HISTORY_EVENT_PHASE_STEP
    iteration_index: int = 0
    pair_index: int = 0
    phase_step_index: int = 0
    phase_name: str = ""
    model_used: str = ""
    note_summary: str = ""
    change_summary: str = ""
    prompt_rendered: str = ""
    output_snapshot: str = ""
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        # Backward compatibility: older checkpoints used pair_index only.
        if self.iteration_index <= 0 and self.pair_index > 0:
            self.iteration_index = self.pair_index
        elif self.pair_index <= 0 and self.iteration_index > 0:
            self.pair_index = self.iteration_index
        elif self.iteration_index > 0 and self.pair_index > 0 and self.iteration_index != self.pair_index:
            self.pair_index = self.iteration_index


def make_prompt_architect_event(*, model_used: str, note_summary: str) -> IterationRecord:
    """Create a non-iteration history record for prompt template generation."""
    return IterationRecord(
        event_type=HISTORY_EVENT_PROMPT_ARCHITECT,
        model_used=model_used,
        note_summary=note_summary.strip(),
    )


def make_repair_event(
    *,
    model_used: str,
    note_summary: str,
    prompt_rendered: str,
    output_snapshot: str,
) -> IterationRecord:
    """Create a non-phase history record for one structural repair attempt."""
    return IterationRecord(
        event_type=HISTORY_EVENT_REPAIR,
        model_used=model_used,
        note_summary=note_summary.strip(),
        prompt_rendered=prompt_rendered,
        output_snapshot=output_snapshot,
    )


def format_history_label(record: IterationRecord) -> str:
    """Format a history row label with distinct text for non-iteration events."""
    if record.event_type == HISTORY_EVENT_PROMPT_ARCHITECT:
        return "prompt_architect event - templates generated"
    if record.event_type == HISTORY_EVENT_REPAIR:
        return "repair event - structural validation retry"
    phase_prefix = f"{record.phase_name.title()} phase" if record.phase_name else "Phase step"
    return f"{phase_prefix} - step {record.phase_step_index}"


@dataclass
class ProjectState:
    """Canonical in-memory representation of project inputs and history."""

    schema_version: int = 1
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
