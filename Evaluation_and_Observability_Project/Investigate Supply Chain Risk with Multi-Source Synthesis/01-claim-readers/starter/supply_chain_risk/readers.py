"""Source readers — adapters over differently-shaped evidence sources that all
converge on the same `Claim` representation.

- `read_audit`     : structured supplier-audit JSON
- `read_logistics` : semi-structured shipment CSV (metrics derived from rows)
- `read_quality`   : internal quality records in SQLite
- `read_news`      : unstructured prose, extracted via a `NewsExtractor`
                     (the Anthropic SDK at runtime, a recorded fixture in tests)

Readers return `ReaderResult` — errors are values, not exceptions — so a single
unreadable source never aborts the investigation.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Protocol

from .models import Claim, FailureContext, ReaderResult

AUDIT = "supplier_audit"
LOGISTICS = "logistics"
QUALITY = "internal_quality"
NEWS = "industry_news"


def read_audit(path: str | Path) -> ReaderResult:
    """Parse the structured supplier audit JSON into Claims."""
    path = Path(path)
    # TODO: If the file does not exist, return a ReaderResult with ok=False and a
    #       FailureContext(failure_type="file_not_found", ...). This is an access
    #       failure, distinct from a readable-but-empty source.
    # TODO: Otherwise, load the JSON, parse report_date into a real date, and map
    #       each metric into a Claim with source=AUDIT and source_date=report_date.
    #       Return ReaderResult(source=AUDIT, ok=True, claims=claims).
    if not path.exists():
        return ReaderResult(
            source=AUDIT,
            ok=False,
            error=FailureContext(
                failure_type="file_not_found",
                attempted=str(path),
                alternatives=[],
            ),
        )
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        
        if isinstance(data, list):
            items = data
            report_date = date.today()
        elif isinstance(data, dict):
            date_str = data.get("report_date") or data.get("audit_date") or data.get("date")
            report_date = date.fromisoformat(date_str) if date_str else date.today()

            items = (
                data.get("claims")
                or data.get("metrics")
                or data.get("findings")
                or data.get("audit")
                or []
            )
            if not items and "claim" in data:
                items = [data]
        else:
            items = []

        claims = []
        for item in items:
            if not isinstance(item, dict):
                continue
            d_str = item.get("source_date") or item.get("date")
            item_date = date.fromisoformat(d_str) if d_str else report_date
            
            claims.append(
                Claim(
                    claim=str(item.get("claim", "")),
                    evidence=str(item.get("evidence", "")),
                    source=AUDIT,
                    source_date=item_date,
                    confidence=float(item.get("confidence", 0.9)),
                    metric_id=str(item.get("metric_id", "")),
                    value=float(item["value"]) if item.get("value") is not None else None,
                    unit=str(item["unit"]) if item.get("unit") is not None else None,
                )
            )
        return ReaderResult(source=AUDIT, ok=True, claims=claims)
    except Exception as e:
        return ReaderResult(
            source=AUDIT,
            ok=False,
            error=FailureContext(
                failure_type="parse_error",
                attempted=str(path),
                alternatives=[],
            ),
        )

def _logistics_claims(rows: list[dict[str, str]]) -> list[Claim]:
    # TODO: Derive the delivery metrics from the shipment rows:
    #       on_time_delivery_rate, average_lead_time_days, late_shipment_count.
    #       Use max(collection_date) across rows as the source_date. Return one
    #       Claim per metric with source=LOGISTICS and confidence around 0.85.
    """Derive delivery metrics from the shipment rows."""
    if not rows:
        return []

    dates = []
    for row in rows:
        d_val = row.get("date") or row.get("shipment_date") or row.get("collection_date")
        if d_val:
            try:
                dates.append(date.fromisoformat(d_val.strip()))
            except ValueError:
                pass
    max_date = max(dates) if dates else date.today()

    total_shipments = len(rows)
    on_time_count = sum(
        1 for r in rows if str(r.get("on_time", "")).strip().lower() in ("true", "1", "yes")
    )
    late_count = sum(
        1 for r in rows if str(r.get("on_time", "")).strip().lower() in ("false", "0", "no")
    )

    lead_times = [float(r["lead_time_days"]) for r in rows if r.get("lead_time_days")]
    avg_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0.0
    on_time_rate = (on_time_count / total_shipments * 100.0) if total_shipments > 0 else 0.0

    return [
        Claim(
            claim=f"On-time delivery rate is {on_time_rate:.2f}%",
            evidence=f"Derived from {total_shipments} shipment records.",
            source=LOGISTICS,
            source_date=max_date,
            confidence=0.85,
            metric_id="on_time_delivery_rate",
            value=on_time_rate,
            unit="percent",
        ),
        Claim(
            claim=f"Average lead time is {avg_lead_time:.1f} days",
            evidence=f"Derived from {total_shipments} shipment records.",
            source=LOGISTICS,
            source_date=max_date,
            confidence=0.85,
            metric_id="average_lead_time_days",
            value=avg_lead_time,
            unit="days",
        ),
        Claim(
            claim=f"Late shipment count is {late_count}",
            evidence=f"Derived from {total_shipments} shipment records.",
            source=LOGISTICS,
            source_date=max_date,
            confidence=0.85,
            metric_id="late_shipment_count",
            value=float(late_count),
            unit="count",
        ),
    ]

# Metrics only this source provides — used to report a coverage gap when it fails.
LOGISTICS_EXCLUSIVE_METRICS = ("late_shipment_count",)


def read_logistics(path: str | Path, *, fail_after: int | None = None) -> ReaderResult:
    """Derive delivery metrics from the semi-structured shipment CSV.

    `fail_after` simulates a source timeout after reading that many rows: the
    reader returns `ok=False` with a `FailureContext` carrying the partial
    results gathered before the failure — it does not raise.
    """
    path = Path(path)
    # TODO: Handle a missing file as an access failure (ok=False), as in read_audit.
    # TODO: Read the CSV rows. An empty file is a valid empty result (ok=True, []).
    # TODO (Exercise 3): If fail_after is set and there are more rows than that,
    #       simulate a timeout: compute partial claims from rows[:fail_after] and
    #       return ok=False with a FailureContext(failure_type="timeout",
    #       partial_results=partial, ...). Do not raise.
    # TODO: Otherwise return ReaderResult(source=LOGISTICS, ok=True,
    #       claims=_logistics_claims(rows)).
    if not path.exists():
        return ReaderResult(
            source=LOGISTICS,
            ok=False,
            error=FailureContext(
                failure_type="file_not_found",
                attempted=str(path),
                alternatives=[],
            ),
        )

    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception:
        return ReaderResult(
            source=LOGISTICS,
            ok=False,
            error=FailureContext(
                failure_type="read_error",
                attempted=str(path),
                alternatives=[],
            ),
        )

    if not rows:
        return ReaderResult(source=LOGISTICS, ok=True, claims=[])

    if fail_after is not None and len(rows) > fail_after:
        partial_rows = rows[:fail_after]
        partial_claims = _logistics_claims(partial_rows)
        return ReaderResult(
            source=LOGISTICS,
            ok=False,
            error=FailureContext(
                failure_type="timeout",
                attempted=str(path),
                partial_results=partial_claims,
                alternatives=["read_audit", "read_quality"],
            ),
        )

    return ReaderResult(
        source=LOGISTICS,
        ok=True,
        claims=_logistics_claims(rows),
    )

def read_quality(path: str | Path) -> ReaderResult:
    """Read internal quality records from SQLite."""
    path = Path(path)
    # TODO: Handle a missing file as an access failure (ok=False).
    # TODO: Open the SQLite db, SELECT from quality_metrics, and map each row into
    #       a Claim with source=QUALITY and source_date=date.fromisoformat(recorded_date).
    if not path.exists():
        return ReaderResult(
            source=QUALITY,
            ok=False,
            error=FailureContext(
                failure_type="file_not_found",
                attempted=str(path),
                alternatives=[],
            ),
        )

    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Try default quality_metrics table first
        try:
            cursor.execute("SELECT * FROM quality_metrics")
        except sqlite3.OperationalError:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            if tables:
                cursor.execute(f"SELECT * FROM {tables[0][0]}")
            else:
                raise
                
        rows = cursor.fetchall()
        conn.close()

        claims = []
        for row in rows:
            keys = row.keys()
            claim_text = row["claim"] if "claim" in keys else row[0]
            evidence_text = row["evidence"] if "evidence" in keys else row[1]
            metric_id = row["metric_id"] if "metric_id" in keys else row[2]
            val = row["value"] if "value" in keys else None
            unit = row["unit"] if "unit" in keys else None
            conf = float(row["confidence"]) if "confidence" in keys else 0.9
            
            date_col = row["recorded_date"] if "recorded_date" in keys else (row["date"] if "date" in keys else str(date.today()))

            claims.append(
                Claim(
                    claim=str(claim_text),
                    evidence=str(evidence_text),
                    source=QUALITY,
                    source_date=date.fromisoformat(str(date_col)),
                    confidence=conf,
                    metric_id=str(metric_id),
                    value=float(val) if val is not None else None,
                    unit=str(unit) if unit is not None else None,
                )
            )
        return ReaderResult(source=QUALITY, ok=True, claims=claims)
    except Exception as e:
        return ReaderResult(
            source=QUALITY,
            ok=False,
            error=FailureContext(
                failure_type="sqlite_error",
                attempted=str(path),
                alternatives=[],
            ),
        )

class NewsExtractor(Protocol):
    """Extracts structured claim dicts from one article's prose.

    Implemented by `AnthropicNewsExtractor` (live SDK call) at runtime and by a
    recorded-fixture extractor in tests. Returns a list of raw claim dicts
    matching the `Claim` field names (plus `needs_identifier`/`candidates`).
    """

    def extract(self, article_text: str) -> list[dict[str, object]]: ...


def read_news(path: str | Path, extractor: NewsExtractor) -> ReaderResult:
    """Extract Claims from an unstructured news article via `extractor`.

    A readable article that yields no supplier-relevant claims returns
    `ok=True, claims=[]` (a valid empty result), distinct from a missing file
    (`ok=False`). When the extractor surfaces an ambiguous entity match, the
    resulting Claim carries `needs_identifier=True` and the candidate list —
    the reader does not pick one heuristically.
    """
    path = Path(path)
    # TODO: Handle a missing file as an access failure (ok=False).
    # TODO: Call extractor.extract(article_text) to get raw claim dicts, then map
    #       each into a Claim with source=NEWS and source_date parsed from the dict.
    #       Carry needs_identifier and candidates straight through from the dict —
    #       do NOT resolve an ambiguous match yourself.
    if not path.exists():
        return ReaderResult(
            source=NEWS,
            ok=False,
            error=FailureContext(
                failure_type="file_not_found",
                attempted=str(path),
                alternatives=[],
            ),
        )

    try:
        article_text = path.read_text(encoding="utf-8")
        raw_claims = extractor.extract(article_text)
        claims = []
        for rc in raw_claims:
            candidates_val = rc.get("candidates")
            candidates_tuple = tuple(candidates_val) if candidates_val else ()
            claims.append(
                Claim(
                    claim=str(rc["claim"]),
                    evidence=str(rc["evidence"]),
                    source=NEWS,
                    source_date=date.fromisoformat(str(rc["source_date"])),
                    confidence=float(rc["confidence"]),
                    metric_id=str(rc["metric_id"]),
                    value=float(rc["value"]) if rc.get("value") is not None else None,
                    unit=str(rc["unit"]) if rc.get("unit") is not None else None,
                    needs_identifier=bool(rc.get("needs_identifier", False)),
                    candidates=candidates_tuple,
                )
            )
        return ReaderResult(source=NEWS, ok=True, claims=claims)
    except Exception:
        return ReaderResult(
            source=NEWS,
            ok=False,
            error=FailureContext(
                failure_type="extraction_error",
                attempted=str(path),
                alternatives=[],
            ),
        )