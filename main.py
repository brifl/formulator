"""NiceGUI entrypoint for Prompt Iteration Workbench."""

from __future__ import annotations

from nicegui import ui
from prompt_iteration_workbench.models import IterationRecord

FORMAT_OPTIONS = ["Markdown", "JSON", "Text", "Python"]


def build_ui() -> None:
    """Render the stage-2 base shell with project inputs and phase controls."""
    history_records: list[IterationRecord] = []

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

    with ui.card().classes("w-full"):
        ui.label("History").classes("text-xl font-semibold")
        history_container = ui.column().classes("w-full gap-2")

        def render_history() -> None:
            history_container.clear()
            with history_container:
                if not history_records:
                    ui.label("No history entries yet. Run iterations to populate this panel.").classes(
                        "text-sm text-gray-600"
                    )
                    return
                for record in history_records:
                    with ui.card().classes("w-full bg-gray-50"):
                        ui.label(f"{record.phase_name.title()} phase - step {record.step_index}")
                        ui.label(record.timestamp_text).classes("text-xs text-gray-600")

        def inject_placeholder_history() -> None:
            history_records.clear()
            history_records.extend(
                [
                    IterationRecord(phase_name="additive", step_index=1, timestamp_text="2026-02-06 09:00:00"),
                    IterationRecord(phase_name="reductive", step_index=2, timestamp_text="2026-02-06 09:01:00"),
                    IterationRecord(phase_name="additive", step_index=3, timestamp_text="2026-02-06 09:02:00"),
                ]
            )
            render_history()

        def clear_history() -> None:
            history_records.clear()
            render_history()

        with ui.row().classes("gap-2"):
            ui.button("Inject placeholder history", on_click=inject_placeholder_history)
            ui.button("Clear history", on_click=clear_history)

        render_history()

    with ui.card().classes("w-full"):
        ui.label("Commands").classes("text-xl font-semibold")

        def notify_click(message: str) -> None:
            ui.notify(message, type="positive")

        with ui.row().classes("w-full gap-2"):
            ui.button(
                "Generate prompts (if empty)",
                on_click=lambda: notify_click("Generate prompts (if empty) clicked."),
            )
            ui.button("Run iterations", on_click=lambda: notify_click("Run iterations clicked."))
            ui.button("Run next step", on_click=lambda: notify_click("Run next step clicked."))
            stop_button = ui.button("Stop", on_click=lambda: notify_click("Stop clicked."))
            stop_button.props("disable")
            ui.button("Save project", on_click=lambda: notify_click("Save project clicked."))
            ui.button("Load project", on_click=lambda: notify_click("Load project clicked."))
            ui.button("New project", on_click=lambda: notify_click("New project clicked."))


def main() -> None:
    host = "127.0.0.1"
    port = 8080
    print(f"Starting Prompt Iteration Workbench at http://{host}:{port}")
    build_ui()
    ui.run(host=host, port=port, title="Prompt Iteration Workbench", show=False, reload=False)


if __name__ == "__main__":
    main()
