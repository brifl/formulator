#!/usr/bin/env python3
"""Repo-local wrapper for the workflow agentctl implementation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROLE_TO_PROMPT_ID: dict[str, str] = {
    "design": "prompt.stage_design",
    "implement": "prompt.checkpoint_implementation",
    "review": "prompt.checkpoint_review",
    "issues_triage": "prompt.issues_triage",
    "consolidation": "prompt.consolidation",
    "context_capture": "prompt.context_capture",
    "improvements": "prompt.process_improvements",
    "advance": "prompt.advance_checkpoint",
}


def _arg_value(args: list[str], option: str) -> str | None:
    for index, token in enumerate(args):
        if token == option and index + 1 < len(args):
            return args[index + 1]
    return None


def _is_json_next(args: list[str]) -> bool:
    return "next" in args and (_arg_value(args, "--format") or "").lower() == "json"


def _load_last_loop_result(repo_root: Path) -> dict[str, object] | None:
    target = repo_root / ".vibe" / "LOOP_RESULT.json"
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _should_override_to_next_hint(
    decision: dict[str, object],
    loop_result: dict[str, object] | None,
) -> bool:
    if not isinstance(loop_result, dict):
        return False
    if str(decision.get("recommended_role", "")) != "improvements":
        return False
    reason_text = str(decision.get("reason", ""))
    if "Work log has" not in reason_text:
        return False
    if str(loop_result.get("loop", "")) != "improvements":
        return False
    if str(loop_result.get("result", "")) != "completed":
        return False
    if str(loop_result.get("stage", "")) != str(decision.get("stage", "")):
        return False
    if str(loop_result.get("checkpoint", "")) != str(decision.get("checkpoint", "")):
        return False
    if str(loop_result.get("status", "")).upper() != str(decision.get("status", "")).upper():
        return False
    next_hint = str(loop_result.get("next_role_hint", "")).strip()
    if next_hint not in ROLE_TO_PROMPT_ID:
        return False
    if next_hint == "improvements":
        return False
    return True


def _apply_next_hint_override(
    decision: dict[str, object],
    loop_result: dict[str, object] | None,
) -> dict[str, object]:
    patched = dict(decision)
    if not _should_override_to_next_hint(decision, loop_result):
        return patched

    next_hint = str(loop_result.get("next_role_hint", "")).strip()
    patched["recommended_role"] = next_hint
    patched["recommended_prompt_id"] = ROLE_TO_PROMPT_ID[next_hint]
    patched["recommended_prompt_title"] = f"Checkpoint via next_role_hint ({next_hint})"
    patched["reason"] = (
        "Recent improvements loop completed for this same state; "
        f"honoring next_role_hint '{next_hint}'."
    )
    return patched


def _apply_work_log_threshold_override(decision: dict[str, object]) -> dict[str, object]:
    patched = dict(decision)
    if str(patched.get("recommended_role", "")) != "improvements":
        return patched
    reason_text = str(patched.get("reason", ""))
    if "Work log has" not in reason_text:
        return patched
    patched["recommended_role"] = "implement"
    patched["recommended_prompt_id"] = ROLE_TO_PROMPT_ID["implement"]
    patched["recommended_prompt_title"] = "Checkpoint via work-log threshold fallback (implement)"
    patched["reason"] = (
        "Work-log threshold triggered improvements routing; "
        "wrapper fallback selects implement to avoid repeated workflow starvation."
    )
    return patched


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    target = repo_root / ".codex" / "skills" / "vibe-loop" / "scripts" / "agentctl.py"
    if not target.exists():
        print(f"ERROR: fallback agentctl not found: {target}", file=sys.stderr)
        return 2

    args = list(sys.argv[1:])
    cmd = [sys.executable, str(target), *args]

    if _is_json_next(args):
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        if completed.returncode != 0:
            if completed.stdout:
                sys.stdout.write(completed.stdout)
            return int(completed.returncode)

        try:
            decision = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            if completed.stdout:
                sys.stdout.write(completed.stdout)
            return int(completed.returncode)

        if isinstance(decision, dict):
            patched = _apply_next_hint_override(decision, _load_last_loop_result(repo_root))
            patched = _apply_work_log_threshold_override(patched)
            sys.stdout.write(json.dumps(patched, indent=2, sort_keys=True) + "\n")
            return 0

        if completed.stdout:
            sys.stdout.write(completed.stdout)
        return 0

    completed = subprocess.run(cmd)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
