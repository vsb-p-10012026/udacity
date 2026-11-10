---
# TODO: Write the YAML frontmatter for this command. It must include:
#
#   description:   one line, ≥10 characters, naming what the command does
#   argument-hint: short description of how to pass a target (PR ref, diff range, or file path)
#   allowed-tools: a list of READ-ORIENTED tools only — no Edit, Write, NotebookEdit, or
#                  unrestricted Bash.
#
# Granular Bash sub-command allowlisting is the canonical pattern. For example:
#   - Bash(git diff:*)
#   - Bash(git log:*)
#   - Bash(gh pr view:*)
# This lets you allow READ operations on git without unlocking the full shell. The
# command should be able to run `git diff`, `git log`, `gh pr view`, `gh pr checks`,
# etc. — but NOT `git push`, `git commit`, or arbitrary `Bash(...)`.
description: Perform a comprehensive, convention-aligned code review on a PR reference, diff range, or file path.
argument-hint: <pr-ref | diff-range | file-path>
allowed-tools:
  - Grep
  - Glob
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(gh pr view:*)
  - Bash(gh pr checks:*)
  - Bash(gh pr diff:*)
---


# /review — team PR review

You are reviewing the diff identified by `$ARGUMENTS` against this repository's conventions. Apply the path-scoped rules in `.claude/rules/` (they auto-load based on the files touched) and the shared standards in `.claude/standards/`.

## Phase 1 — Interview pattern

