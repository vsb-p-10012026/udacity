"""Tool schemas and dispatcher.

Seven tools, registered with Anthropic tool-use shape. The dispatcher returns
serialized JSON strings to be wrapped as `tool_result` content. Errors follow
the Playbook "Graceful Tool Failure" shape:

    {"is_error": true,
     "error_category": "transient"|"permanent",
     "is_retryable": bool,
     "message": "..."}

Errors are never raised to the loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claims_intake.session import ClaimSession

CLAIM_TYPES = ["property_damage", "theft", "liability", "auto"]
SEVERITIES = ["low", "medium", "high"]

# ----------------------------------------------------------------------------
# Schemas — passed verbatim to the Anthropic Messages API as the `tools` arg.
# ----------------------------------------------------------------------------

# TODO: Populate TOOL_SCHEMAS with the first four tool schemas. Each schema
# is a dict with "name", "description", and "input_schema". Tool descriptions are read by
# the model on every turn — write them as if you were teaching the model what each tool is
# for and *when* to call it. Categorical fields ("claim_type", "severity") must use
# Anthropic's tool-use `enum` shape against CLAIM_TYPES and SEVERITIES.
#
#   - lookup_policy(policy_id: str)
#     Returns the policy record. Used early in the conversation.
#   - record_claim_fact(field: str, value: str)
#     Records one normalized fact (incident_date, location, items_lost, ...).
#   - classify_claim(claim_type: enum CLAIM_TYPES, confidence: number in [0,1], rationale: str)
#     Commits the model to a claim type with a confidence score.
#   - assess_severity(severity: enum SEVERITIES, rationale: str)
#     Commits the model to a severity bucket.
#
# Later tools (request_clarification, route_to_adjuster, escalate_to_human) extend this list.
TOOL_SCHEMAS: list[dict[str, Any]] = [{
    "name":"lookup_policy",
    "description":"Retrieves the full policy record using a policy ID. Use this early in the conversation to verify coverage and poilcy details.",
    "input_schema":{
        "type":"object",
        "properties":{
            "policy_id":{
                "type":"string",
                "description":"The unique identifier of the insurance policy."
            }
        },
        "required":["policy_id"]
    }
},
{
    "name":"record_claim_fact",
    "description":"Records a single normalized fact about the incident or claim (e.g., incident_date, location, items_lost) into the session context.",
    "input_schema":{
        "type":"object",
        "properties":{
            "field":{
                "type":"string",
                "description":"The name of the fact field being recorded (e.g., 'incident_date', 'location')."
            },
            "value":{
                "type":"string",
                "description":"The normalized value associated with the field."
            }
        },
        "required":["field","value"]
    }
},
{
    "name":"classify_claim",
    "description":"Commits the model to a specific claim type along with a confidence score and explanatory rationale.",
    "input_schema":{
        "type":"object",
        "properties":{
            "claim_type":{
                "type":"string",
                "enum":CLAIM_TYPES,
                "description":"The classified type of the claim."
            },
            "confidence":{
                "type":"number",
                "description":"A float between 0 and 1 representing classification confidence."
            },
            "rationale":{
                "type":"string",
                "description":"The reasoning behind the classification."
            }
        },
        "required": ["claim_type", "confidence", "rationale"]
    }
},
{
    "name":"assess_severity",
    "description":"Commits the model to a severity bucket (low, medium, high) with a supporting rationale.",
    "input_schema":{
        "type":"object",
        "properties":{
            "severity":{
                "type":"string",
                "enum":SEVERITIES,
                "description":"The assessed severity level of the claim."
            },
            "rationale":{
                "type":"string",
                "description":"The reasoning behind the severity assessment."
            }
        },
        "required":["severity", "rationale"]
    }
},
{
    "name":"request_clarification",
    "description":"Asks the claimant a clarifying question when there is ambiguity between multiple options.",
    "input_schema":{
        "type":"object",
        "properties":{
            "question":{
                "type":"string",
                "description":"The clarification question directed at the claimant."
            },
            "ambiguity_between":{
                "type":"array",
                "items":{"type": "string"},
                "description":"A list of at least two items representing the choices or ambiguities being resolved."
            }
        },
        "required":["question", "ambiguity_between"]
    }
},
{
    "name":"route_to_adjuster",
    "description":"Terminal tool that routes a fully classified and assessed claim to the appropriate adjuster queue,",
    "input_schema":{
        "type":"object",
        "properties":{
            "queue":{
                "type":"string",
                "enum":CLAIM_TYPES,
                "description":"The target adjuster queue matching one of the claim types."
            },
            "claim_summary":{
                "type":"string",
                "description":"A comprehensive summary of the claim for the adjuster."
            }
        },
        "required":["queue", "claim_summary"]
    }
},
{
    "name":"escalate_to_human",
    "description":"Terminal tool that escalates a problematic or complex claim to a human supervisor with structured summary details.",
    "input_schema":{
        "type":"object",
        "properties":{
            "reason":{
                "type":"string",
                "description":"The reason why human escalation is required."
            },
            "structured_summary":{
                "type":"object",
                "properties":{
                    "policy_id":{"type":"string"},
                    "root_cause":{"type":"string"},
                    "candidate_claim_types":{
                        "type":"array",
                        "items":{"type":"string"}
                    },
                    "case_facts":{
                        "type":"object",
                        "additionalProperties":{"type":"string"}
                    },
                    "recommended_action":{"type":"string"},
                    "confidence":{"type":"number"}
                },
                "required":[
                    "policy_id",
                    "root_cause",
                    "candidate_claim_types",
                    "case_facts",
                    "recommended_action",
                    "confidence"
                ],
                "description": "Structured metadata summarizing the case history and recommendation."
            }
        },
        "required":["reason", "structured_summary"]
    }
}
]

# ----------------------------------------------------------------------------
# Errors — Graceful Tool Failure shape
# ----------------------------------------------------------------------------


def _err(category: str, retryable: bool, message: str) -> str:
    # TODO: Return a JSON string with these keys (the Graceful Tool Failure shape):
    #   is_error: True
    #   error_category: category   ("transient" or "permanent")
    #   is_retryable: retryable
    #   message: message
    # The shape is what tool_result content carries when the model needs to read an error
    # and adapt rather than crash the loop.
    return json.dumps({
        "is_error":True,
        "error_category":category,
        "is_retryable":retryable,
        "message":message,
    }, ensure_ascii=False)


def _ok(payload: dict[str, Any]) -> str:
    # TODO: Return json.dumps(payload). Tool results are always strings;
    # the model parses them on the next turn.
    return json.dumps(payload, ensure_ascii=False)


# ----------------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------------


def _t_lookup_policy(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Read inp["policy_id"]; if not a string, return a permanent error.
    # Look it up in session.policies; if missing, return a permanent error naming the id.
    # Otherwise return the policy dict via _ok(...).
    policy_id = inp.get("policy_id")
    if not isinstance(policy_id, str):
        return _err("permanent", False, "policy_id must be a string")

    policy = session.policies.get(policy_id)
    if policy is None:
        return _err("permanent", False, f"Policy ID not found: {policy_id!r}")
    return _ok(policy)


def _t_record_claim_fact(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Validate inp["field"] and inp["value"] are both strings; store
    # session.case_facts[field] = value; return _ok with {"recorded": True, "field": field,
    # "case_facts_count": len(session.case_facts)}.
    field_name = inp.get("field")
    value = inp.get("value")
    if not isinstance(field_name, str) or not isinstance(value, str):
        return _err("permanent", False, "Both 'field' and 'value' must be strings")
    session.case_facts[field_name]=value
    return _ok({
        "recorded": True,
        "field": field_name,
        "case_facts_count":len(session.case_facts)
    })


def _t_classify_claim(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Validate claim_type (in CLAIM_TYPES), confidence (number in [0,1]),
    # rationale (string). Store session.classification = {claim_type, confidence, rationale}
    # and return _ok with the recorded values plus {"recorded": True}.
    claim_type=inp.get("claim_type")
    confidence=inp.get("confidence")
    rationale=inp.get("rationale")
    if claim_type not in CLAIM_TYPES:
        return _err("permanent", False, f"Invalid claim_type: {claim_type!r}. Must be one of {CLAIM_TYPES}")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        return _err("permanent", False, "Confidence must be a number between 0 and 1")
    if not isinstance(rationale, str):
        return _err("permanent",  False, "Rationale must be a string")

    classification_data={
        "claim_type": claim_type,
        "confidence": float(confidence),
        "rationale": rationale
    }
    session.classification=classification_data
    return _ok({**classification_data, "recorded":True})


def _t_assess_severity(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Validate severity (in SEVERITIES) and rationale (string).
    # Store session.severity = {severity, rationale} and return _ok with the recorded
    # values plus {"recorded": True}.
    severity=inp.get("severity")
    rationale=inp.get("rationale")
    if severity not in SEVERITIES:
        return _err("permanent", False, f"Invalid severity: {severity!r}. Must be one of {SEVERITIES}")
    if not isinstance(rationale, str):    
        return _err("permanent", False, "Rationale must be a string")

    severity_data={
        "severity":severity,
        "rationale":rationale
    }
    session.severity=severity_data
    return _ok({**severity_data, "recorded": True})


def _t_request_clarification(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Implement the clarification dispatcher.
    #   1. Validate inp["question"] is a string and inp["ambiguity_between"] is a list of
    #      at least 2 entries; otherwise return _err("permanent", False, ...).
    #   2. Record the asked clarification in session.clarifications_asked (so the runner
    #      can count it).
    #   3. Substring-match the question (case-insensitive) against the keys in
    #      session.clarification_responses; if any key appears in the question, return
    #      _ok({"claimant_reply": <the matching reply>}).
    #   4. Otherwise return _ok({"claimant_reply": "NO_RESPONSE"}).
    question=inp.get("question")
    ambiguity_between=inp.get("ambiguity_between")
    if not isinstance(question, str):
        return _err("permanent", False, "question must be a string")
    if not isinstance(ambiguity_between, list) or len(ambiguity_between)<2:
        return _err("permanent", False, "ambiguity_between must be a list containing at least 2 entries")
    session.classification_asked.append(question)
    question_lower = question.lower()
    matching_reply = "NO_RESPONSE"
    for key, reply in session.classification_responses.items():
        if key.lower() in question_lower:
            matching_reply = reply
            break
    return _ok({"claimant_reply": matching_reply})


def _t_route_to_adjuster(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Implement the routing terminal tool.
    #   1. Guard against double-terminal: if session.terminal_called, return an error.
    #   2. Validate inp["queue"] is in CLAIM_TYPES and inp["claim_summary"] is a string.
    #   3. Require session.classification and session.severity to be set; otherwise error.
    #   4. Build the routing record (claim_id, policy_id, claim_type, severity, confidence,
    #      rationale, claim_summary, case_facts) and assign it to session.routing.
    #   5. Append the record to runs/<run>/queues/<queue>.jsonl via _append_jsonl.
    #   6. Return _ok({"routed": True, "queue": queue}).
    if getattr(session, "terminal_called", False):
        return _err("permanent", False, "Terminal tool has already been called for this session.")
    queue = inp.get("queue")
    claim_summary=inp.get("claim_summary")
    if queue not in CLAIM_TYPES:
        return _err("permanent", False, f"Invalid queue: {queue!r}. Must be one of {CLAIM_TYPES}")
    if not isinstance(claim_summary, str):
        return _err("permanent", False, "claim_summary must be a string")
    if not session.classification or not session.severity:
        return _err("permanent", False, "Cannot route to adjuster without prior classification and severity assessment.")
    session.terminal_called=True
    routing_record={
        "claim_id":session.claim_id,
        "policy_id":session.policy_id,
        "claim_type":session.classification["claim_type"],
        "severity":session.severity["severity"],
        "confidence":session.classification["confidence"],
        "rationale":session.classification["rationale"],
        "claim_summary":claim_summary,
        "case_facts":session.case_facts,
    }
    session.routing=routing_record
    run_name=getattr(session, "run_name", "default")
    jsonl_path=Path(f"runs/{run_name}/queues/{queue}.jsonl")
    _append_jsonl(jsonl_path, routing_record)
    return _ok({"routed":True, "queue":queue})


def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    # TODO: Implement the escalation terminal tool.
    #   1. Guard against double-terminal: if session.terminal_called, return an error.
    #   2. Validate inp["reason"] is a string and inp["structured_summary"] is a dict
    #      containing all required keys: policy_id, root_cause, candidate_claim_types,
    #      case_facts, recommended_action, confidence. Return an error listing any missing
    #      fields by name.
    #   3. Build the escalation record (claim_id, policy_id, reason, **structured_summary,
    #      case_facts_at_escalation) and assign it to session.escalation.
    #   4. Append it to runs/<run>/escalations.jsonl via _append_jsonl.
    #   5. Return _ok({"escalated": True}).
    if getattr(session, "terminal_called", False):
        return _err("permanent", False, "Terminal tool has already been called for this session.")
    reason = inp.get("reason")
    structured_summary = inp.get("structured_summary")
    if not isinstance(reason, str):
        return _err("permanent", False, "reason must be a string")
    if not isinstance(structured_summary, dict):
        return _err("permanent", False, "structured_summary must be a dictionary")
    required_keys=[
        "policy_id",
        "root_cause",
        "candidate_claim_types",
        "case_facts",
        "recommended_action",
        "cofidence"
    ]
    missing_fields = [key for key in required_keys if key not in structured_summary]
    if missing_fields:
        return _err("permanent", False, f"Missing required fields in structured_summary:{missing_fields}")
    session.terminal_called=True
    escalation_record={
        "claim_id": session.claim_id,
        "policy_id": session.policy_id,
        "reason": reason,
        **structured_summary,
        "case_facts_at_escalation": session.case_facts,
    }
    session.escalation=escalation_record
    run_name=getattr(session, "run_name", "default")
    jsonl_path = Path(f"runs/{run_name}/escalations.jsonl")
    _append_jsonl(jsonl_path, escalation_record)
    return _ok({"escalated":True})
    


# ----------------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------------


_DISPATCH = {
    "lookup_policy": _t_lookup_policy,
    "record_claim_fact": _t_record_claim_fact,
    "classify_claim": _t_classify_claim,
    "assess_severity": _t_assess_severity,
    "request_clarification": _t_request_clarification,
    "route_to_adjuster": _t_route_to_adjuster,
    "escalate_to_human": _t_escalate_to_human,
}


def make_executor(session: ClaimSession) -> Executor:
    """Return a ToolExecutor callable bound to this session."""

    def execute(name: str, tool_input: dict[str, Any]) -> str:
        handler = _DISPATCH.get(name)
        if handler is None:
            return _err("permanent", False, f"unknown tool: {name}")
        try:
            return handler(session, tool_input)
        except Exception as exc:
            # Defensive: anything raised inside a handler becomes a graceful error,
            # never crashes the loop.
            return _err("transient", True, f"{type(exc).__name__}: {exc}")

    return execute


# Type alias for clarity; the loop only sees a Callable.
Executor = Any


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
