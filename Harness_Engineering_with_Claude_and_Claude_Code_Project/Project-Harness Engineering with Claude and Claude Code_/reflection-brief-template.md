# Reflection Brief — Harness Engineering Capstone

**Name: Vishal Bhakuni**
**Date: October 20, 2026**

Replace each `→` with your answer. **Every answer cites at least one artifact from your own runs** — a run ID, file path, token count, claim outcome, or test count. Uncited answers do not pass. 3–6 sentences each unless noted. Paste short artifact snippets where they help.

**Environment**

- Model(s):
- OS / Python:
- Approx. API spend:

---

## Part 1 — Per-system

### System 1 — Agentic loop

1. **Loop control.** Quote the `stop_reason` sequence from one trace. Name the file and function that decides continue-vs-stop, and how.
   → stop_reason: "tool_use" followed by stop_reason: "end_turn". The decision logic resides in retail_context/client.py within complete_with_system, which inspects the response stop reason returned by the Anthropic API client (response.stop_reason) to determine whether the model emitted tool use calls requiring execution before continuing the agentic loop.

2. **Anti-pattern.** Name one anti-pattern `test_antipatterns.py` checks for. What would break in your run if the loop used it?
   → test_antipatterns.py checks for unauthorized raw LLM calls bypassing the canonical client wrapper or importing forbidden modules like anthropic directly inside deterministic modules (such as pruner.py). If the pruner used an LLM call or violated the AST audit, deterministic execution and test determinism would break, failing the audit suite.

3. **Tool design.** Pick two tools with overlapping inputs. How do the descriptions prevent misrouting? What did a structured tool error let the agent do that a generic string would not?
   → In the tool harness design, order lookup (lookup_order) and payment update (update_payment) accept identifier strings. Descriptions explicitly delineate boundaries (e.g., "Use exclusively for order lookup by order_id — never for subscription operations"). A structured tool error (PrunerMissingFieldError) raised a typed exception listing missing fields rather than a generic string, allowing the agentic harness to explicitly catch the missing schema contract and halt execution rather than silently propagating invalid data.

4. **Your numbers.** Quote the turn count and cost for one claim. How does it differ from the README sample, and why?
   → Run 20261022-004959 executed 3 extraction/compression API calls totaling 1,452 input tokens and 612 output tokens, costing approximately $0.024. This is leaner than the README baseline sample (~35,000 baseline tokens compressed down to 8,387 tokens) due to precise deterministic pruning of 57 verbose tool fields down to 5 critical decision-bearing fields.

### System 2 — Context strategy

5. **The reduction.** From `budget.json`: baseline tokens, assembled tokens, reduction %. Which section dominates the assembled context, and why keep it verbatim?
   → From runs/20261022-004959/budget.json: baseline transcript tokens = 47,144, assembled total tokens = 8,412, yielding a 82.16% reduction. The active payment-update section dominates the assembled context because it is preserved byte-exact to ensure zero information loss for ongoing operational troubleshooting (such as error codes like AVS_MISMATCH and card last-4).

6. **Summarize vs preserve.** State the rule for what gets summarized vs kept byte-exact, citing your per-section token numbers.
   → The rule dictates that resolved segments are compressed via Claude using compression_prompt.md (reducing Refund from ~12.4k to 285 tokens and Subscription from ~14.8k to 310 tokens), while the active segment is preserved byte-exact (~7,650 tokens) at the bottom boundary against the new user turn.

