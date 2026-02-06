"""UI validation status helper tests for checkpoint 8.3."""

from __future__ import annotations

from prompt_iteration_workbench.validation_status import describe_validation_state


def test_describe_validation_state_reports_valid_json() -> None:
    status, message = describe_validation_state('{"a": 1}', 'JSON')

    assert status == 'Validation status: Valid'
    assert message == 'Validation message: None'


def test_describe_validation_state_reports_invalid_json_error() -> None:
    status, message = describe_validation_state('{a:1}', 'JSON')

    assert status == 'Validation status: Invalid'
    assert 'Invalid JSON:' in message


def test_describe_validation_state_not_applicable_for_markdown() -> None:
    current_output = '# Heading\nBody'

    status, message = describe_validation_state(current_output, 'Markdown')

    assert status == 'Validation status: Not applicable'
    assert '(not applicable for selected format)' in message
    assert current_output == '# Heading\nBody'
