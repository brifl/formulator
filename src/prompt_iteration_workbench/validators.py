"""Structural validators for machine-checkable output formats."""

from __future__ import annotations

from dataclasses import dataclass
import ast
import json


@dataclass(frozen=True)
class ValidationResult:
    """Normalized validator response for output-structure checks."""

    ok: bool
    message: str
    applicable: bool
    format_name: str


def validate_json(text: str) -> ValidationResult:
    """Validate that text is syntactically valid JSON."""
    candidate = str(text or "")
    try:
        json.loads(candidate)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            ok=False,
            message=f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
            applicable=True,
            format_name="JSON",
        )
    return ValidationResult(ok=True, message="Valid JSON.", applicable=True, format_name="JSON")


def validate_python(text: str) -> ValidationResult:
    """Validate that text is syntactically valid Python code."""
    candidate = str(text or "")
    try:
        ast.parse(candidate)
    except SyntaxError as exc:
        line = int(getattr(exc, "lineno", 0) or 0)
        column = int(getattr(exc, "offset", 0) or 0)
        details = str(exc.msg or "syntax error").strip() or "syntax error"
        return ValidationResult(
            ok=False,
            message=f"Invalid Python: {details} at line {line}, column {column}.",
            applicable=True,
            format_name="PYTHON",
        )
    return ValidationResult(ok=True, message="Valid Python syntax.", applicable=True, format_name="PYTHON")


def validate_for_format(text: str, output_format: str) -> ValidationResult:
    """Run applicable structural validator for a selected output format."""
    normalized_format = str(output_format or "").strip().upper()
    if normalized_format == "JSON":
        return validate_json(text)
    if normalized_format == "PYTHON":
        return validate_python(text)
    return ValidationResult(
        ok=True,
        message=f"Validation not applicable for format '{normalized_format or 'TEXT'}'.",
        applicable=False,
        format_name=normalized_format or "TEXT",
    )

