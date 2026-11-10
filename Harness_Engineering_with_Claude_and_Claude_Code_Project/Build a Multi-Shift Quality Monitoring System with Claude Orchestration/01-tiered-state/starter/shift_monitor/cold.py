"""Cold tier: monthly Markdown summaries derived deterministically from the warm tier."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .warm import WarmStore


@dataclass
class ColdStore:
    store: WarmStore
    cold_dir: Path

    def write_monthly_summary(self, year: int, month: int) -> Path:
        # TODO: Produce a Markdown file at `self.cold_dir / "YYYY-MM.md"` with:
        #   - A heading `# YYYY-MM`
        #   - A `Total defects: N` line (from WarmStore.count_for_month)
        #   - A "## Top components" section listing the top-3 components by
        #     count (from WarmStore.top_components_for_month), one per bullet
        # An empty month should still produce a valid file with `Total defects: 0`.
        # Return the path to the written file.
        self.cold_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = self.cold_dir / f"{year:04d}-{month:02d}.md"
        
        total_defects = self.store.count_for_month(year, month)
        top_components = self.store.top_components_for_month(year, month)
        
        lines = [
            f"# {year:04d}-{month:02d}",
            f"Total defects: {total_defects}",
            "",
            "## Top components"
        ]
        
        for item in top_components:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                name, count = item
                lines.append(f"- {name}: {count} defects")
            else:
                lines.append(f"- {item}")
                
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return file_path