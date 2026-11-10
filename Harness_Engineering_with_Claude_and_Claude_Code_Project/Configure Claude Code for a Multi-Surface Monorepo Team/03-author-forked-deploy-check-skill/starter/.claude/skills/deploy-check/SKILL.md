---
# TODO: Write the YAML frontmatter for this skill. It must include:
#
#   name: deploy-check
#   description: (one line naming what the skill does)
#   context: fork                    ← runs in a forked sub-agent (the key piece)
#   argument-hint: "..."             ← QUOTE any value containing a colon. Unquoted
#                                      `argument-hint: <foo: bar>` parses as a NESTED
#                                      MAPPING and breaks frontmatter loading.
#   allowed-tools: a READ-ONLY allowlist (Read, Grep, Glob, granular Bash sub-commands
#                  like Bash(git status:*) and Bash(gh pr view:*) — no Edit, Write,
#                  NotebookEdit, or unrestricted Bash).
#
# A note on schema drift: the current Claude Code IDE LSP (2026-05) may not list
# `context` or `allowed-tools` in its skill-frontmatter completions. That's the LSP
# lagging the product spec, not a problem with your file — see Troubleshooting in
# the exercise instructions.
name: deploy-check
description: Run read-only pre-deployment validation checks against the current working tree and branch.
context: fork
argument-hint: "<target-branch>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(gh pr view:*)
  - Bash(gh pr checks:*)
---

# /deploy-check

Runs the team's pre-deployment validation checklist against the current working tree and the branch you're about to ship. Read-only by design — this skill never modifies files, never pushes, never deploys. It returns a single structured summary so the calling session can decide whether to proceed.

## Why this is a skill (not a CLAUDE.md addition)

