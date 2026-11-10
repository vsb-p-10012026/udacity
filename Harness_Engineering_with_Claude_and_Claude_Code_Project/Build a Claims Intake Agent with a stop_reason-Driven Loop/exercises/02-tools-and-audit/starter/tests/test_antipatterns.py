"""Anti-pattern audit.

Verifies, by static AST analysis, that the agentic loop does NOT:
- use string-membership tests against text content to drive control flow
- use an integer-literal iteration cap as its primary stopping mechanism
- omit reference to `stop_reason` as the loop-breaking signal

And that the package broadly does not branch on `claim_type` equality
outside of the tool-schema definitions and the cost-estimate module.

Each test parses the relevant file with `ast` and walks the tree. There are
no runtime imports of claims_intake here — the audit is static, so it works
even if loop.py / tools.py do not run end-to-end.
"""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "claims_intake"
LOOP_PY = PKG / "loop.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ---------------------------------------------------------------------------
# Anti-pattern 1 — no string-membership tests against assistant text in the loop
# ---------------------------------------------------------------------------
def test_no_string_membership_against_text_in_loop() -> None:
    """No `"some_token" in <something>` expressions in loop.py.

    Heuristic: any `ast.Compare` node using `ast.In` whose `left` operand is a
    string `ast.Constant` is flagged. The loop has no legitimate reason to test
    for the presence of a magic string inside the model's output — that would be
    natural-language-driven control flow.
    """
    # TODO: Parse LOOP_PY into an AST. Walk every node. For each
    # ast.Compare, look at its `ops` — if any op is ast.In AND `node.left` is an
    # ast.Constant holding a `str`, append `ast.unparse(node)` to an offenders list.
    # Assert the offenders list is empty; include the offending expressions in the
    # failure message so a reader can find the bad line.
    tree = _parse(LOOP_PY)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            has_in = any(isinstance(op, ast.In) for op in node.ops)
            if has_in:
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    offenders.append(ast.unparse(node))
    assert not offenders, (
        f"Found string-membership tests against text in loop.py (natural-language-driven control flow):\n"
        f"{'\n'.join(offenders)}"
    )

# ---------------------------------------------------------------------------
# Anti-pattern 2 — no integer-literal iteration cap as the primary stop mechanism
# ---------------------------------------------------------------------------
def test_no_integer_literal_iteration_cap_in_loop() -> None:
    """No `for _ in range(<int literal>)` and no `while <var> < <int literal>` in loop.py.

    Token/wall-clock/config-sourced budgets are explicitly allowed because they
    read their cap from a `Budget` instance (an attribute access or a function
    arg), not from a literal. If you need a cap, pass it in.
    """
    # TODO: Walk LOOP_PY's AST. Flag:
    #   - any ast.For whose iter is `range(<int literal>, ...)`
    #     (ast.Call to a Name "range" with at least one Constant int arg)
    #   - any ast.While whose test is an ast.Compare with an int Constant on the right
    # Assert the offenders list is empty. Mention "use a Budget instead" in the failure
    # message so the reader sees the recommended fix.
    tree = _parse(LOOP_PY)
    offenders=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                if node.iter.args and any(isinstance(arg, ast.Constant) and isinstance(arg.value, int) for arg in node.iter.args):
                    offenders.append(ast.unparse(node))
        elif isinstance(node, ast.While):
            if isinstance(node.test, ast.Compare):
                has_int_constant=any(
                    isinstance(comp, ast.Constant) and isinstance(comp.value, int)
                    for comp in node.test.comparators
                )
                if has_int_constant:
                    offenders.append(ast.unparse(node))
    assert not offenders, (
        f"Found integer-literal iteration caps in loop.py. Use a Budget instead:\n"
        f"{'\n' .join(offenders)}"
    )

# ---------------------------------------------------------------------------
# Positive evidence — stop_reason is the value that breaks the while loop
# ---------------------------------------------------------------------------
def test_stop_reason_is_loop_control() -> None:
    """loop.py references `stop_reason` AND a `while` loop exits via return/raise on it."""
    # TODO: Parse LOOP_PY. Walk the tree:
    #   1. Assert there is at least one reference to `stop_reason` (either as an
    #      ast.Attribute named `stop_reason` or an ast.Name named `stop_reason`).
    #   2. Find every ast.While node. For at least one of them, the unparsed body
    #      must mention BOTH "stop_reason" AND ("return" OR "raise"). That is what
    #      "the loop exits on stop_reason" looks like at the AST level.
    # Fail with a clear message if either condition is missing.
    tree = _parse(LOOP_PY)
    has_stop_reason_ref = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "stop_reason":
            has_stop_reason_ref = True
            break
        elif isinstance(node, ast.Name) and node.id == "stop_reason":
            has_stop_reason_ref = True
            break
    assert has_stop_reason_ref, "loop.py must reference `stop_reason` to drive control flow."
    valid_while_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            body_source = ast.unparse(node.body)
            mentions_stop_reason = "stop_reason" in body_source
            mentions_exit =  "return" in body_source or "raise" in body_source
            if mentions_stop_reason and mentions_exit:
                valid_while_found = True
                break
    assert valid_while_found, (
        "No `while` loop in loop.py was found that checks `stop_reason` and exits via `return` or `raise`."
    )


# ---------------------------------------------------------------------------
# Decision-tree-in-Python — no `if claim_type == "..."` branches in the package
# ---------------------------------------------------------------------------
def test_no_claim_type_equality_branching_in_package() -> None:
    """Decision logic about claim type lives in the model, not in Python.

    tools.py is exempt (it defines the enum in input_schema).
    pricing.py is exempt (it may map claim_type to per-queue cost weights).
    """
    # TODO: Walk every .py file under PKG (recursively). Skip tools.py,
    # pricing.py, and __init__.py. For each file, parse the AST, find every ast.Compare
    # whose operators include ast.Eq and whose left operand is a Name/Attribute named
    # "claim_type" compared against a string Constant. Collect "filename:lineno: <expr>"
    # for each match. Assert the list is empty; recommend in the failure message that
    # you move the decision into the model via tool calls.
    excluded_files = {
        "tools.py",
        "pricing.py",
        "__init__.py"
    }
    offenders = []
    for path in PKG.glob("**/*.py"):
        if path.name in excluded_files:
            continue
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                if any(isinstance(op, ast.Eq) for op in node.ops):
                    left = node.left
                    is_claim_type_left = (
                        (isinstance(left, ast.Name) and left.id == "claim_type") or
                        (isinstance(left, ast.Attribute) and left.attr == "claim_type")
                    )
                    has_string_constant=any(
                        isinstance(comp, ast.Constant) and isinstance(comp.value, str)
                        for comp in node.comparators
                    )
                    if is_claim_type_left and has_string_constant:
                        rel_path = path.relative_to(PKG.parent)
                        offenders.append(f"{rel_path}:{node.lineno}:{ast.unparse(node)}")
    assert not offenders, (
        f"Found `claim_type == '...'` equality branching in the package. "
        f"Move decision logic into the model via tool calls instead:\n"
        f"{'\n' .join(offenders)}"
    )