"""History snapshot restore helpers."""

from __future__ import annotations

from prompt_iteration_workbench.models import IterationRecord, make_restore_event


def restore_history_snapshot(
    history_records: list[IterationRecord],
    *,
    record_index: int,
) -> tuple[str, list[IterationRecord]]:
    """Restore output from a selected history record and append a restore event."""
    if record_index < 0 or record_index >= len(history_records):
        raise IndexError("record_index is out of range.")

    next_history = [IterationRecord(**record.__dict__) for record in history_records]
    selected = next_history[record_index]
    restored_output = selected.output_snapshot
    restore_note = f"Restored from history entry {record_index + 1}."
    next_history.append(
        make_restore_event(
            note_summary=restore_note,
            output_snapshot=restored_output,
        )
    )
    return restored_output, next_history
