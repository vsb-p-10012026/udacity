---
description: TODO write a one-line description of these rules
paths:
  # TODO: add glob(s) that activate this rule when Claude edits files under src/api/
 - "src/api/**/*"
---

# API handler rules

<!--
TODO: Write at least one concrete, non-trivial convention for editing files under
      src/api/. Pull from `.claude/standards/api.md` (already complete) for context,
      but write something more specific than the standard — a rule that ONLY fires
      when editing API handler files. For example: handler signature shape, error-type
      enforcement, or repository-import boundaries.
-->
When modifying or creating files under `src/api/`, strictly adhere to the following architectural and code quality conventions:

## 1. Handler Signature & Typing
- **Explicit Request/Response Schemas**: Every API endpoint handler must accept a strongly-typed request model (e.g., Pydantic schemas) and return a fully typed response model. Raw dictionary returns or untyped `Any` payloads are strictly forbidden.
- **Async Definition**: All HTTP route handlers must be defined as `async def` to ensure non-blocking I/O execution.

## 2. Error-Type Enforcement & Boundaries
- **Domain Exception Translation**: Handlers must never catch and expose raw database exceptions or internal system errors directly to clients. All errors must map to explicit, typed HTTP exceptions or domain error classes handled by global exception middleware.
- **Strict Repository Import Boundaries**: API handlers are strictly prohibited from importing raw database drivers or executing direct SQL queries. All data access must be delegated through service layers or repository abstractions.

## 3. Dependency Injection
- **Framework Dependencies**: Use native dependency injection constructs (e.g., `Depends()`) for authentication, database sessions, and service clients rather than global singletons or direct instantiation inside route functions.
