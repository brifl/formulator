"""Domain model placeholders."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptIterationState:
    """Minimal placeholder model for iterative prompt state."""

    outcome: str = ""
    history: list["IterationRecord"] = field(default_factory=list)


@dataclass
class IterationRecord:
    """Minimal history entry for UI rendering."""

    phase_name: str = ""
    step_index: int = 0
    timestamp_text: str = ""
