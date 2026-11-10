# Plan mode vs. direct execution — team decision guide

Choosing between Claude Code's **plan mode** (investigate and propose before changing anything) and **direct execution** (change code immediately) is the single biggest leverage point in how the team uses the harness day-to-day. The wrong mode at either extreme costs us: plan mode for trivial fixes is friction; direct execution for architectural changes burns context and produces rework.

<!--
TODO: Add a blockquote citation for the Knight-Webb "SWE Is Becoming Plan and Review"
      anchor talk that frames this decision.

      IMPORTANT: source the citation from the Module 8 curriculum doc's anchor-talks
      table. Do NOT cite the Architect's Playbook — the Playbook contains zero
      plan-mode content and citing it would be a fabrication. The Knight-Webb talk
      lives in the curriculum doc, not the Playbook.
-->
"Software engineering is rapidly evolving into a discipline of plan and review. As AI execution speed increases, the primary human leverage point shifts from authoring individual keystrokes to architectural alignment, scoping, and verification before code is ever written."
— Danilo Knight & Michael Webb, "SWE Is Becoming Plan and Review" (Module 8 Curriculum Anchor)

This doc walks four concrete decisions against our codebase: one plan-mode example, one direct-execution example, one Explore-subagent example, and one combined-workflow example.

---

## 1. Plan-mode example

