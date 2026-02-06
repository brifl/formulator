"""Utilities for rendering human-readable text diffs."""

from __future__ import annotations

import difflib


def unified_text_diff(
    previous_output: str,
    current_output: str,
    *,
    previous_label: str = "previous",
    current_label: str = "selected",
) -> str:
    """Return a unified diff string between previous and current output snapshots."""
    previous_lines = str(previous_output).splitlines()
    current_lines = str(current_output).splitlines()
    diff_lines = difflib.unified_diff(
        previous_lines,
        current_lines,
        fromfile=previous_label,
        tofile=current_label,
        lineterm="",
    )
    return "\n".join(diff_lines)
