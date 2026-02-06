"""Minimal NiceGUI entrypoint for Prompt Iteration Workbench."""

from __future__ import annotations

from nicegui import ui


def build_ui() -> None:
    """Render the initial placeholder UI for local runs."""
    ui.label("Prompt Iteration Workbench").classes("text-2xl font-bold")
    ui.label("Checkpoint 1.2 placeholder UI is running.")


def main() -> None:
    host = "127.0.0.1"
    port = 8080
    print(f"Starting Prompt Iteration Workbench at http://{host}:{port}")
    build_ui()
    ui.run(host=host, port=port, title="Prompt Iteration Workbench", show=False, reload=False)


if __name__ == "__main__":
    main()
