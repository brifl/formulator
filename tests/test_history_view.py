from prompt_iteration_workbench.history_view import format_history_header
from prompt_iteration_workbench.models import IterationRecord


def test_format_history_header_phase_step_fields() -> None:
    record = IterationRecord(
        phase_name="additive",
        iteration_index=2,
        phase_step_index=3,
        model_used="gpt-5-mini",
        created_at="2026-02-06T11:00:00+00:00",
    )

    header = format_history_header(record)

    assert "phase=additive" in header
    assert "iteration=2" in header
    assert "step=3" in header
    assert "ts=2026-02-06T11:00:00+00:00" in header
    assert "model=gpt-5-mini" in header


def test_format_history_header_defaults_for_missing_values() -> None:
    record = IterationRecord(
        event_type="prompt_architect",
        phase_name="",
        iteration_index=0,
        phase_step_index=0,
        model_used="",
        created_at="",
    )

    header = format_history_header(record)

    assert "phase=prompt architect" in header
    assert "iteration=-" in header
    assert "step=-" in header
    assert "ts=-" in header
    assert "model=-" in header