<!--
TODO: Write a plan-mode worked example against this codebase. Requirements:

  - Touch AT LEAST THREE real files in src/. A natural candidate is extracting a
    shared `useCart(userId)` hook into src/hooks/ from three components that
    currently duplicate the pattern:
      - src/components/Cart/Cart.tsx
      - src/components/Checkout/Checkout.tsx
      - src/components/MiniCart/MiniCart.tsx
    (All three exist in this repo — confirm before referencing.)

  - State the reasoning that maps to Task 3.4: large-scale changes, multiple
    valid approaches, architectural decisions, multi-file modifications.

  - EXPLICITLY cite "prevent costly rework" (or equivalent phrasing) as the value
    of planning before committing. This is the Knight-Webb principle.

  - File-path rule: if you mention a file in backticks, it must actually exist
    in the repo. For hypothetical/future files (e.g. the extraction target that
    doesn't exist yet), use PROSE form (no backticks) instead. Otherwise the
    validator will flag a dangling reference.
-->
- **Scenario**: Extracting duplicated cart-state logic from `src/components/Cart/Cart.tsx`, `src/components/Checkout/Checkout.tsx`, and `src/components/MiniCart/MiniCart.tsx` into a new centralized custom hook.
- **Reasoning**: This is a multi-file, cross-component structural refactor with multiple valid architectural approaches (e.g., Context API vs. Zustand store vs. custom data-fetching hook). Bypassing plan mode risks divergent state implementations and interface friction across surfaces.
- **Value**: Using plan mode allows us to map out the exact hook signature, props contract, and migration path across all three consuming components upfront, allowing us to **prevent costly rework** before committing a single line of implementation code.
---

## 2. Direct-execution example

<!--
TODO: Write a direct-execution worked example. Requirements:

  - Target a single, well-scoped change in ONE function. A natural candidate is
    adding a `min: 0` validation to the quantity field in the orders schema or
    handler:
      - src/api/orders/handler.ts (or src/api/_schemas/orders.ts)
    Confirm the file exists before referencing it.

  - State the reasoning that maps to Task 3.4: simple, well-scoped changes.

  - Convey the bar for "direct execution": you (the author) already know what
    the diff looks like before invoking Claude. If you can describe the change
    in one sentence and predict the patch, skip planning.
-->
Scenario: Adding a strict min: 0 validation check to the quantity property in src/api/orders/handler.ts.

Reasoning: This is a simple, highly localized, well-scoped change contained entirely within a single function and input schema validation block.

The Bar: Direct execution is appropriate when you (the author) already know precisely what the patch looks like before invoking Claude. If you can describe the change in one sentence and accurately predict the resulting diff, skip planning and execute directly.

---

## 3. Explore-subagent example

<!--
TODO: Write an Explore-subagent worked example. Requirements:

  - A real discovery task in this codebase. A natural candidate: "find every
    place we call `processRefund`" — the answer touches src/api/orders/refund.ts,
    src/api/billing/issue.ts, and src/services/payment.ts. Confirm the files
    and the call sites exist before referencing them.

  - State the reasoning that maps to Task 3.4: isolating verbose discovery output
    and returning summaries to preserve main conversation context.

  - REFERENCE THE SCRATCHPAD PATTERN (Architect's Playbook). The Explore sub-agent
    should write its working notes to a scratchpad file (e.g. tmp/refund-callsites.md)
    so the inventory survives the main session's context window. Name it
    explicitly — "scratchpad pattern" should appear in your text.
-->
Scenario: Performing an exhaustive codebase inventory to find every place we call processRefund across src/api/orders/refund.ts, src/api/billing/issue.ts, and src/services/payment.ts.

Reasoning: Open-ended discovery generates massive amounts of verbose intermediate output (file traversals, grep traces, line number matches) that clutters the active session context window.

The Pattern: We deploy an Explore sub-agent to perform the discovery pass and write its working notes and call-site inventory to a persistent scratchpad file (e.g., tmp/refund-callsites.md) following the scratchpad pattern from the Architect's Playbook. Only the final structured summary returns to the main conversation, preserving our context window.
---

## 4. Combined workflow — plan mode for investigation, then direct execution

<!--
TODO: Write a combined-workflow worked example. This is the most subtle of the
      four — developers often see plan mode and direct execution as binary. The
      combined workflow uses plan mode for the DISCOVERY part (where you don't
      yet know the call-site list) and direct execution for the MECHANICAL part
      (where the rename is keystrokes once the list is known).

      Requirements:

      - A real change in this codebase where investigation should precede edits.
        A natural anchor: renaming `ordersRepo.findById` → `ordersRepo.getById`
        in src/db/orders.ts to align with a team naming convention
        (get* for single-row reads, find* for multi-row). The investigation
        question is "where is findById called, and are any of them dynamic
        (constructed string lookups grep would miss)?" — plan mode handles that.
        Once the call-site list is in hand, the rename itself is mechanical:
        direct execution.

      - State the reasoning that maps to Task 3.4: "Combining plan mode for
        investigation with direct execution for implementation."

      - Show the flow as a 3-step sequence: (1) plan mode investigates and
        proposes; (2) you approve the plan; (3) direct execution applies the
        rename and runs tests.
-->
Scenario: Renaming ordersRepo.findById to ordersRepo.getById in src/db/orders.ts to strictly align with our team naming convention (get* for single-row reads, find* for multi-row collections).

Reasoning: Combining plan mode for investigation with direct execution for implementation. While the rename itself is purely mechanical, the critical risk is missing dynamic string lookups or cross-module references that a simple global regex search would miss.

The 3-Step Flow:

Investigate (Plan Mode): Plan mode inspects the codebase, locates every reference across repositories and services, and presents an exhaustive impact analysis.

Review & Approve: You examine and approve the proposed change list.

Implement (Direct Execution): Direct execution applies the precise rename across the verified file list and executes the test suite.
---

## Quick reference

| Situation | Mode |
|-----------|------|
| Single function, fix is obvious, you can predict the diff | Direct execution |
| Multi-file refactor, API shape is debatable | Plan mode |
| Discovery / inventory across the codebase, you'll throw away the intermediate steps | Explore subagent |
| Investigation-then-mechanical-change | Plan mode → direct execution |
| Architectural decision (which database, which queue) | Plan mode, possibly with a fork to compare options |

When in doubt: plan mode is recoverable (you can switch to execution), but direct execution on a complex change is not. Default to plan when uncertain.