<!--
TODO: Write a 2-3 line decision rubric explaining why /deploy-check is a SKILL
      rather than always-loaded CLAUDE.md guidance.

      The contrast you must convey:
        - Skill: on-demand, forked, task-specific. You only need it right before a
          deploy. It produces verbose intermediate output (file enumeration, diff
          parsing, check execution traces) that has no value once the summary is
          known.
        - CLAUDE.md: always-loaded, universal. Conventions that need to be present
          in every session (e.g. "tests are co-located", "throw ApiError for
          validation failures") belong here.

      Without this contrast, teammates default to dumping everything into CLAUDE.md
      and end up with a 600-line monolith that wastes context on every session.

      Rule-of-thumb summary at the end: on-demand / forked / task-specific → skill;
      always-loaded / universal → CLAUDE.md.
-->
Deciding where guidance belongs is essential to keeping context windows efficient:
- **Skill**: On-demand, forked, and task-specific. You only need this right before a deploy. It generates verbose intermediate outputs (file enumerations, diff parsing, check execution traces) that hold zero value once the final decision summary is known.
- **CLAUDE.md**: Always-loaded and universal. Core conventions that must be present in every single session (e.g., "tests are co-located", "throw `ApiError` for validation failures") belong here.

*Rule of thumb:* On-demand / forked / task-specific → **Skill**; Always-loaded / universal → **CLAUDE.md**.

## Why `context: fork`

<!--
TODO: Write the rationale paragraph for `context: fork`. It MUST do two things:

  (a) Explicitly state that the goal is to keep verbose intermediate output OUT OF
      THE MAIN SESSION / conversation. A deploy check walks the working tree,
      inspects diffs, and runs several enumeration passes — none of that has any
      value to the calling session once we know whether to ship. Only the
      structured summary should return to the main conversation.

  (b) Note that `context: fork` is a Claude Code PRODUCT FEATURE operating at the
      skill-invocation layer, conceptually analogous to the Architect's Playbook
      *Branching Reality* pattern (which describes session-level forking via
      `fork_session`). Mention both so a reader who knows the Playbook can map the
      mental model.
-->
(a) The primary goal is to keep verbose intermediate execution output **out of the main conversation session**. A comprehensive deploy check walks the working tree, inspects diffs, runs multiple enumeration passes, and queries GitHub status checks — none of which benefits the calling session once the pass/fail determination is complete. Only the concise structured summary returns to the parent conversation.

(b) `context: fork` operates as a Claude Code product feature at the skill-invocation layer, conceptually analogous to the Architect's Playbook *Branching Reality* pattern (which describes session-level forking via `fork_session`). Both isolate execution states and preserve parent context clarity.

## Checks

Run all three. Each check produces a pass-or-fail verdict; if any fails, the overall summary is **fail**.

<!--
TODO: Write at least THREE pre-deployment checks. For each check, declare:

  - Detect: the exact command(s) or signal(s) that determine whether the
            condition holds.
  - Pass:   what a passing result looks like.
  - Fail:   what a failing result looks like, including what to surface in the
            verdict-summary so the author can act on it.

Suggested checks (you may substitute equivalents if your team's deploy
shape needs different ones):

  1. Uncommitted changes — `git status --porcelain` returns empty.
  2. Migrations up-to-date with code — every new repository import in the diff
     since the target branch is backed by a migration file in the same branch.
  3. CI checks green on the open PR — `gh pr view --json statusCheckRollup`
     reports all required checks as SUCCESS.
-->
### 1. Uncommitted changes

- **Detect:** run `git status --porcelain`. Empty output means the working tree is clean.
- **Pass:** working tree has no staged, unstaged, or untracked files.
- **Fail:** any file shows up in `git status --porcelain`. List the first 10 paths in the summary so the author knows what to commit or stash.

### 2. Migrations up-to-date with code

- **Detect:** glob `src/db/migrations/*.sql` for the highest sequence number, then `grep -R "from \"src/db/.*\"" src/api/` for repository imports added in the diff since the target branch. If any new repository module is imported but no migration file's sequence ≥ the previous highest, that's a fail. Also check `git diff <target>..HEAD --name-only` for any `src/db/types.ts` change without a corresponding `src/db/migrations/` change.
- **Pass:** every new repository function or type change is backed by a migration file in this branch.
- **Fail:** code references a column or table that doesn't exist in any committed migration. Report the orphaned reference and the missing migration name.

### 3. CI checks green on the open PR

- **Detect:** if a PR exists for this branch (`gh pr view --json number,state,statusCheckRollup`), inspect the latest `statusCheckRollup`. Otherwise note "no PR open" and skip.
- **Pass:** all required checks have status `SUCCESS`.
- **Fail:** any required check is `FAILURE`, `CANCELLED`, or still `PENDING` when the PR is marked ready-for-review. Report the failing check names and link to the run.


## Output format

Return exactly this shape to the main session:

```
verdict: pass | fail
checks:
  - name: <check-name>
    status: pass | fail
    detail: <one line or empty>
```

Do not include the raw `git status`, raw diff hunks, or full check logs in the returned summary — those stay in the fork. If the author wants to investigate a failed check, they can re-invoke the skill targeting that single check or run the underlying command themselves.

## Personalization

<!--
TODO: Add a short note explaining that this skill is project-scoped
      (`.claude/skills/deploy-check/`) so the whole team gets the same checks.
      Mention that a teammate who wants a stricter personal variant — say, one
      that additionally fails when the diff exceeds 500 lines without a long
      enough PR description — can create a parallel skill at
      `~/.claude/skills/deploy-check-strict/` with a different name. Their
      variant will not be committed to the repo and will not affect teammates.
-->
This skill is project-scoped (`.claude/skills/deploy-check/`) so the entire team shares the exact same pre-deployment validation criteria. If a teammate wants a stricter personal variant — for instance, one that additionally fails when the diff exceeds 500 lines without an adequately detailed PR description — they can create a parallel custom skill at `~/.claude/skills/deploy-check-strict/` under a distinct name. Their local variant will remain uncommitted to the repo and will not impact teammates.

## What this skill deliberately does not do

- It never pushes, deploys, or runs migrations. The `allowed-tools` allowlist is read-only by construction; even if a future maintainer adds `Write` here, the team's `/review` command should catch the change.
- It does not run the test suite. Tests have their own pre-merge gate in CI; duplicating that here would slow every deploy check without adding signal.
- It does not check for secrets in code. That's the job of the `gitleaks` pre-commit hook, which fails the commit, not the deploy.
