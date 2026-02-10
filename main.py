"""NiceGUI entrypoint for Prompt Iteration Workbench."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import re

from nicegui import ui
from nicegui.events import UploadEventArguments

from prompt_iteration_workbench.diffs import unified_text_diff
from prompt_iteration_workbench.engine import (
    generate_change_summary_for_record,
    run_next_step,
)
from prompt_iteration_workbench.history_view import format_history_header
from prompt_iteration_workbench.history_restore import restore_history_snapshot
from prompt_iteration_workbench.llm_client import LLMError
from prompt_iteration_workbench.models import (
    HISTORY_EVENT_PHASE_STEP,
    format_history_label,
    IterationRecord,
    ProjectState,
    make_prompt_architect_event,
)
from prompt_iteration_workbench.persistence import load_project, load_project_from_text, save_project
from prompt_iteration_workbench.prompt_architect import (
    PromptArchitectError,
    generate_template_for_phase,
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
MODEL_TIER_OPTIONS = ["budget", "premium"]
PROJECTS_DIR = Path("projects")
LOG_FILE = Path("logs/app.log")
LOGGER = logging.getLogger("prompt_iteration_workbench.ui")
_TITLE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _has_file_handler(logger: logging.Logger, path: Path) -> bool:
    target_path = path.resolve()
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            continue
        handler_path = Path(getattr(handler, "baseFilename", "")).resolve()
        if handler_path == target_path:
            return True
    return False


def _configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    for logger in (
        LOGGER,
        logging.getLogger("prompt_iteration_workbench.llm_client"),
    ):
        if not _has_file_handler(logger, LOG_FILE):
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def _slugify_title(text: str) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    slug = _TITLE_SLUG_PATTERN.sub("-", normalized).strip("-")
    return slug


def _sanitize_upload_filename(name: str) -> str:
    raw_name = Path(str(name or "")).name
    stem = _slugify_title(Path(raw_name).stem)
    if not stem:
        stem = "project"
    return f"{stem}.json"


def _next_available_project_path(title: str, directory: Path) -> Path:
    slug = _slugify_title(title)
    if not slug:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return directory / f"project-{timestamp}.json"

    candidate = directory / f"{slug}.json"
    if not candidate.exists():
        return candidate

    suffix = 2
    while True:
        versioned = directory / f"{slug}-{suffix}.json"
        if not versioned.exists():
            return versioned
        suffix += 1


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

    ui.add_css(
        """
        .piw-field,
        .piw-field .q-field {
            width: 100%;
        }
        """
    )

    ui.label("Prompt Iteration Workbench").classes("text-3xl font-bold")
    ui.label("Adversarial prompt iteration workspace").classes("text-sm text-gray-600")

    with ui.row().classes("w-full items-start gap-6"):
        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Project Inputs").classes("text-xl font-semibold")
            project_title_input = ui.input(
                label="Project title",
                placeholder="Example: Ultimate Chili Recipe",
            ).classes("piw-field")
            outcome_input = ui.textarea(label="Outcome", placeholder="Example: Skin Cream Formulation").props(
                "autogrow"
            ).classes("piw-field")
            requirements_input = ui.textarea(
                label="Requirements and constraints", placeholder="Must-haves and must-nots"
            ).props("autogrow").classes("piw-field")
            resources_input = ui.textarea(
                label="Special equipment, ingredients, skills",
                placeholder="Anything non-standard available to you",
            ).props("autogrow").classes("piw-field")

        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Phase Controls").classes("text-xl font-semibold")
            iterations_input = ui.number(
                label="Iterations (additive + reductive pairs)", value=1, min=1, step=1
            ).props("outlined").classes("piw-field")
            format_input = ui.select(options=FORMAT_OPTIONS, value="Markdown", label="Format selector").classes(
                "piw-field"
            )
            additive_tier_input = ui.select(
                options=MODEL_TIER_OPTIONS,
                value="budget",
                label="Additive phase model tier",
            ).classes("piw-field")
            reductive_tier_input = ui.select(
                options=MODEL_TIER_OPTIONS,
                value="budget",
                label="Reductive phase model tier",
            ).classes("piw-field")
            additive_rules_input = ui.textarea(
                label="Additive phase allowed changes",
                placeholder="What additive steps are allowed to change",
            ).props("autogrow").classes("piw-field")
            reductive_rules_input = ui.textarea(
                label="Reductive phase allowed changes",
                placeholder="What reductive steps are allowed to change",
            ).props("autogrow").classes("piw-field")

    with ui.row().classes("w-full items-start gap-6"):
        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Prompt Templates").classes("text-xl font-semibold")
            additive_template_input = ui.textarea(
                label="Additive prompt template",
                placeholder="Template text for additive phase",
            ).props("autogrow").classes("piw-field")
            reductive_template_input = ui.textarea(
                label="Reductive prompt template",
                placeholder="Template text for reductive phase",
            ).props("autogrow").classes("piw-field")
            with ui.row().classes("w-full gap-2"):
                ui.button("Preview additive", on_click=lambda: preview_template("additive"))
                ui.button("Preview reductive", on_click=lambda: preview_template("reductive"))

        with ui.card().classes("w-full lg:w-1/2"):
            ui.label("Current Output").classes("text-xl font-semibold")
            current_output_input = ui.textarea(
                label="Current output (editable)",
                placeholder="Current working draft",
            ).props("autogrow").classes("piw-field")

            async def copy_current_output_action() -> None:
                content = str(current_output_input.value or "")
                try:
                    await ui.run_javascript(
                        f"navigator.clipboard.writeText({json.dumps(content)});"
                    )
                    ui.notify("Current output copied to clipboard.", type="positive")
                except Exception as exc:
                    LOGGER.exception("Copy to clipboard failed.")
                    set_error(f"Copy failed: {exc}")
                    ui.notify("Copy to clipboard failed.", type="negative")

            with ui.row().classes("w-full justify-end"):
                ui.button("Copy output", on_click=copy_current_output_action).props("size=sm")

    with ui.dialog() as preview_dialog, ui.card().classes("w-[92vw] max-w-5xl"):
        preview_title = ui.label("Rendered prompt preview").classes("text-lg font-semibold")
        preview_validation_label = ui.label("Validation: OK").classes("text-sm")
        preview_textarea = ui.textarea(label="Rendered prompt").props("readonly autogrow").classes("w-full")
        ui.button("Close", on_click=preview_dialog.close)

    with ui.card().classes("w-full"):
        ui.label("History").classes("text-xl font-semibold")
        history_container = ui.column().classes("w-full gap-2")

        async def generate_change_summary_action(record_index: int) -> None:
            try:
                set_status("Running")
                set_error("None")
                source_state = state_from_ui()
                next_state = await asyncio.to_thread(
                    lambda: generate_change_summary_for_record(
                        source_state,
                        record_index=record_index,
                        tier="budget",
                    )
                )
                apply_state(next_state)
                set_status("Idle")
                ui.notify("Change summary generated.", type="positive")
            except LLMError as exc:
                LOGGER.exception("Generate change summary failed with normalized LLM error.")
                set_status("Error")
                set_error(exc.message)
                ui.notify(exc.message, type="negative")
            except Exception as exc:
                LOGGER.exception("Generate change summary failed unexpectedly.")
                set_status("Error")
                set_error(f"Generate change summary failed: {exc}")
                ui.notify("Generate change summary failed.", type="negative")

        def restore_history_entry_action(record_index: int) -> None:
            try:
                restored_output, restored_history = restore_history_snapshot(
                    history_records,
                    record_index=record_index,
                )
                current_output_input.value = restored_output
                history_records.clear()
                history_records.extend(restored_history)
                render_history()
                refresh_validation_status()
                set_status("Restored")
                set_error("None")
                ui.notify("Current output restored from selected history entry.", type="positive")
            except IndexError:
                LOGGER.exception("Restore failed because history index was out of range.")
                set_status("Error")
                set_error("Restore failed: selected history entry is out of range.")
                ui.notify("Restore failed: invalid history selection.", type="negative")
            except Exception as exc:
                LOGGER.exception("Restore failed unexpectedly.")
                set_status("Error")
                set_error(f"Restore failed: {exc}")
                ui.notify("Restore failed.", type="negative")

        def render_history() -> None:
            history_container.clear()
            with history_container:
                if not history_records:
                    ui.label("No history entries yet. Run iterations to populate this panel.").classes(
                        "text-sm text-gray-600"
                    )
                    return
                for index, record in enumerate(history_records):
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

                        if index == 0:
                            ui.label("Diff vs previous entry: no prior diff is available.").classes(
                                "text-sm text-gray-600"
                            )
                        else:
                            previous_snapshot = history_records[index - 1].output_snapshot
                            diff_text = unified_text_diff(previous_snapshot, record.output_snapshot)
                            if not diff_text:
                                diff_text = "(no textual changes from previous entry)"
                            ui.textarea(
                                label="Diff vs previous entry",
                                value=diff_text,
                            ).props("readonly autogrow").classes("w-full")

                        if record.change_summary.strip():
                            ui.markdown(record.change_summary.strip()).classes("text-sm")
                        else:
                            ui.label("Change summary: (none)").classes("text-sm text-gray-600")

                        async def generate_change_summary_click(idx: int = index) -> None:
                            await generate_change_summary_action(idx)

                        ui.button(
                            "Generate change summary",
                            on_click=generate_change_summary_click,
                        ).props("size=sm")
                        ui.button(
                            "Restore this output",
                            on_click=lambda idx=index: restore_history_entry_action(idx),
                        ).props("size=sm")

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

        def load_project_picker_action(event: UploadEventArguments) -> None:
            nonlocal last_saved_path
            try:
                payload_text = event.content.read().decode("utf-8")
                loaded = load_project_from_text(payload_text)
                apply_state(loaded)

                PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
                last_saved_path = PROJECTS_DIR / _sanitize_upload_filename(event.name)
                last_saved_path_label.set_text(f"Last saved path: {last_saved_path}")
                last_saved_time_label.set_text("Last saved time: (not saved since picker load)")
                set_status("Idle")
                set_error("None")
                ui.notify(f"Loaded project from picker: {event.name}", type="positive")
            except Exception as exc:
                LOGGER.exception("Load from file picker failed unexpectedly.")
                set_status("Error")
                set_error(f"Load from picker failed: {exc}")
                ui.notify("Load from file picker failed.", type="negative")

        ui.label("Load project via file picker").classes("text-sm text-gray-700")
        ui.upload(
            on_upload=load_project_picker_action,
            auto_upload=True,
        ).props("accept=.json").classes("w-full")

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
            project_title=str(project_title_input.value or ""),
            outcome=str(outcome_input.value or ""),
            requirements_constraints=str(requirements_input.value or ""),
            special_resources=str(resources_input.value or ""),
            iterations=int(iterations_input.value or 1),
            output_format=str(format_input.value or "Markdown"),
            additive_phase_model_tier=str(additive_tier_input.value or "budget"),
            reductive_phase_model_tier=str(reductive_tier_input.value or "budget"),
            additive_phase_allowed_changes=str(additive_rules_input.value or ""),
            reductive_phase_allowed_changes=str(reductive_rules_input.value or ""),
            additive_prompt_template=str(additive_template_input.value or ""),
            reductive_prompt_template=str(reductive_template_input.value or ""),
            current_output=str(current_output_input.value or ""),
            history=[IterationRecord(**record.__dict__) for record in history_records],
        )

    def next_phase_metadata(state: ProjectState) -> tuple[str, int]:
        phase_record_count = sum(
            1
            for record in state.history
            if record.event_type == HISTORY_EVENT_PHASE_STEP and record.phase_name in ("additive", "reductive")
        )
        phase_name = "additive" if phase_record_count % 2 == 0 else "reductive"
        iteration_index = (phase_record_count + 2) // 2
        return phase_name, iteration_index

    def apply_state(state: ProjectState) -> None:
        nonlocal is_applying_state
        is_applying_state = True
        try:
            project_title_input.value = state.project_title
            outcome_input.value = state.outcome
            requirements_input.value = state.requirements_constraints
            resources_input.value = state.special_resources
            iterations_input.value = state.iterations
            format_input.value = state.output_format
            additive_tier_input.value = state.additive_phase_model_tier
            reductive_tier_input.value = state.reductive_phase_model_tier
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
            title = str(project_title_input.value or "").strip()
            last_saved_path = _next_available_project_path(title, PROJECTS_DIR)
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

        async def generate_prompts_action() -> None:
            try:
                source_state = state_from_ui()
                existing_additive = str(additive_template_input.value or "")
                existing_reductive = str(reductive_template_input.value or "")
                overwrite_existing = bool(overwrite_templates_toggle.value)
                needs_additive = overwrite_existing or not existing_additive.strip()
                needs_reductive = overwrite_existing or not existing_reductive.strip()

                # Do not spend LLM calls when both templates already exist unless overwrite is enabled.
                if not needs_additive and not needs_reductive:
                    set_status("Idle")
                    set_error("None")
                    ui.notify(
                        "Generate prompts skipped: templates already exist. Enable overwrite to regenerate.",
                        type="info",
                    )
                    return

                set_status("Running")
                set_error("None")
                if needs_additive and needs_reductive:
                    generated_additive, generated_reductive, notes = await asyncio.to_thread(
                        lambda: generate_templates(source_state)
                    )
                else:
                    generated_additive = existing_additive
                    generated_reductive = existing_reductive
                    note_parts: list[str] = []
                    if needs_additive:
                        generated_additive, additive_note = await asyncio.to_thread(
                            lambda: generate_template_for_phase(source_state, "additive")
                        )
                        note_parts.append(additive_note)
                    else:
                        note_parts.append("additive: preserved")
                    if needs_reductive:
                        generated_reductive, reductive_note = await asyncio.to_thread(
                            lambda: generate_template_for_phase(source_state, "reductive")
                        )
                        note_parts.append(reductive_note)
                    else:
                        note_parts.append("reductive: preserved")
                    notes = "; ".join(note_parts)

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
                    existing_additive=existing_additive,
                    existing_reductive=existing_reductive,
                    generated_additive=generated_additive,
                    generated_reductive=generated_reductive,
                    overwrite_existing=overwrite_existing,
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
                LOGGER.exception("Generate prompts failed with PromptArchitectError.")
                set_status("Error")
                set_error(exc.message)
                ui.notify(exc.message, type="negative")
            except Exception as exc:
                LOGGER.exception("Generate prompts failed unexpectedly.")
                set_status("Error")
                set_error(f"Generate prompts failed: {exc}")
                ui.notify("Generate prompts failed.", type="negative")

        async def run_next_step_action() -> None:
            nonlocal is_run_active
            if is_run_active:
                ui.notify("A run is already active.", type="warning")
                return
            try:
                is_run_active = True
                set_error("None")
                source_state = state_from_ui()
                phase_name, iteration_index = next_phase_metadata(source_state)
                set_status(f"Running {phase_name} step of iteration {iteration_index}")
                next_state = await asyncio.to_thread(lambda: run_next_step(source_state))
                apply_state(next_state)
                set_status("Idle")
                refresh_validation_status()
                notify_click("Run next step completed.")
            except Exception as exc:
                LOGGER.exception("Run next step failed unexpectedly.")
                set_status("Error")
                set_error(f"Run next step failed: {exc}")
                ui.notify("Run next step failed.", type="negative")
            finally:
                is_run_active = False

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
                LOGGER.exception("Save failed unexpectedly.")
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
                LOGGER.exception("Load failed unexpectedly.")
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
                set_error("None")

                total_phase_steps = requested_iterations * 2
                steps_completed = 0
                current_state = state_from_ui()
                cancelled = False

                for _ in range(total_phase_steps):
                    if stop_requested:
                        cancelled = True
                        break

                    phase_name, _ = next_phase_metadata(current_state)
                    iteration_in_run = (steps_completed // 2) + 1
                    set_status(
                        f"Running {phase_name} step of iteration {iteration_in_run} of {requested_iterations}"
                    )
                    current_state = await asyncio.to_thread(
                        lambda state=current_state: run_next_step(state)
                    )
                    steps_completed += 1
                    apply_state(current_state)
                    refresh_validation_status()
                    await asyncio.sleep(0)

                if cancelled:
                    set_status("Stopped")
                    ui.notify(
                        f"Run stopped after {steps_completed} phase steps.",
                        type="warning",
                    )
                else:
                    set_status("Idle")
                    notify_click(f"Run iterations completed ({steps_completed} phase steps).")
            except Exception as exc:
                LOGGER.exception("Run iterations failed unexpectedly.")
                set_status("Error")
                set_error(f"Run iterations failed: {exc}")
                ui.notify("Run iterations failed.", type="negative")
            finally:
                is_run_active = False
                stop_button.disable()
                stop_requested = False

        run_iterations_button.on_click(run_iterations_action)

    for editable in [
        project_title_input,
        outcome_input,
        requirements_input,
        resources_input,
        iterations_input,
        format_input,
        additive_tier_input,
        reductive_tier_input,
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
    _configure_logging()
    print(f"Starting Prompt Iteration Workbench at http://{host}:{port}")
    build_ui()
    ui.run(host=host, port=port, title="Prompt Iteration Workbench", show=False, reload=False)


if __name__ == "__main__":
    main()