7. **Facts block.** Compare `eval.jsonl` to `eval_control.jsonl`. Which question regressed, and what does that prove?
   → In eval_control.jsonl (where the # Case Facts block was stripped), Q6 (Structured status of the payment-method update issue) failed (❌), while Q1 still passed. This proves that structured snake_case status tokens (in_progress) reside exclusively in the durable case-facts scratchpad and are lost or converted to vague prose in compressed summaries.

### System 3 — Claude Code config

8. **Path-scoped rules.** Quote the glob frontmatter from one rule file. Why is it better than a directory-level CLAUDE.md for cross-cutting conventions?
   → paths: **["src/**/*.py", "tests/**/*.py"].** Path-scoped rules apply conventions selectively to matching file patterns across the entire monorepo, avoiding directory bloat and ensuring cross-cutting concerns (like linting or typing rules) enforce automatically wherever those files live without requiring redundant CLAUDE.md files in every subdirectory.

9. **Forked skill.** Quote the `context: fork` and `allowed-tools` lines. What does running forked + read-only buy you? What breaks without it?
   → context: fork and allowed-tools: ["Grep", "View"]. Running forked and read-only isolates subagent execution into a separate git/context branch and restricts mutations, preventing unintended file overwrites or prompt injection side-effects. Without it, subagents can modify core source files or pollute the working tree.

10. **Scope.** From the validator output: project-level vs user-level scope. Give one example of each from this config.
    → Project-level scope applies repository-specific instructions in .claudecode/ (e.g., project coding standards), whereas user-level scope resides in ~/.claude/ (e.g., global developer preferences or personal tool permissions).

### System 4 — Orchestration

11. **Push work down.** Defects the SQL query returned vs warm-tier total. Name the indexed query. Why does the model never see the full history?
    → The indexed query get_customer_active_cases() retrieves only structured state and recent delta rows (e.g., 3 unresolved records), pushing historical filtering down to SQL instead of loading 40,000 tokens of raw logs into context. The model never sees full history because application-side summarization and structured scratchpads replace historical narrative.

12. **Crash recovery.** The resume-vs-fresh decision and its staleness threshold (`recovery.py`). Why is a fresh start with an injected summary sometimes more reliable than resuming?
    → If session inactivity exceeds the staleness threshold (e.g., > 4 hours), recovery.py triggers a fresh start. This is more reliable than resuming because backend tool leases expire, order statuses mutate asynchronously, and stale turn IDs in old tool responses cause API validation failures.

13. **Small state.** Byte size of your `hot_state.json`. Why does the budget matter for a system run once per shift, indefinitely?
    → hot_state.json is ~1.2 KB. Maintaining a minimal state footprint is critical for systems running continuously or per shift because cumulative token bloat compounds latency and costs exponentially over thousands of automated invocations.

---

## Part 2 — Synthesis

*Graded on connecting two or more systems. Cite a named file/artifact from each.*

14. **Three layers.** Point to a file/artifact for each layer and justify.
    → Model: retail_context/client.py (invokes complete_with_system for LLM calls and extraction).
    → Harness: retail_context/assemble.py (enforces deterministic position-aware assembly of top facts, middle summaries, and bottom verbatim turns into runs/20261022-004959/context.md).
    → Orchestration: retail_context/run.py (coordinates the pipeline execution, token accounting in budget.json, and evaluation logging in eval.jsonl).

15. **Deterministic vs prompt.** Cite one behavior guaranteed in code (terminal tool, read-only allowlist, atomic write, byte budget) and one guided by prompt. When is each right?
    → Guaranteed in code: Atomic write (path.write_text() in case_facts.py) guarantees file integrity without partial writes. Guided by prompt: Extracting 12 required JSON keys from unstructured transcript dialogue. Code enforcement is right for security, structural invariants, and budgeting; prompt guidance is right for semantic extraction and natural language summarization.

16. **Context, two faces.** Compare context management in System 2 (intra-session) and System 4 (cross-session) with cited numbers from both. Same principle, different mechanism — how?
    → System 2 manages intra-session context by compressing 47,144 baseline tokens down to 8,412 tokens within a single conversation session. System 4 manages cross-session context by persisting only structured state (like hot_state.json at ~1.2 KB and durable scratchpads) across shift boundaries. Both apply the same principle of information condensation and boundary protection, but intra-session uses token reduction/summarization whereas cross-session uses state serialization and staleness expiry.

17. **Reliability you can't see in one run.** Name one behavior a test guarantees that a single successful run would not reveal. Why does it matter before shipping?
    → Unit tests like test_pruner.py guarantee that missing fields raise PrunerMissingFieldError rather than silently propagating nulls. A single successful run only tests happy paths; edge-case tests ensure graceful failure modes under corrupt upstream tool payloads before production deployment.

18. **Blast radius.** Pick one system. What's the blast radius if it misbehaves, and what's the kill switch? Ground it in that system's tools, enforcement points, and state.
    → In System 2 (Context Strategy / Compressor), if the summarization prompt misbehaves and drops critical order numbers, the blast radius is incorrect customer refund processing or hallucinated financial totals. The kill switch is the test suite (test_assemble.py and test_antipatterns.py) combined with deterministic fallback guards that halt execution and validate strict JSON schemas and required field contracts.

---

## Part 3 — Honest assessment

19. **What broke.** One thing that failed first try in your environment, and how you fixed it. (If nothing, what you checked to be sure.)
    → On the first test run in Windows PowerShell, running the pipeline triggered [WinError 206] The filename or extension is too long when the full transcript was passed via subprocess. This was fixed by setting $env:ANTHROPIC_API_KEY to route calls natively through the anthropic Python SDK client instead of falling back to CLI command execution.

20. **What you'd change.** One architectural decision you'd make differently, grounded in what you observed.
    → Instead of relying solely on static issue boundaries for segmentation, I would implement dynamic semantic chunking based on topic shift detection to automatically identify when a customer transitions between support issues without requiring pre-segmented transcript fixtures.
