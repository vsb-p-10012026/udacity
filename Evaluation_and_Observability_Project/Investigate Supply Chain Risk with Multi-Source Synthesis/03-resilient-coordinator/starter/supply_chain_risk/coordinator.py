"""Coordinator — deterministic control-flow over the source readers.

Runs each scoped reader, collects successful claims into shared memory, and hands
them to synthesis. Error propagation is local-recovery: a reader that fails
returns a `ReaderResult` with structured `FailureContext`; the coordinator
proceeds on the remaining sources and annotates the gap in the briefing rather
than aborting. Only successful claims are written to shared memory — failures are
recorded as coverage gaps, not vectorized.

This is intentionally a plain control-flow function, not an LLM-driven
orchestrator (multi-agent orchestration is a separate module).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .memory import SharedMemory
from .models import ReaderResult
from .readers import (
    LOGISTICS_EXCLUSIVE_METRICS,
    NewsExtractor,
    read_audit,
    read_logistics,
    read_news,
    read_quality,
)
from .synthesis import Briefing, build_briefing

# Metrics each source is the sole expected provider of (for gap attribution).
EXCLUSIVE_METRICS = {"logistics": LOGISTICS_EXCLUSIVE_METRICS}


@dataclass
class InvestigationResult:
    briefing: Briefing
    reader_results: list[ReaderResult]


def investigate(
    supplier: str,
    data_dir: str | Path,
    extractor: NewsExtractor,
    *,
    simulate_logistics_timeout: bool = False,
    logistics_fail_after: int = 5,
    memory: SharedMemory | None = None,
) -> InvestigationResult:
    # TODO: Run every reader (audit, logistics, quality, and read_news for each
    #   article in data_dir/news). Pass fail_after to read_logistics only when
    #   simulate_logistics_timeout is set.
    # TODO: Keep only claims from successful reads (r.ok). For each FAILED read,
    #   record an "unavailable" note and map the source's EXCLUSIVE_METRICS to a
    #   gap reason — but only for metrics no surviving source reported.
    # TODO: Add ONLY the successful claims to shared memory (never partial results),
    #   then call build_briefing with the unavailable annotations. Return an
    #   InvestigationResult carrying the briefing and all reader_results.
    """Run the complete supply-chain investigation pipeline across all sources."""
    data_dir = Path(data_dir)
    memory = memory or SharedMemory()

    reader_results: list[ReaderResult] = []

    # 1. Audit reader
    audit_path = data_dir / "audit.json"
    if not audit_path.exists():
        for p in data_dir.glob("*.json"):
            audit_path = p
            break
    reader_results.append(read_audit(audit_path))

    # 2. Logistics reader
    logistics_path = data_dir / "shipments.csv"
    if not logistics_path.exists():
        for p in data_dir.glob("*.csv"):
            logistics_path = p
            break
    fail_after = logistics_fail_after if simulate_logistics_timeout else None
    reader_results.append(read_logistics(logistics_path, fail_after=fail_after))

    # 3. Quality reader
    quality_path = data_dir / "quality.sqlite"
    if not quality_path.exists():
        for p in data_dir.glob("*.sqlite"):
            quality_path = p
            break
        for p in data_dir.glob("*.db"):
            quality_path = p
            break
    reader_results.append(read_quality(quality_path))

    # 4. News reader
    news_dir = data_dir / "news"
    if news_dir.exists() and news_dir.is_dir():
        for article_path in sorted(news_dir.glob("*.txt")):
            reader_results.append(read_news(article_path, extractor))

    # Collect successful claims
    all_successful_claims: list[Claim] = []
    surviving_metric_ids: set[str] = set()

    for r in reader_results:
        if r.ok:
            all_successful_claims.extend(r.claims)
            for c in r.claims:
                surviving_metric_ids.add(c.metric_id)

    # Write ONLY successful claims to shared memory
    if all_successful_claims:
        memory.add_claims(all_successful_claims)

    # Map unavailable sources and exclusive metric gaps
    unavailable_sources: list[str] = []
    unavailable_map: dict[str, str] = {}

    for r in reader_results:
        if not r.ok:
            source_name = r.source
            if source_name not in unavailable_sources:
                unavailable_sources.append(source_name)

            error_type = r.error.failure_type if r.error else "failed"

            exclusive_metrics = EXCLUSIVE_METRICS.get(source_name, ())
            for m_id in exclusive_metrics:
                if m_id not in surviving_metric_ids:
                    unavailable_map[m_id] = f"Source {source_name} failed ({error_type})"

    briefing = build_briefing(
        supplier=supplier,
        claims=all_successful_claims,
        memory=memory,
        unavailable=unavailable_map,
        unavailable_sources=unavailable_sources,
    )

    return InvestigationResult(
        briefing=briefing,
        reader_results=reader_results,
    )