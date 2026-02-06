"""Domain model placeholders."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PromptIterationState:
    """Minimal placeholder model for iterative prompt state."""

    outcome: str = ""
