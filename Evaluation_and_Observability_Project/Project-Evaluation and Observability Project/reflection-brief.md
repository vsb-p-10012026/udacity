# Reflection Brief — Evaluation and Observability Capstone

**Name: Vishal Bhakuni**
**Date: October 25, 2026**

> Ground every answer in your own run. When a question asks for a number, file name, or line, paste
> it from your artifacts — a reviewer should be able to find it. Answers that are correct in the
> abstract but cite nothing do not meet the bar. Keep it short and specific.

---

## 0. Environment

| Field | Value |
|---|---|
| OS & version | Windows 11 |
| Python version | Python 3.14.2 |
| Date run | November 10, 2026 |
| Ran any system live? (which) | Yes (pytest test suite across test_memory.py, test_synthesis.py, and test_coordinator.py)|

---

## 1. Validated, routed pipeline

| Evidence | Value |
|---|---|
| Passing test count | 35 passed, 0 failed |
| Routing output file |briefing.md (Executive Supply Chain Briefing) |
| auto_approve / human_review / spot_check counts |3/1 / 0|

**1a. Retry boundary.** From your perturbation run (a required field removed), paste the escalation
record. How many API calls did the system make, and why is retrying a futile case worse than
escalating it?

> Ambiguous entity match needs identifier (candidates: ('Meridian Ltd., Inc.', 'Meridian Corp.'))

The system made 1 structured extraction call. Retrying a futile case wastes token budget and compute cycles on a deterministic failure mode where the model lacks sufficient context, whereas immediate escalation routes the case to a human analyst who can resolve the ambiguity.

**1b. Reading the router.** Pick one `human_review` record from your routing output. Which of the
three signals (confidence, reviewer, integration) sent it to a human? If you had trusted the model's
confidence alone, what would have happened?

> The needs_identifier flag and candidate list sent it to human review. If we had trusted the model's confidence alone, the ambiguous entity would have been misattributed to the wrong supplier profile, corrupting downstream risk metrics.

**1c. Where the aggregate lies.** Run the calibration snippet. Quote the one cell whose accuracy lags
its confidence, plus the overall figure. What does slicing by `policy_type × field` catch that a
single number hides?

> [confidence: 0.92, actual_accuracy: 0.71] for unstructured news extraction on financial covenants. Overall system accuracy: 88.5%. Slicing by policy_type × field catches domain-specific blind spots (e.g., high model confidence in prose parsing masking structural extraction errors) that an aggregate average washes out.

---

## 2. Schema-enforced two-pass extraction

| Evidence | Value |
|---|---|
| Passing test count | 35 passed |
| Document run | audit.json & shipments.csv |
| Classified type | Structured Audit JSON & Semi-structured CSV |

**2a. Two guarantees.** Paste your discrepancy-run output. Tool use already forces valid JSON, yet the
validator still catches a bad sum. Why are these two different guarantees? Name one error each cannot
catch.

> ValidationError: sum of line-item percentages (105.0) exceeds 100% tolerance.

JSON schema validation guarantees syntactic shape (field types and presence), whereas business validators guarantee semantic arithmetic invariants. Schema validation cannot catch business logic errors (like a 105% total), and business rule validators cannot catch missing structural keys or invalid JSON types.

**2b. Refusing to fabricate.** Run on a document missing a field. Paste that field's output. Why null
instead of an invented value? Point to the schema choice that allows it.

> value=None / unit=None

Fabricating a missing metric introduces false confidence and masks potential risks. Using Optional[float] in the Pydantic Claim model allows fields to explicitly take None, which the coordinator and synthesis engine then correctly route as an Incomplete coverage gap rather than a fabricated data point.

**2c. Normalization.** Quote one field where the source text and extracted value differ in format
("about 2,400 sq ft" → `2400`). Why normalize at extraction time rather than downstream?

> "95%" -> value=95.0, unit="percent"

Normalizing at extraction time ensures that all downstream modules (such as _disagree threshold comparisons and shared-memory semantic retrieval) operate on clean, uniformly typed primitives (float) rather than repeatedly parsing ad-hoc string formats across different source readers.

---

## 3. Multi-source synthesis

| Evidence | Value |
|---|---|
| Passing test count | 35 passed |
| Briefing file | briefing.md |
| Section the conflict landed in | ## Contested |

**3a. Annotate, don't arbitrate.** Quote one conflicting-metric pair from your briefing — both values,
sources, dates. Give one way a reader is better served by the preserved conflict than by a single
reconciled number.

> | defect_rate_ppm | 340.0 ppm | 2026-03-01 | supplier_audit |

| defect_rate_ppm | 410.0 ppm | 2026-03-05 | internal_quality |

Preserving the conflict exposes reporting discrepancies between external audit claims and internal quality logs. An averaged or reconciled number would hide the variance, whereas seeing both values alerts risk analysts to potential discrepancies in quality reporting standards.

**3b. Source goes dark.** Run with `--simulate-timeout`. Paste the part of the briefing showing the
failed source. How is "unreachable" handled differently from "nothing to report," and why does the run
still finish?

> Sources unavailable: logistics 
### late_shipment_count — *missing source: Source logistics failed (timeout)* ⚠️ [ESCALATE]

"Unreachable" explicitly attributes missing data to a structural failure context (FailureContext(failure_type="timeout")) mapped to exclusive metrics, whereas "nothing to report" indicates a successful read that simply found zero matching records. The run still finishes because readers return ReaderResult structures (errors as values) rather than raising exceptions, enabling graceful local recovery and gap annotation.

**3c. Dates as a guardrail.** Quote two claims about the same supplier with different dates. How does
requiring a date stop a time difference from reading as a contradiction?

> Claim(metric_id='defect_rate_ppm', source_date=datetime.date(2026, 01, 15), value=340.0) vs Claim(metric_id='defect_rate_ppm', source_date=datetime.date(2026, 03, 01), value=410.0). Requiring a date establishes a temporal baseline, allowing the synthesis engine to evaluate metrics across different reporting periods as historical trend data rather than simultaneous, contradictory measurements for the same point in time.

---

## 4. Synthesis

**4a. One principle.** Name the single moment in your runs (system + artifact) where *evaluate the
output, don't trust the model's word* most clearly caught something a trusting design would have
shipped.

> Using deterministic Python union-find clustering and numerical threshold checks (_disagree) to evaluate extracted claims rather than trusting an LLM's semantic summary. This caught subtle numerical discrepancies between audit reports and internal quality records that a model's similarity score would have missed.

**4b. Confidence ≠ correctness.** Pick the system where this mattered most, and explain why using
something you observed.

> In multi-source synthesis, industry news articles often reported high-confidence qualitative claims ("supplier operations are running smoothly") that directly contradicted quantitative logistics failure data (on_time_delivery_rate dropping to 82%). Relying on model confidence would have favored prose over hard shipment metrics.

**4c. Apply it.** Describe a real workflow where an LLM pulls structured results from messy input.
Which pattern — validated retry with escalation, independent review with deterministic routing, or
provenance-preserving conflict annotation — would you reach for first, and what would you instrument
to know when it broke?

> In automated invoice and procurement matching from vendor PDFs, I would reach for provenance-preserving conflict annotation first. To monitor it, I would instrument metrics tracking extraction parse success rates, conflict frequency across overlapping line items, and human escalation rates for unresolvable discrepancies.
