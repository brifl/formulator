"""History event tests for Prompt Architect generation."""

from __future__ import annotations

from prompt_iteration_workbench.models import (
    HISTORY_EVENT_PHASE_STEP,
    HISTORY_EVENT_PROMPT_ARCHITECT,
    IterationRecord,
    ProjectState,
    format_history_label,
    make_prompt_architect_event,
)
from prompt_iteration_workbench.persistence import load_project, save_project


def test_make_prompt_architect_event_defaults_to_non_iteration_step() -> None:
    event = make_prompt_architect_event(model_used="gpt-5", note_summary="Templates generated")

    assert event.event_type == HISTORY_EVENT_PROMPT_ARCHITECT
    assert event.model_used == "gpt-5"
    assert event.note_summary == "Templates generated"
    assert event.phase_name == ""
    assert event.phase_step_index == 0
    assert event.pair_index == 0


def test_format_history_label_distinguishes_prompt_architect_events() -> None:
    phase_record = IterationRecord(
        event_type=HISTORY_EVENT_PHASE_STEP,
        pair_index=1,
        phase_step_index=2,
        phase_name="reductive",
    )
    event_record = make_prompt_architect_event(model_used="gpt-5", note_summary="Generated prompts")

    assert format_history_label(phase_record) == "Reductive phase - step 2"
    assert format_history_label(event_record) == "prompt_architect event - templates generated"


def test_persistence_roundtrip_keeps_prompt_architect_event(tmp_path) -> None:
    state = ProjectState(
        outcome="Test",
        history=[
            IterationRecord(
                event_type=HISTORY_EVENT_PHASE_STEP,
                pair_index=1,
                phase_step_index=1,
                phase_name="additive",
                model_used="gpt-5-mini",
            ),
            make_prompt_architect_event(model_used="gpt-5", note_summary="Prompt Architect templates generated."),
        ],
    )

    temp_file = tmp_path / "prompt-architect-history-event.json"
    save_project(state, temp_file)
    loaded = load_project(temp_file)

    assert len(loaded.history) == 2
    assert loaded.history[0].event_type == HISTORY_EVENT_PHASE_STEP
    assert loaded.history[0].phase_name == "additive"
    assert loaded.history[1].event_type == HISTORY_EVENT_PROMPT_ARCHITECT
    assert loaded.history[1].model_used == "gpt-5"
    assert "templates generated" in loaded.history[1].note_summary.lower()
