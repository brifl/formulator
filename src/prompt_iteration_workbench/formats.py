"""Format-specific soft guidance blocks for iteration prompts."""

from __future__ import annotations

_FORMAT_GUIDANCE: dict[str, str] = {
    "JSON": (
        "Output format guidance: return valid JSON only.\n"
        "Do not include markdown fences or explanatory text.\n"
        "Ensure keys and string values are properly quoted."
    ),
    "MARKDOWN": (
        "Output format guidance: return clear Markdown.\n"
        "Use concise headings and bullet lists where helpful.\n"
        "Avoid code fences unless code is explicitly requested."
    ),
    "PYTHON": (
        "Output format guidance: return syntactically valid Python code.\n"
        "Keep code runnable and avoid explanatory prose outside comments.\n"
        "Use explicit imports when needed."
    ),
    "TEXT": (
        "Output format guidance: return plain text only.\n"
        "Keep structure readable with short paragraphs or numbered lines.\n"
        "Avoid markdown syntax unless requested."
    ),
}


def get_format_guidance(format_name: str) -> str:
    """Return normalized guidance text for the selected output format."""
    normalized = str(format_name or "Text").strip().upper()
    return _FORMAT_GUIDANCE.get(normalized, _FORMAT_GUIDANCE["TEXT"])

