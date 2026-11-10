---
description: TODO write a one-line description of these rules
paths:
  # TODO: add glob(s) that activate this rule for co-located test files anywhere in
  # the tree. Tests are co-located: Foo.tsx lives next to Foo.test.tsx — so the glob
  # needs to cross-cut both the components tree and the API tree.
- "**/*.test.ts"
- "**/*.test.tsx"
---

# Test file rules

<!--
TODO: Write at least one concrete, non-trivial convention for editing co-located
      test files (*.test.ts / *.test.tsx). Think about what should layer ON TOP of
      the React or API rules when the file under test sits in those directories.
      Examples: assertion-style enforcement, test-data-builder usage, forbidden
      patterns (snapshots, setTimeout, DB mocking).
-->

When modifying or creating co-located test files (`*.test.ts`, `*.test.tsx`), strictly adhere to the following testing conventions:

## 1. Anti-Patterns & Forbidden Constructs
- **No UI Snapshots**: The use of snapshot testing (`toMatchSnapshot()` or `toMatchInlineSnapshot()`) is strictly prohibited. Snapshots easily hide regression details under massive wall-of-text diffs; assert explicit DOM states or property values instead.
- **No Real Timers or `setTimeout`**: Never use raw `setTimeout` or `setInterval` in tests to wait for asynchronous updates. Always use fake timers (`vi.useFakeTimers()` / `jest.useFakeTimers()`) or await asynchronous testing utilities (e.g., `waitFor`).

## 2. Test Data & Structure
- **Mandatory Test Data Builders**: Complex domain entities and payloads must not be constructed using raw object literals. Use centralized test data builders or factory functions to ensure valid baseline states and reduce boilerplate.
- **Co-Location Alignment**: Test files must reside directly next to the module under test (e.g., `UserService.ts` and `UserService.test.ts`), verifying public interfaces rather than implementation details.