<!--
TODO: Write the interview-pattern subsection. The reviewer agent should ask clarifying
      questions BEFORE reporting findings whenever the author's intent is ambiguous.

      Why this matters (and why it's not obvious on first read): without an interview
      step, the reviewer commits to a confidently-wrong verdict on ambiguous changes —
      e.g. a refactor that touched no test files. The author then has to argue against
      a "no test coverage" finding when the behavior was already covered upstream. The
      interview pattern asks first.

      Name at least three concrete trigger conditions where the reviewer should
      interview rather than report. Suggested triggers:
        - dependency changes (package.json or pyproject.toml diffs)
        - public API response shape changes or DB column changes
        - refactors with no corresponding test changes
        - changes that touch multiple surfaces (API + components + DB) at once
-->
When reviewing changes, do not immediately commit to a final verdict if the author's intent is ambiguous. Ask clarifying questions **before** reporting findings when encountering any of the following concrete trigger conditions:

1. **Dependency Changes**: `package.json`, `pyproject.toml`, or lockfile diffs where the rationale for new or updated packages is unclear.
2. **Public API or Schema Changes**: Public API response shape alterations, endpoint deprecations, or database column/migration modifications without a visible migration script or backwards-compatibility layer.
3. **Refactors Without Tests**: Significant structural refactors or functional rewrites that touch no test files (`*.test.tsx`, `*.test.ts`) or reduce test coverage. Clarify whether behavior is already covered upstream or if new tests were omitted.
4. **Cross-Surface Changes**: Changes that simultaneously touch multiple architectural tiers (API handlers + UI components + DB repositories) at once, where architectural boundaries might be blurred.

## Phase 2 — Review criteria

<!--
TODO: Write the explicit must-report vs. skip taxonomy. The point of explicit criteria
      (vs vague "be thorough" instructions) is that two teammates running this command
      on the same PR should reach the same verdict.

      Must report: at minimum, name categories for bugs (logic errors, missing await,
      race conditions, off-by-one), security (raw SQL with user input, missing auth,
      secrets in code, dangerouslySetInnerHTML), convention violations the path-scoped
      rules catch, breaking changes, and migration safety.

      Skip: at minimum, name categories the reviewer should NOT block on — minor
      formatting (Prettier handles it), naming bikeshed when the name is fine, personal
      stylistic preferences not encoded in rules/standards, and TODOs that already have
      tracked tickets.

      The skip list is what keeps false positives from destroying author trust.
-->
TTo ensure consistent verdicts across team members, apply this explicit taxonomy:

### Must Report
- **Bugs**: Logic errors, missing `await` statements on asynchronous calls, race conditions, concurrency bugs, and off-by-one errors.
- **Security Vulnerabilities**: Raw SQL queries concatenated with user input, missing authentication/authorization checks, secrets or API keys checked into code, and dangerous injections (e.g., `dangerouslySetInnerHTML`).
- **Convention Violations**: Failures caught by path-scoped rules in `.claude/rules/` (e.g., snapshot testing, unmocked timers, missing async handler definitions, or repository import boundary violations).
- **Breaking Changes & Migration Safety**: Unsafe database migrations (e.g., non-nullable columns added without defaults) and breaking API contract changes without versioning.

### Skip (Do Not Block On)
- **Minor Formatting**: Whitespace, trailing commas, or styling handled automatically by Prettier/Black/Ruff.
- **Naming Bikeshed**: Variable or function names when they are clear, grammatically sound, and follow general domain naming conventions.
- **Personal Preferences**: Subjective stylistic choices not explicitly encoded in project rules or standards.
- **Tracked TODOs**: TODO comments that already reference valid, tracked tickets in the issue tracker.

## Phase 3 — Bundling: interacting vs. independent findings

<!--
TODO: Write the bundling guidance. The contrast is hard to internalize without a
      concrete pair of examples (which you'll write in the Examples section below).

      Interacting findings: those that overlap or affect the same fix. Bundle into
      ONE detailed message with all context. Example: a missing `await` and a missing
      transaction wrapper on the same function — the author needs to see them together
      because the fix changes both lines.

      Independent findings: separate functions, separate files, no shared fix. Report
      SEQUENTIALLY as discrete items so each piece of feedback is actionable.

      Give a one-line heuristic for telling them apart (e.g. "if fixing A changes the
      code B references, they are interacting").
-->
Use this heuristic to determine whether to bundle or separate findings: **"If fixing finding A changes or invalidates the exact lines of code that finding B references, they are interacting and must be bundled."**

- **Interacting Findings**: Overlap or share a single combined fix. Bundle them into **ONE** detailed message listing all context. (e.g., a missing `await` alongside a missing transaction wrapper on the same function).
- **Independent Findings**: Separate functions, separate files, and completely distinct fixes. Report them **SEQUENTIALLY** as discrete items so each piece of feedback remains individually actionable.

## Phase 4 — Output format

For each finding, produce:

```
[severity] path/to/file.ts:line
finding: <one-sentence description>
fix: <one-sentence recommendation>
```

Severity is `bug` | `security` | `convention` | `breaking`. End with a one-line verdict: `approve`, `comment`, or `request-changes`.

## Examples

<!--
TODO: Write at least TWO concrete input/output examples using the format above.

Per Task 3.5, examples are the difference between a command that produces
consistent output across team members and one that produces wildly varying output.

Example 1 — INDEPENDENT findings. Show a diff with two unrelated convention
violations on the same file (e.g. a handler returning a `{ status: 404 }` shape
instead of throwing ApiError, AND a raw SQL call that bypasses the repository
layer). Report each as a separate `[convention]` finding. End with a verdict.

Example 2 — INTERACTING findings. Show a diff where multiple problems share a
single fix (e.g. a refundOrder handler that has missing awaits AND no transaction
wrapper AND wrong ordering between paymentService and DB writes). Bundle them
into ONE `[bug]` finding that lists the three issues together because the fix
changes the same three lines. End with a verdict.
-->
### Example 1 — convention violation (independent)

**Input:**
```diff
-export async function getOrder(id: string) {
-  const order = await db.query("SELECT * FROM orders WHERE id = $1", [id]);
-  if (!order) return { status: 404, body: null };
-  return { status: 200, body: order };
-}
+export async function getOrder(id: string) {
+  const order = await db.query("SELECT * FROM orders WHERE id = $1", [id]);
+  if (!order) return { status: 404, body: { error: "not found" } };
+  return { status: 200, body: order };
+}
```

**Output:**
```
[convention] src/api/orders/get.ts:3
finding: handler returns a `{ status: 404 }` shape instead of throwing `ApiError(404, ...)`.
fix: replace the `if (!order) return ...` with `if (!order) throw new ApiError(404, "NOT_FOUND", \`order ${id} not found\`);`
[convention] src/api/orders/get.ts:2
finding: handler calls `db.query` directly with raw SQL; this bypasses the repository layer and lets user input reach SQL composition.
fix: call `ordersRepo.findById(id)` from `src/db/orders.ts` instead.
verdict: request-changes
```

### Example 2 — interacting findings (bundle)

**Input:**
```diff
+export async function refundOrder(id: string, amount: number) {
+  const order = ordersRepo.findById(id);
+  const updated = ordersRepo.markRefunded(id);
+  paymentService.refund(order.paymentId, amount);
+  return { status: 200, body: updated };
+}
```

**Output:**
```
[bug] src/api/orders/refund.ts:2-4
finding: three interacting issues on the same code path —
  (1) `ordersRepo.findById` is not awaited; `order` is a Promise, so `order.paymentId` is undefined;
  (2) `ordersRepo.markRefunded` is also not awaited;
  (3) the three writes are not wrapped in `withTransaction`, so a paymentService failure leaves the DB marked-refunded while no money moved.
fix: wrap the whole body in `await withTransaction(async (tx) => { ... })`, await each repo call, and order the writes so paymentService.refund runs *before* markRefunded.
verdict: request-changes
```

These are bundled because the fix changes the same three lines and the author needs to see them together to understand the ordering constraint.

## Notes

- This command is project-scoped (`.claude/commands/review.md`) so everyone on the team gets the same review. If you want to layer personal preferences (e.g. a stricter accessibility check on your own PRs), put a `~/.claude/commands/review-strict.md` in your home directory — it will not affect teammates.
- If a finding requires running code or modifying files to verify, ask the author to run a specific check rather than attempting it from the review session. This command's `allowed-tools` are read-only by design.
