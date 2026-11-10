"""Synthesis — turn provenance-carrying claims into an executive briefing.

The synthesis is deterministic Python (not an LLM call), so provenance
preservation and conflict annotation are *guaranteed*, not merely prompted:

- claims are grouped by the metric they describe (with shared-memory retrieval
  catching near-duplicate metric ids);
- each group is classified Well-Established / Contested / Incomplete;
- conflicts are **annotated, not arbitrated** — every conflicting value is kept
  with its source and date, and no single/averaged value is emitted;
- each finding carries a coverage annotation and an escalation flag driven by
  explicit criteria (never by model confidence or sentiment).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .memory import SharedMemory, _claim_id
from .models import Claim

WELL_ESTABLISHED = "Well-Established"
CONTESTED = "Contested"
INCOMPLETE = "Incomplete"
SECTIONS = (WELL_ESTABLISHED, CONTESTED, INCOMPLETE)

REL_TOL = 0.10  # values within 10% are treated as agreeing

# Metrics the investigation always tries to assess; a tracked metric with no
# usable source is reported as Incomplete (a coverage gap, not a fabricated one).
TRACKED_METRICS = (
    "on_time_delivery_rate",
    "defect_rate_ppm",
    "average_lead_time_days",
    "production_capacity_utilization",
)
HIGH_IMPACT = frozenset(
    {"on_time_delivery_rate", "defect_rate_ppm", "production_capacity_utilization"}
)
LOGISTICS = "logistics"
NEWS = "industry_news"


def _tokens(metric_id: str) -> set[str]:
    return set(metric_id.split("_"))


@dataclass
class MetricGroup:
    metric_id: str
    claims: list[Claim]


def group_by_metric(claims: list[Claim], memory: SharedMemory | None = None) -> list[MetricGroup]:
    """Cluster claims describing the same metric.

    Claims with an identical metric_id always group together. When `memory` is
    given, near-duplicate metric ids (different strings, same concept) are merged
    too: two claims unify if shared-memory retrieval ranks them as neighbours and
    their metric ids share at least two tokens (e.g. defect_rate / defect_rate_ppm).
    """
    # TODO: Cluster claims that share a metric_id. A union-find over claim indices
    #   works well: first union all claims with the same metric_id, then — when
    #   `memory` is provided — for each claim pull memory.related_to(claim) and
    #   union it with any neighbour whose metric_id shares >= 2 tokens (see
    #   _tokens) with it. Emit one MetricGroup per cluster, choosing the most
    #   common metric_id in the cluster as the canonical id. Sort groups by id.
    if not claims:
        return []

    if memory is not None:
        memory.add_claims(claims)

    parent = list(range(len(claims)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if claims[i].metric_id == claims[j].metric_id:
                union(i, j)

    if memory is not None:
        for i, claim in enumerate(claims):
            try:
                neighbors = memory.related_to(claim, k=10)
                for neighbor in neighbors:
                    for j, c2 in enumerate(claims):
                        if _claim_id(c2) == _claim_id(neighbor):
                            tokens_i = _tokens(claim.metric_id)
                            tokens_j = _tokens(c2.metric_id)
                            if len(tokens_i & tokens_j) >= 2:
                                union(i, j)
            except Exception:
                pass

    clusters: dict[int, list[Claim]] = {}
    for i, claim in enumerate(claims):
        root = find(i)
        clusters.setdefault(root, []).append(claim)

    groups: list[MetricGroup] = []
    for cluster_claims in clusters.values():
        counts = {}
        for c in cluster_claims:
            counts[c.metric_id] = counts.get(c.metric_id, 0) + 1
        canonical_id = max(counts, key=counts.get)
        groups.append(MetricGroup(metric_id=canonical_id, claims=cluster_claims))

    groups.sort(key=lambda g: g.metric_id)
    return groups

@dataclass
class Finding:
    metric_id: str
    classification: str
    claims: list[Claim]
    coverage: str
    escalate: bool
    escalation_reason: str = ""

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for c in self.claims:
            if c.source not in seen:
                seen.append(c.source)
        return seen


def _source_values(claims: list[Claim]) -> dict[str, float]:
    values: dict[str, float] = {}
    for c in claims:
        if c.value is not None and c.source not in values:
            values[c.source] = c.value
    return values


def _disagree(values: list[float]) -> bool:
    # TODO: Return True when the values disagree beyond REL_TOL. Use a relative
    #   difference: (max - min) / max(abs(min), abs(max), tiny) > REL_TOL.
    if len(values) < 2:
        return False
    min_v, max_v = min(values), max(values)
    tiny = 1e-9
    diff = (max_v - min_v) / max(abs(min_v), abs(max_v), tiny)
    return diff > REL_TOL

def _classify(group: MetricGroup) -> tuple[str, str]:
    """Return (classification, coverage_badge) for a present metric group."""
    # TODO: 2+ sources whose values disagree -> (CONTESTED, "N sources, conflicting").
    #   2+ sources that agree -> (WELL_ESTABLISHED, "corroborated across N sources").
    #   A single source -> (WELL_ESTABLISHED, "single source only").
    values_by_source = _source_values(group.claims)
    unique_sources = len(set(c.source for c in group.claims))
    vals = list(values_by_source.values())

    if unique_sources >= 2 and _disagree(vals):
        return CONTESTED, f"{unique_sources} sources, conflicting"
    elif unique_sources >= 2:
        return WELL_ESTABLISHED, f"corroborated across {unique_sources} sources"
    else:
        return WELL_ESTABLISHED, "single source only"

def _escalation(metric_id: str, classification: str, claims: list[Claim]) -> tuple[bool, str]:
    """Explicit escalation criteria — never confidence/sentiment.

    Few-shot intent:
      on_time_delivery_rate Contested (high-impact) -> escalate
      defect_rate_ppm Well-Established               -> do not escalate
      production_capacity_utilization Incomplete     -> escalate (high-impact gap)
      supplier_financial_distress needs_identifier   -> escalate for clarification
    """
    # TODO: Escalate when any claim has needs_identifier, OR the metric is
    #   high-impact (HIGH_IMPACT) and Contested, OR high-impact and Incomplete.
    #   Otherwise do not escalate. Never read the confidence field.
    for c in claims:
        if c.needs_identifier:
            return True, f"Ambiguous entity match needs identifier (candidates: {c.candidates})"

    is_high_impact = metric_id in HIGH_IMPACT
    if is_high_impact and classification == CONTESTED:
        return True, f"High-impact metric '{metric_id}' is Contested."
    if is_high_impact and classification == INCOMPLETE:
        return True, f"High-impact metric '{metric_id}' is Incomplete (coverage gap)."

    return False, ""

@dataclass
class Briefing:
    supplier: str
    findings: list[Finding] = field(default_factory=list)
    unavailable_sources: list[str] = field(default_factory=list)

    def section(self, name: str) -> list[Finding]:
        return [f for f in self.findings if f.classification == name]

    @property
    def escalations(self) -> list[Finding]:
        return [f for f in self.findings if f.escalate]

    def render(self) -> str:
        lines = [f"# Supply Chain Risk Briefing — {self.supplier}", ""]
        if self.unavailable_sources:
            lines.append(f"> Sources unavailable: {', '.join(self.unavailable_sources)}")
            lines.append("")
        for name in SECTIONS:
            lines.append(f"## {name}")
            findings = self.section(name)
            if not findings:
                lines.append("_none_")
                lines.append("")
                continue
            for f in findings:
                lines.extend(_render_finding(f))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def _render_finding(f: Finding) -> list[str]:
    # TODO: Render one finding as Markdown lines. Lead with a heading carrying the
    #   metric_id, its coverage badge, and an escalation flag when f.escalate.
    #   Render content appropriately: numeric metric comparisons as a structured
    #   list ("Reported values by source:"), logistics data as a Markdown table,
    #   and news findings as prose ("> ..."). For an INCOMPLETE finding, just show
    #   the coverage line. Keep EVERY conflicting value with its source and date —
    #   never average or drop one.
    lines = []
    esc = " ⚠️ [ESCALATE]" if f.escalate else ""
    lines.append(f"### `{f.metric_id}` — *{f.coverage}*{esc}")
    if f.escalation_reason:
        lines.append(f"> **Escalation Reason:** {f.escalation_reason}")

    if f.classification == INCOMPLETE:
        lines.append(f"> Metric unavailable or incomplete.")
        lines.append("")
        return lines

    has_logistics = any(c.source == LOGISTICS for c in f.claims)
    if has_logistics and any(c.value is not None for c in f.claims):
        lines.append("")
        lines.append("| Metric | Value | As of | Source |")
        lines.append("|---|---|---|---|")
        for c in f.claims:
            val_str = f"{c.value} {c.unit or ''}".strip()
            lines.append(f"| `{f.metric_id}` | {val_str} | {c.source_date} | `{c.source}` |")
        lines.append("")
    elif any(c.source == NEWS for c in f.claims):
        lines.append("")
        for c in f.claims:
            lines.append(f"> **[{c.source} ({c.source_date})]**: {c.claim} — *{c.evidence}*")
        lines.append("")
    else:
        lines.append("")
        lines.append("- Reported values by source:")
        for c in f.claims:
            val_str = f"value={c.value} {c.unit or ''}" if c.value is not None else "qualitative"
            lines.append(f"  - **{c.source}** ({c.source_date}): {c.claim} ({val_str})")
        lines.append("")

    return lines

def build_briefing(
    supplier: str,
    claims: list[Claim],
    memory: SharedMemory | None = None,
    *,
    tracked_metrics: tuple[str, ...] = TRACKED_METRICS,
    unavailable: dict[str, str] | None = None,
    unavailable_sources: list[str] | None = None,
) -> Briefing:
    """Assemble the coverage-tagged briefing.

    `unavailable` maps a metric_id to a failure reason (from a source that could
    not be read) so its metric is reported under Incomplete with that context.
    """
    # TODO: Group the claims, classify each group into a Finding (with coverage and
    #   escalation), then add Incomplete findings for tracked metrics with no usable
    #   source and for any metric in `unavailable` not otherwise present. Sort
    #   findings by (section order, metric_id) and return a Briefing.
    unavailable = unavailable or {}
    unavailable_sources = unavailable_sources or []

    groups = group_by_metric(claims, memory)
    present_metric_ids = {g.metric_id for g in groups}

    findings: list[Finding] = []

    for g in groups:
        classification, coverage = _classify(g)
        esc, esc_reason = _escalation(g.metric_id, classification, g.claims)
        findings.append(
            Finding(
                metric_id=g.metric_id,
                classification=classification,
                claims=g.claims,
                coverage=coverage,
                escalate=esc,
                escalation_reason=esc_reason,
            )
        )

    all_target_metrics = set(tracked_metrics) | set(unavailable.keys())
    for m_id in all_target_metrics:
        if m_id not in present_metric_ids:
            reason = unavailable.get(m_id, "source unavailable")
            coverage_text = f"missing source: {reason}" if reason else "missing / unobserved"
            dummy_claim = Claim(
                claim=f"Metric {m_id} is incomplete: {reason}",
                evidence=reason,
                source="system",
                source_date=__import__("datetime").date.today(),
                confidence=0.0,
                metric_id=m_id,
            )
            esc, esc_reason = _escalation(m_id, INCOMPLETE, [dummy_claim])
            findings.append(
                Finding(
                    metric_id=m_id,
                    classification=INCOMPLETE,
                    claims=[dummy_claim],
                    coverage=coverage_text,
                    escalate=esc,
                    escalation_reason=esc_reason or reason,
                )
            )

    section_order = {WELL_ESTABLISHED: 0, CONTESTED: 1, INCOMPLETE: 2}
    findings.sort(key=lambda f: (section_order.get(f.classification, 99), f.metric_id))

    return Briefing(
        supplier=supplier,
        findings=findings,
        unavailable_sources=unavailable_sources,
    )