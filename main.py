"""NiceGUI entrypoint for Prompt Iteration Workbench."""

from __future__ import annotations

from nicegui import ui

FORMAT_OPTIONS = ["Markdown", "JSON", "Text", "Python"]


def build_ui() -> None:
    """Render the stage-2 base shell with project inputs and phase controls."""
    ui.label("Prompt Iteration Workbench").classes("text-3xl font-bold")
    ui.label("Adversarial prompt iteration workspace").classes("text-sm text-gray-600")

    with ui.row().classes("w-full items-start gap-6"):
        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Project Inputs").classes("text-xl font-semibold")
            ui.textarea(label="Outcome", placeholder="Example: Skin Cream Formulation").props("autogrow")
            ui.textarea(label="Requirements and constraints", placeholder="Must-haves and must-nots").props(
                "autogrow"
            )
            ui.textarea(
                label="Special equipment, ingredients, skills",
                placeholder="Anything non-standard available to you",
            ).props("autogrow")

        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Phase Controls").classes("text-xl font-semibold")
            ui.number(label="Iterations (additive + reductive pairs)", value=1, min=1, step=1).props(
                "outlined"
            )
            ui.select(options=FORMAT_OPTIONS, value="Markdown", label="Format selector")
            ui.textarea(
                label="Additive phase allowed changes",
                placeholder="What additive steps are allowed to change",
            ).props("autogrow")
            ui.textarea(
                label="Reductive phase allowed changes",
                placeholder="What reductive steps are allowed to change",
            ).props("autogrow")

    with ui.row().classes("w-full items-start gap-6"):
        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Prompt Templates").classes("text-xl font-semibold")
            ui.textarea(
                label="Additive prompt template",
                placeholder="Template text for additive phase",
            ).props("autogrow")
            ui.textarea(
                label="Reductive prompt template",
                placeholder="Template text for reductive phase",
            ).props("autogrow")

        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Current Output").classes("text-xl font-semibold")
            ui.textarea(
                label="Current output (editable)",
                placeholder="Current working draft",
            ).props("autogrow")


def main() -> None:
    host = "127.0.0.1"
    port = 8080
    print(f"Starting Prompt Iteration Workbench at http://{host}:{port}")
    build_ui()
    ui.run(host=host, port=port, title="Prompt Iteration Workbench", show=False, reload=False)


if __name__ == "__main__":
    main()
