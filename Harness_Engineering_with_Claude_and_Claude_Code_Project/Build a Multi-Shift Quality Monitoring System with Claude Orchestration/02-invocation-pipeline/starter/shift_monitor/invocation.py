"""Three invocation shapes.

thin     — prompt only.
rich     — hot state + new defects.
resumed  — prior partial findings + new defects since the last manifest step.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from .state import HotState

InvocationShape = Literal["thin", "rich", "resumed"]


@dataclass(frozen=True)
class Invocation:
    shape: InvocationShape
    prompt: str


def thin(prompt: str) -> Invocation:
    # TODO: Return an Invocation with shape="thin" and the prompt unchanged.
    # The thin shape is for one-shot calls that don't need any project state.
    return Invocation(shape="thin", prompt=prompt)


def rich(
    role: str, hot_state: HotState, new_defects: Sequence[Mapping[str, Any]]
) -> Invocation:
    # TODO: Build a rich prompt that includes:
    #   - A one-line role framing ("You are the on-call {role} for Northridge Plant 3.")
    #   - A "## Current hot state" section listing recent_defect_hashes,
    #     current_shift_summary, active_alerts, threshold_statuses.
    #   - A "## New defects since last shift" section enumerating each new defect
    #     (id / ts / shift / component / severity / description).
    #   - A trailing instruction asking for: Summary, Findings, Recommended
    #     actions, and an Updated hot state proposal as a JSON block.
    # Return an Invocation with shape="rich" and the rendered prompt.
    lines = [f"You are the on-call {role} for Northridge Plant 3.", ""]

    lines.append("## Current hot state")
    lines.append(f"- Recent defect hashes: {hot_state.recent_defect_hashes}")
    lines.append(f"- Current shift summary: {hot_state.current_shift_summary}")
    lines.append(f"- Active alerts: {hot_state.active_alerts}")
    lines.append(f"- Threshold statuses: {hot_state.threshold_statuses}")
    lines.append("")

    lines.append("## New defects since last shift")
    if new_defects:
        for defect in new_defects:
            lines.append(
                f"- ID: {defect.get('id')} | TS: {defect.get('ts')} | "
                f"Shift: {defect.get('shift')} | Component: {defect.get('component')} | "
                f"Severity: {defect.get('severity')} | Description: {defect.get('description')}"
            )
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("Please provide the following:")
    lines.append("1. Summary")
    lines.append("2. Findings")
    lines.append("3. Recommended actions")
    lines.append("4. Updated hot state proposal as a JSON block.")

    prompt_text = "\n".join(lines)
    return Invocation(shape="rich", prompt=prompt_text)


def resumed(
    session_id: str,
    summary: str,
    latest_message: str,
    prior_steps: Sequence[Mapping[str, Any]],
    new_defects: Sequence[Mapping[str, Any]],
) -> Invocation:
    # TODO: Build a resumed prompt with three required sections:
    #   - "## Prior partial findings" — one line per prior step, showing its
    #     `name` and a truncated representation of its `payload`.
    #   - "## Prior summary" — the supplied summary string.
    #   - "## New defects since last partial step" — enumerate new_defects
    #     (id / ts / component / severity / description), or "- (none)" if empty.
    # Close with the latest_message under "## Latest instruction".
    # Return an Invocation with shape="resumed".
    lines = []

    lines.append("## Prior partial findings")
    if prior_steps:
        for step in prior_steps:
            name = step.get("name", "unknown")
            payload = step.get("payload", "")     
            payload_str = str(payload)
            if len(payload_str) > 100:
                payload_str = payload_str[:97] + "..."
            lines.append(f"- {name}: {payload_str}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Prior summary")
    lines.append(summary)
    lines.append("")

    lines.append("## New defects since last partial step")
    if new_defects:
        for defect in new_defects:
            lines.append(
                f"- ID: {defect.get('id')} | TS: {defect.get('ts')} | "
                f"Component: {defect.get('component')} | Severity: {defect.get('severity')} | "
                f"Description: {defect.get('description')}"
            )
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Latest instruction")
    lines.append(latest_message)

    prompt_text = "\n".join(lines)
    return Invocation(shape="resumed", prompt=prompt_text)
