"""Shift pipeline: SQL pre-filter, prompt build, single Claude call, atomic state update."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .client import ClaudeClient, Message
from .invocation import rich
from .scratchpad import Scratchpad, ScratchpadEntry
from .state import HOT_STATE_BYTE_BUDGET, MAX_RECENT_HASHES, HotState
from .warm import WarmStore

log = logging.getLogger(__name__)

JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass(frozen=True)
class ShiftResult:
    shift_id: str
    new_defect_count: int
    summary: str


def gather_new_defects(
    warm: WarmStore, since_ts: str, limit: int = 50
) -> list[dict[str, Any]]:
    # TODO: Return WarmStore.defects_since(since_ts, limit=limit) — nothing more.
    # This must be a pure pass-through to SQL. No Python-side filtering of
    # severity, component, or time. The test scans this function's source with
    return warm.defects_since(since_ts, limit=limit)

def build_rich_prompt(
    role: str, hot_state: HotState, new_defects: Sequence[Mapping[str, Any]]
) -> str:
    # TODO: Build a rich invocation and return its rendered prompt string.
    return rich(role, hot_state, new_defects).prompt


def _parse_hot_state_update(response_text: str) -> dict[str, Any] | None:
    match = JSON_FENCE_RE.search(response_text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _short_summary_from_response(response_text: str, shift_id: str) -> str:
    for line in response_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
            return stripped[:200]
    return f"Shift {shift_id}: no summary extracted."


def _new_hashes(new_defects: Sequence[Mapping[str, Any]], prior: Sequence[str]) -> list[str]:
    incoming = [d["id"] for d in new_defects]
    merged: list[str] = []
    for h in incoming + list(prior):
        if h not in merged:
            merged.append(h)
        if len(merged) >= MAX_RECENT_HASHES:
            break
    return merged


def _trim_to_budget(state: HotState) -> HotState:
    if len(state.to_json_bytes()) <= HOT_STATE_BYTE_BUDGET:
        return state
    alerts = list(state.active_alerts)
    while alerts and len(state.to_json_bytes()) > HOT_STATE_BYTE_BUDGET:
        alerts.pop()
        state = state.model_copy(update={"active_alerts": alerts})
    return state


def run_shift(
    shift_id: str,
    client: ClaudeClient,
    warm: WarmStore,
    hot_state_path: Path,
    scratchpad_path: Path,
    since_ts: str,
    role: str = "quality engineer",
) -> ShiftResult:
    # TODO: One shift = exactly one Claude call. Walk the pipeline end to end:
    #
    #   1. Read the prior HotState from hot_state_path.
    #   2. Pull new defects via gather_new_defects (SQL side, no Python filter).
    #   3. Build the rich prompt with build_rich_prompt(role, hot_state, new_defects).
    #   4. Call client.complete([Message(role="user", content=prompt)]) exactly once.
    #   5. Parse the response's JSON fence (use _parse_hot_state_update) for an
    #      updated current_shift_summary, active_alerts, and threshold_statuses.
    #      Fall back to the prior values when a field is missing.
    #   6. Build the updated HotState (use _new_hashes for the hash list, then
    #      _trim_to_budget to honor the 5_120-byte ceiling).
    #   7. Write the updated HotState atomically to hot_state_path.
    #   8. Append one ScratchpadEntry to scratchpad_path summarising this shift
    #      (hypothesis_id=f"shift-{shift_id}", evidence + conclusion derived
    #      from the response, ts=datetime.now(UTC)).
    #   9. Return ShiftResult(shift_id, new_defect_count, summary).
    if hot_state_path.exists():
        hot_state = HotState.from_path(hot_state_path)
    else:
        hot_state = HotState()

    new_defects = gather_new_defects(warm, since_ts)

    prompt = build_rich_prompt(role, hot_state, new_defects)

    response = client.complete([Message(role="user", content=prompt)])
    response_text = response.content

    update_dict = _parse_hot_state_update(response_text) or {}

    current_shift_summary = update_dict.get("current_shift_summary")
    if not current_shift_summary:
        current_shift_summary = _short_summary_from_response(response_text, shift_id)

    active_alerts = update_dict.get("active_alerts")
    if active_alerts is None:
        active_alerts = list(hot_state.active_alerts)

    threshold_statuses = update_dict.get("threshold_statuses")
    if threshold_statuses is None:
        threshold_statuses = dict(hot_state.threshold_statuses)

    updated_hashes = _new_hashes(new_defects, hot_state.recent_defect_hashes)
    candidate_state = HotState(
        recent_defect_hashes=updated_hashes,
        current_shift_summary=current_shift_summary,
        active_alerts=active_alerts,
        threshold_statuses=threshold_statuses,
    )
    trimmed_state = _trim_to_budget(candidate_state)

    trimmed_state.write_atomic(hot_state_path)

    entry = ScratchpadEntry(
        hypothesis_id=f"shift-{shift_id}",
        evidence=f"Evaluated {len(new_defects)} new defects since {since_ts}.",
        conclusion=current_shift_summary,
        ts=datetime.now(UTC),
    )
    if scratchpad_path.exists():
        pad = Scratchpad.from_path(scratchpad_path)
    else:
        pad = Scratchpad(path=scratchpad_path)
    pad.append(entry)


    return ShiftResult(
        shift_id=shift_id,
        new_defect_count=len(new_defects),
        summary=current_shift_summary,
    )