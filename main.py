"""NiceGUI entrypoint for Prompt Iteration Workbench."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from nicegui import ui

from prompt_iteration_workbench.engine import run_iterations, run_next_step
from prompt_iteration_workbench.history_view import format_history_header
from prompt_iteration_workbench.models import (
    HISTORY_EVENT_PHASE_STEP,
    HISTORY_EVENT_PROMPT_ARCHITECT,
    format_history_label,
    IterationRecord,
    ProjectState,
    make_prompt_architect_event,
)
from prompt_iteration_workbench.persistence import load_project, save_project
from prompt_iteration_workbench.prompt_architect import (
    PromptArchitectError,
    generate_templates,
    resolve_prompt_architect_model,
)
from prompt_iteration_workbench.prompt_templates import (
    SUPPORTED_TOKENS,
    build_context,
    render_template,
    validate_template,
)
from prompt_iteration_workbench.validation_status import describe_validation_state

FORMAT_OPTIONS = ["Markdown", "JSON", "Text", "Python"]
PROJECTS_DIR = Path("projects")


def apply_generated_templates(
    *,
    existing_additive: str,
    existing_reductive: str,
    generated_additive: str,
    generated_reductive: str,
    overwrite_existing: bool,
) -> tuple[str, str, list[str]]:
    """Merge generated templates into current fields with optional overwrite."""
    next_additive = existing_additive
    next_reductive = existing_reductive
    updated_fields: list[str] = []

    if overwrite_existing or not existing_additive.strip():
        next_additive = generated_additive
        updated_fields.append("additive")
    if overwrite_existing or not existing_reductive.strip():
        next_reductive = generated_reductive
        updated_fields.append("reductive")

    return next_additive, next_reductive, updated_fields


def describe_template_validation_issues(template_name: str, template_text: str) -> str | None:
    """Summarize unknown/missing token issues for UI warning display."""
    validation = validate_template(template_text, SUPPORTED_TOKENS, set())
    parts: list[str] = []
    if validation.unknown:
        unknown = ", ".join(f"{{{{{token}}}}}" for token in sorted(validation.unknown))
        parts.append(f"unknown tokens: {unknown}")
    if validation.missing_required:
        missing = ", ".join(f"{{{{{token}}}}}" for token in sorted(validation.missing_required))
        parts.append(f"missing required tokens: {missing}")
    if not parts:
        return None
    return f"{template_name}: " + "; ".join(parts)


def build_ui() -> None:
    """Render the stage-2 base shell with project inputs and phase controls."""
    history_records: list[IterationRecord] = []
    last_saved_path: Path | None = None
    is_applying_state = False
    is_run_active = False
    stop_requested = False
    current_status = "Idle"

    ui.label("Prompt Iteration Workbench").classes("text-3xl font-bold")
    ui.label("Adversarial prompt iteration workspace").classes("text-sm text-gray-600")

    with ui.row().classes("w-full items-start gap-6"):
        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Project Inputs").classes("text-xl font-semibold")
            outcome_input = ui.textarea(label="Outcome", placeholder="Example: Skin Cream Formulation").props(
                "autogrow"
            )
            requirements_input = ui.textarea(
                label="Requirements and constraints", placeholder="Must-haves and must-nots"
            ).props("autogrow")
            resources_input = ui.textarea(
                label="Special equipment, ingredients, skills",
                placeholder="Anything non-standard available to you",
            ).props("autogrow")

        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Phase Controls").classes("text-xl font-semibold")
            iterations_input = ui.number(
                label="Iterations (additive + reductive pairs)", value=1, min=1, step=1
            ).props("outlined")
            format_input = ui.select(options=FORMAT_OPTIONS, value="Markdown", label="Format selector")
            additive_rules_input = ui.textarea(
                label="Additive phase allowed changes",
                placeholder="What additive steps are allowed to change",
            ).props("autogrow")
            reductive_rules_input = ui.textarea(
                label="Reductive phase allowed changes",
                placeholder="What reductive steps are allowed to change",
            ).props("autogrow")

    with ui.row().classes("w-full items-start gap-6"):
        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Prompt Templates").classes("text-xl font-semibold")
            additive_template_input = ui.textarea(
                label="Additive prompt template",
                placeholder="Template text for additive phase",
            ).props("autogrow")
            reductive_template_input = ui.textarea(
                label="Reductive prompt template",
                placeholder="Template text for reductive phase",
            ).props("autogrow")
            with ui.row().classes("w-full gap-2"):
                ui.button("Preview additive", on_click=lambda: preview_template("additive"))
                ui.button("Preview reductive", on_click=lambda: preview_template("reductive"))

        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Current Output").classes("text-xl font-semibold")
            current_output_input = ui.textarea(
                label="Current output (editable)",
                placeholder="Current working draft",
            ).props("autogrow")

    with ui.dialog() as preview_dialog, ui.card().classes("w-[92vw] max-w-5xl"):
        preview_title = ui.label("Rendered prompt preview").classes("text-lg font-semibold")
        preview_validation_label = ui.label("Validation: OK").classes("text-sm")
        preview_textarea = ui.textarea(label="Rendered prompt").props("readonly autogrow").classes("w-full")
        ui.button("Close", on_click=preview_dialog.close)

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
                    with ui.expansion(format_history_header(record)).classes("w-full"):
                        ui.label(format_history_label(record)).classes("text-xs text-gray-600")

                        if record.note_summary.strip():
                            ui.label(record.note_summary.strip()).classes("text-sm text-gray-700")

                        ui.textarea(
                            label="Output snapshot",
                            value=record.output_snapshot,
                        ).props("readonly autogrow").classes("w-full")

                        if record.prompt_rendered.strip():
                            ui.textarea(
                                label="Prompt rendered",
                                value=record.prompt_rendered,
                            ).props("readonly autogrow").classes("w-full")

        def inject_placeholder_history() -> None:
            history_records.clear()
            history_records.extend(
                [
                    IterationRecord(
                        pair_index=1,
                        phase_step_index=1,
                        phase_name="additive",
                        model_used="gpt-5-mini",
                        prompt_rendered="Additive prompt placeholder render",
                        output_snapshot="Placeholder additive output",
                        created_at="2026-02-06 09:00:00",
                    ),
                    IterationRecord(
                        pair_index=1,
                        phase_step_index=2,
                        phase_name="reductive",
                        model_used="gpt-5-mini",
                        output_snapshot="Placeholder reductive output",
                        created_at="2026-02-06 09:01:00",
                    ),
                    IterationRecord(
                        pair_index=2,
                        phase_step_index=3,
                        phase_name="additive",
                        model_used="gpt-5-mini",
                        output_snapshot="Placeholder additive output",
                        created_at="2026-02-06 09:02:00",
                    ),
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
        ui.label("Run Status").classes("text-xl font-semibold")
        status_label = ui.label("Status: Idle").classes("font-medium")
        error_label = ui.label("Error: None").classes("text-sm text-red-700")

        def set_status(value: str) -> None:
            nonlocal current_status
            current_status = value
            status_label.set_text(f"Status: {value}")

        def set_error(message: str) -> None:
            error_label.set_text(f"Error: {message}")

        def trigger_test_error() -> None:
            set_status("Error")
            set_error("Test error: placeholder failure surface for UI verification.")
            ui.notify("Test error surfaced.", type="negative")

        with ui.row().classes("w-full gap-2"):
            ui.button("Set Running", on_click=lambda: set_status("Running"))
            ui.button("Set Stopped", on_click=lambda: set_status("Stopped"))
            ui.button("Reset Idle", on_click=lambda: set_status("Idle"))
            ui.button("Trigger test error", on_click=trigger_test_error)

    with ui.card().classes("w-full"):
        ui.label("Validation Status").classes("text-xl font-semibold")
        validation_status_label = ui.label("Validation status: Not applicable").classes("font-medium")
        validation_error_label = ui.label("Validation message: (not applicable for selected format)").classes(
            "text-sm text-gray-700"
        )

        def refresh_validation_status() -> None:
            status_text, message_text = describe_validation_state(
                str(current_output_input.value or ""),
                str(format_input.value or ""),
            )
            validation_status_label.set_text(status_text)
            validation_error_label.set_text(message_text)

    with ui.card().classes("w-full"):
        ui.label("Persistence").classes("text-xl font-semibold")
        autosave_toggle = ui.switch("Autosave on change", value=False)
        last_saved_path_label = ui.label("Last saved path: (none)").classes("text-sm text-gray-700")
        last_saved_time_label = ui.label("Last saved time: (never)").classes("text-sm text-gray-700")

    def build_preview_context(*, phase_name: str) -> dict[str, object]:
        return build_context(
            state=state_from_ui(),
            phase_name=phase_name,
            iteration_index=int(iterations_input.value or 1),
        )

    def preview_template(phase_name: str) -> None:
        template_text = (
            str(additive_template_input.value or "")
            if phase_name == "additive"
            else str(reductive_template_input.value or "")
        )
        context = build_preview_context(phase_name=phase_name)
        validation = validate_template(template_text, SUPPORTED_TOKENS, set())
        rendered = render_template(template_text, context)

        preview_title.set_text(f"{phase_name.title()} prompt preview")
        if validation.unknown or validation.missing_required:
            issues: list[str] = []
            if validation.unknown:
                unknown = ", ".join(f"{{{{{token}}}}}" for token in sorted(validation.unknown))
                issues.append(f"Unknown tokens: {unknown}")
            if validation.missing_required:
                missing = ", ".join(f"{{{{{token}}}}}" for token in sorted(validation.missing_required))
                issues.append(f"Missing required tokens: {missing}")
            preview_validation_label.set_text("Validation issues: " + " | ".join(issues))
        else:
            preview_validation_label.set_text("Validation: OK")

        preview_textarea.value = rendered
        preview_dialog.open()

    def state_from_ui() -> ProjectState:
        return ProjectState(
            outcome=str(outcome_input.value or ""),
            requirements_constraints=str(requirements_input.value or ""),
            special_resources=str(resources_input.value or ""),
            iterations=int(iterations_input.value or 1),
            output_format=str(format_input.value or "Markdown"),
            additive_phase_allowed_changes=str(additive_rules_input.value or ""),
            reductive_phase_allowed_changes=str(reductive_rules_input.value or ""),
            additive_prompt_template=str(additive_template_input.value or ""),
            reductive_prompt_template=str(reductive_template_input.value or ""),
            current_output=str(current_output_input.value or ""),
            history=[IterationRecord(**record.__dict__) for record in history_records],
        )

    def apply_state(state: ProjectState) -> None:
        nonlocal is_applying_state
        is_applying_state = True
        try:
            outcome_input.value = state.outcome
            requirements_input.value = state.requirements_constraints
            resources_input.value = state.special_resources
            iterations_input.value = state.iterations
            format_input.value = state.output_format
            additive_rules_input.value = state.additive_phase_allowed_changes
            reductive_rules_input.value = state.reductive_phase_allowed_changes
            additive_template_input.value = state.additive_prompt_template
            reductive_template_input.value = state.reductive_prompt_template
            current_output_input.value = state.current_output
            history_records.clear()
            history_records.extend(state.history)
            render_history()
            refresh_validation_status()
        finally:
            is_applying_state = False

    def update_save_metadata(path: Path) -> None:
        last_saved_path_label.set_text(f"Last saved path: {path}")
        last_saved_time_label.set_text(
            f"Last saved time: {datetime.now().isoformat(timespec='seconds')}"
        )

    def persist_current_state() -> Path:
        nonlocal last_saved_path
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        if last_saved_path is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            last_saved_path = PROJECTS_DIR / f"project-{timestamp}.json"
        save_project(state_from_ui(), last_saved_path)
        update_save_metadata(last_saved_path)
        return last_saved_path

    def autosave_if_enabled() -> None:
        if is_applying_state:
            return
        if not bool(autosave_toggle.value):
            return
        try:
            persist_current_state()
            set_status("Idle")
            set_error("None")
        except Exception as exc:
            set_status("Error")
            set_error(f"Autosave failed: {exc}")
            ui.notify("Autosave failed.", type="negative")

    def refresh_validation_if_idle() -> None:
        if is_applying_state or is_run_active:
            return
        if current_status != "Idle":
            return
        refresh_validation_status()

    def register_autosave(element: ui.element) -> None:
        element.on("update:model-value", lambda _event: autosave_if_enabled())

    def register_validation_refresh(element: ui.element) -> None:
        element.on("update:model-value", lambda _event: refresh_validation_if_idle())

    with ui.card().classes("w-full"):
        ui.label("Commands").classes("text-xl font-semibold")
        overwrite_templates_toggle = ui.switch("Overwrite existing templates", value=False)

        def notify_click(message: str) -> None:
            ui.notify(message, type="positive")

        def generate_prompts_action() -> None:
            try:
                generated_additive, generated_reductive, notes = generate_templates(state_from_ui())
                validation_warnings: list[str] = []
                for template_name, template_text in (
                    ("additive", generated_additive),
                    ("reductive", generated_reductive),
                ):
                    issue = describe_template_validation_issues(template_name, template_text)
                    if issue is not None:
                        validation_warnings.append(issue)

                if validation_warnings:
                    ui.notify("Template validation warnings: " + " | ".join(validation_warnings), type="warning")
                else:
                    ui.notify("Template validation: no unknown tokens detected.", type="positive")

                next_additive, next_reductive, updated_fields = apply_generated_templates(
                    existing_additive=str(additive_template_input.value or ""),
                    existing_reductive=str(reductive_template_input.value or ""),
                    generated_additive=generated_additive,
                    generated_reductive=generated_reductive,
                    overwrite_existing=bool(overwrite_templates_toggle.value),
                )
                additive_template_input.value = next_additive
                reductive_template_input.value = next_reductive
                set_status("Idle")
                set_error("None")

                if updated_fields:
                    notify_click(f"Generate prompts updated: {', '.join(updated_fields)}")
                else:
                    ui.notify("Generate prompts made no changes (templates already populated).", type="warning")

                history_records.append(
                    make_prompt_architect_event(
                        model_used=resolve_prompt_architect_model(),
                        note_summary=notes,
                    )
                )
                render_history()

                if notes.strip():
                    ui.notify(f"Prompt Architect notes: {notes[:120]}", type="info")
            except PromptArchitectError as exc:
                set_status("Error")
                set_error(exc.message)
                ui.notify(exc.message, type="negative")
            except Exception as exc:
                set_status("Error")
                set_error(f"Generate prompts failed: {exc}")
                ui.notify("Generate prompts failed.", type="negative")

        def run_next_step_action() -> None:
            nonlocal is_run_active
            if is_run_active:
                ui.notify("A run is already active.", type="warning")
                return
            try:
                set_status("Running")
                set_error("None")
                next_state = run_next_step(state_from_ui())
                apply_state(next_state)
                set_status("Idle")
                refresh_validation_status()
                notify_click("Run next step completed.")
            except Exception as exc:
                set_status("Error")
                set_error(f"Run next step failed: {exc}")
                ui.notify("Run next step failed.", type="negative")

        def stop_action() -> None:
            nonlocal stop_requested
            if not is_run_active:
                return
            stop_requested = True
            set_status("Stopping")
            ui.notify("Stop requested. The run will halt after the current step.", type="warning")

        def save_project_action() -> None:
            try:
                saved_path = persist_current_state()
                set_status("Idle")
                set_error("None")
                notify_click(f"Save project clicked. File: {saved_path}")
            except Exception as exc:
                set_status("Error")
                set_error(f"Save failed: {exc}")
                ui.notify("Save failed.", type="negative")

        def load_project_action() -> None:
            nonlocal last_saved_path
            try:
                if last_saved_path is None:
                    candidates = sorted(PROJECTS_DIR.glob("*.json"))
                    if not candidates:
                        ui.notify("No saved project file found.", type="warning")
                        return
                    last_saved_path = candidates[-1]
                loaded = load_project(last_saved_path)
                apply_state(loaded)
                update_save_metadata(last_saved_path)
                set_status("Idle")
                set_error("None")
                notify_click(f"Load project clicked. File: {last_saved_path}")
            except Exception as exc:
                set_status("Error")
                set_error(f"Load failed: {exc}")
                ui.notify("Load failed.", type="negative")

        def new_project_action() -> None:
            nonlocal last_saved_path
            apply_state(ProjectState())
            last_saved_path = None
            last_saved_path_label.set_text("Last saved path: (none)")
            last_saved_time_label.set_text("Last saved time: (never)")
            set_status("Idle")
            set_error("None")
            notify_click("New project clicked. State reset to defaults.")

        with ui.row().classes("w-full gap-2"):
            ui.button("Generate prompts (if empty)", on_click=generate_prompts_action)
            run_iterations_button = ui.button("Run iterations")
            ui.button("Run next step", on_click=run_next_step_action)
            stop_button = ui.button("Stop", on_click=stop_action)
            stop_button.props("disable")
            ui.button("Save project", on_click=save_project_action)
            ui.button("Load project", on_click=load_project_action)
            ui.button("New project", on_click=new_project_action)

        async def run_iterations_action() -> None:
            nonlocal is_run_active, stop_requested
            if is_run_active:
                ui.notify("A run is already active.", type="warning")
                return

            try:
                requested_iterations = int(iterations_input.value or 1)
                if requested_iterations < 1:
                    raise ValueError("Iterations must be >= 1.")

                is_run_active = True
                stop_requested = False
                stop_button.enable()
                set_status("Running")
                set_error("None")

                base_state = state_from_ui()
                result = await asyncio.to_thread(
                    lambda: run_iterations(
                        base_state,
                        iterations=requested_iterations,
                        should_stop=lambda: stop_requested,
                    )
                )
                apply_state(result.state)
                refresh_validation_status()

                if result.cancelled:
                    set_status("Stopped")
                    ui.notify(
                        f"Run stopped after {result.steps_completed} phase steps.",
                        type="warning",
                    )
                else:
                    set_status("Idle")
                    notify_click(f"Run iterations completed ({result.steps_completed} phase steps).")
            except Exception as exc:
                set_status("Error")
                set_error(f"Run iterations failed: {exc}")
                ui.notify("Run iterations failed.", type="negative")
            finally:
                is_run_active = False
                stop_button.disable()
                stop_requested = False

        run_iterations_button.on_click(run_iterations_action)

    for editable in [
        outcome_input,
        requirements_input,
        resources_input,
        iterations_input,
        format_input,
        additive_rules_input,
        reductive_rules_input,
        additive_template_input,
        reductive_template_input,
        current_output_input,
    ]:
        register_autosave(editable)

    register_validation_refresh(current_output_input)
    register_validation_refresh(format_input)
    refresh_validation_status()


def main() -> None:
    host = "127.0.0.1"
    port = 8080
    print(f"Starting Prompt Iteration Workbench at http://{host}:{port}")
    build_ui()
    ui.run(host=host, port=port, title="Prompt Iteration Workbench", show=False, reload=False)


if __name__ == "__main__":
    main()
