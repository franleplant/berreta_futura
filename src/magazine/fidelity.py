from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ValidationError
from .io import load_structured

STATUSES = {"retained", "boilerplate_removed", "substantive_cut", "modified", "editorial_addition"}


def word_count(text: str) -> int:
    return len(text.split())


@dataclass(frozen=True)
class FidelityReport:
    source_words: int
    retained_words: int
    removed_boilerplate_words: int
    substantive_cut_words: int
    modified_source_words: int
    modified_edited_words: int
    editorial_addition_words: int
    paragraph_counts: dict[str, int]

    @property
    def retention_percent(self) -> float:
        if not self.source_words:
            return 100.0
        return round(100 * self.retained_words / self.source_words, 1)

    def as_markdown(self, title: str) -> str:
        rows = [
            ("Original substantive words", self.source_words),
            ("Retained verbatim", self.retained_words),
            ("Removed as boilerplate", self.removed_boilerplate_words),
            ("Substantive cuts", self.substantive_cut_words),
            ("Modified source words", self.modified_source_words),
            ("Modified edited words", self.modified_edited_words),
            ("Editorial additions", self.editorial_addition_words),
            ("Verbatim retention", f"{self.retention_percent}%"),
        ]
        text = [f"## {title}", "", "| Measure | Value |", "|---|---:|"]
        text.extend(f"| {name} | {value} |" for name, value in rows)
        return "\n".join(text)


def fidelity_report(path: Path) -> FidelityReport:
    data = load_structured(path)
    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list):
        raise ValidationError(f"{path}: paragraphs must be a list")
    totals = {status: 0 for status in STATUSES}
    counts = {status: 0 for status in STATUSES}
    modified_edited = 0
    errors: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, dict) or paragraph.get("status") not in STATUSES:
            errors.append(f"{path}: paragraph {index + 1} has invalid status")
            continue
        status = paragraph["status"]
        source = str(paragraph.get("source", ""))
        edited = str(paragraph.get("edited", ""))
        if status == "modified" and (not source or not edited):
            errors.append(f"{path}: modified paragraph {index + 1} requires source and edited text")
        if status == "editorial_addition" and not paragraph.get("label"):
            errors.append(f"{path}: editorial addition {index + 1} requires a visible label")
        counts[status] += 1
        totals[status] += word_count(edited if status == "editorial_addition" else source)
        if status == "modified":
            modified_edited += word_count(edited)
    if errors:
        raise ValidationError(errors)
    source_words = totals["retained"] + totals["boilerplate_removed"] + totals["substantive_cut"] + totals["modified"]
    return FidelityReport(source_words, totals["retained"], totals["boilerplate_removed"], totals["substantive_cut"], totals["modified"], modified_edited, totals["editorial_addition"], counts)

