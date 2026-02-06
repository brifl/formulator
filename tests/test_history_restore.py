"""History restore behavior tests for checkpoint 9.3."""

from __future__ import annotations

import pytest

from prompt_iteration_workbench.engine import phase_step_history
from prompt_iteration_workbench.history_restore import restore_history_snapshot
from prompt_iteration_workbench.models import (
    HISTORY_EVENT_RESTORE,
    IterationRecord,
    format_history_label,
)


def _sample_history() -> list[IterationRecord]:
    return [
        IterationRecord(
            phase_name="additive",
            iteration_index=1,
            pair_index=1,
            phase_step_index=1,
            output_snapshot="alpha\nbeta\n",
        ),
        IterationRecord(
            phase_name="reductive",
            iteration_index=1,
            pair_index=1,
            phase_step_index=2,
            output_snapshot="alpha\ngamma\n",
        ),
    ]


def test_restore_history_snapshot_restores_output_and_appends_event() -> None:
    original_history = _sample_history()

    restored_output, restored_history = restore_history_snapshot(
        original_history,
        record_index=0,
    )

    assert restored_output == original_history[0].output_snapshot
    assert len(restored_history) == len(original_history) + 1

    restore_event = restored_history[-1]
    assert restore_event.event_type == HISTORY_EVENT_RESTORE
    assert restore_event.output_snapshot == original_history[0].output_snapshot
    assert format_history_label(restore_event) == "restore event - output restored from history"

    # Ensure source list is unchanged.
    assert len(original_history) == 2
    assert original_history[-1].event_type != HISTORY_EVENT_RESTORE


def test_restore_event_does_not_count_as_phase_step() -> None:
    _, restored_history = restore_history_snapshot(_sample_history(), record_index=1)

    assert len(phase_step_history(restored_history)) == 2


def test_restore_history_snapshot_invalid_index_raises() -> None:
    with pytest.raises(IndexError):
        restore_history_snapshot(_sample_history(), record_index=99)
