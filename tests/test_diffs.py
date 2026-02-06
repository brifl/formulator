from prompt_iteration_workbench.diffs import unified_text_diff


def test_unified_text_diff_reports_changes() -> None:
    previous_text = "line one\nline two\nline three\n"
    current_text = "line one\nline two updated\nline three\n"

    diff = unified_text_diff(previous_text, current_text)

    assert "--- previous" in diff
    assert "+++ selected" in diff
    assert "-line two" in diff
    assert "+line two updated" in diff


def test_unified_text_diff_returns_empty_when_equal() -> None:
    text = "same\ncontent\n"

    diff = unified_text_diff(text, text)

    assert diff == ""
