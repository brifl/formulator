"""Helpers for rendering history entries in the UI."""

from __future__ import annotations

from prompt_iteration_workbench.models import IterationRecord


def _display_or_dash(value: str) -> str:
    text = value.strip()
    return text if text else "-"


def format_history_header(record: IterationRecord) -> str:
    """Build a compact header for collapsed history rows."""
    phase_raw = record.phase_name.strip()
    if not phase_raw:
        phase_raw = record.event_type.replace("_", " ").strip() or "unknown"

    iteration_value: int | str = record.iteration_index if record.iteration_index > 0 else "-"
    step_value: int | str = record.phase_step_index if record.phase_step_index > 0 else "-"
    timestamp = _display_or_dash(record.created_at)
    model = _display_or_dash(record.model_used)

    return (
        f"phase={phase_raw} | iteration={iteration_value} | "
        f"step={step_value} | ts={timestamp} | model={model}"
    )
