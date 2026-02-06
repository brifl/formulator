"""Workflow wrapper tests for tools/agentctl.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_wrapper_module():
    wrapper_path = Path("tools/agentctl.py").resolve()
    spec = importlib.util.spec_from_file_location("tools_agentctl_wrapper", wrapper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tools/agentctl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_apply_next_hint_override_for_repeated_improvements_state() -> None:
    mod = _load_wrapper_module()

    decision = {
        "recommended_role": "improvements",
        "recommended_prompt_id": "prompt.process_improvements",
        "reason": "Work log has 21 entries (>15).",
        "stage": "8",
        "checkpoint": "8.2",
        "status": "NOT_STARTED",
    }
    loop_result = {
        "loop": "improvements",
        "result": "completed",
        "stage": "8",
        "checkpoint": "8.2",
        "status": "NOT_STARTED",
        "next_role_hint": "implement",
    }

    patched = mod._apply_next_hint_override(decision, loop_result)

    assert patched["recommended_role"] == "implement"
    assert patched["recommended_prompt_id"] == "prompt.checkpoint_implementation"
    assert "honoring next_role_hint" in patched["reason"]


def test_apply_next_hint_override_noop_when_state_differs() -> None:
    mod = _load_wrapper_module()

    decision = {
        "recommended_role": "improvements",
        "recommended_prompt_id": "prompt.process_improvements",
        "reason": "Work log has 21 entries (>15).",
        "stage": "8",
        "checkpoint": "8.3",
        "status": "NOT_STARTED",
    }
    loop_result = {
        "loop": "improvements",
        "result": "completed",
        "stage": "8",
        "checkpoint": "8.2",
        "status": "NOT_STARTED",
        "next_role_hint": "implement",
    }

    patched = mod._apply_next_hint_override(decision, loop_result)

    assert patched["recommended_role"] == "improvements"
    assert patched["recommended_prompt_id"] == "prompt.process_improvements"


def test_apply_work_log_threshold_override_routes_to_implement() -> None:
    mod = _load_wrapper_module()

    decision = {
        "recommended_role": "improvements",
        "recommended_prompt_id": "prompt.process_improvements",
        "reason": "Work log has 27 entries (>15).",
    }

    patched = mod._apply_work_log_threshold_override(decision)

    assert patched["recommended_role"] == "implement"
    assert patched["recommended_prompt_id"] == "prompt.checkpoint_implementation"
    assert "work-log threshold" in patched["reason"].lower()


def test_apply_work_log_threshold_override_noop_for_other_reasons() -> None:
    mod = _load_wrapper_module()

    decision = {
        "recommended_role": "improvements",
        "recommended_prompt_id": "prompt.process_improvements",
        "reason": "Context snapshot missing (.vibe/CONTEXT.md).",
    }

    patched = mod._apply_work_log_threshold_override(decision)

    assert patched["recommended_role"] == "improvements"
    assert patched["recommended_prompt_id"] == "prompt.process_improvements"
