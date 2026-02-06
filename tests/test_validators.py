"""Structural validator tests for checkpoint 8.1."""

from __future__ import annotations

from prompt_iteration_workbench.validators import validate_for_format, validate_json, validate_python


def test_validate_json_accepts_valid_json() -> None:
    result = validate_json('{"a": 1}')

    assert result.ok is True
    assert result.applicable is True
    assert result.format_name == "JSON"


def test_validate_json_rejects_invalid_json_with_useful_message() -> None:
    result = validate_json('{a:1}')

    assert result.ok is False
    assert "Invalid JSON:" in result.message
    assert "line" in result.message


def test_validate_python_accepts_valid_syntax() -> None:
    result = validate_python('x=1\nprint(x)')

    assert result.ok is True
    assert result.applicable is True
    assert result.format_name == "PYTHON"


def test_validate_python_rejects_invalid_syntax_with_useful_message() -> None:
    result = validate_python('x=\n')

    assert result.ok is False
    assert "Invalid Python:" in result.message
    assert "line" in result.message


def test_validate_for_format_runs_only_applicable_validators() -> None:
    json_result = validate_for_format('{"a":1}', 'JSON')
    python_result = validate_for_format('x=1', 'Python')
    markdown_result = validate_for_format('# title', 'Markdown')

    assert json_result.applicable is True
    assert python_result.applicable is True
    assert markdown_result.applicable is False
    assert markdown_result.ok is True
