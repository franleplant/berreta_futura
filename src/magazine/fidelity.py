from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from .document_structure import visible_blocks
from .errors import ValidationError
from .io import load_structured
from .publication_document import DocumentParseError, parse_publication_document

STATUSES = {"retained", "boilerplate_removed", "substantive_cut", "modified", "editorial_addition"}
CONTENT_MODES = {"faithful_edit", "faithful_synthesis", "selected_extracts", "original_synthesis"}
DISTANCING_VERBS = (
    r"argues?|says?|writes?|explains?|describes?|observes?|contends?|notes?|"
    r"frames?|treats?|uses?|calls?|divides?|considers?|distinguishes?|proposes?|"
    r"suggests?|predicts?|believes?|rejects?"
)
DISTANCING_NARRATION = re.compile(
    rf"\b(?:the\s+)?(?:author|speaker|writer|presenter|article|essay|talk|keynote|presentation)"
    rf"\b[^.!?]{{0,40}}\b(?:{DISTANCING_VERBS})\b",
    re.IGNORECASE,
)


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
    content_mode: str
    manuscript_blocks: int | None = None
    ledger_blocks: int | None = None

    @property
    def retention_percent(self) -> float:
        if not self.source_words:
            return 100.0
        return round(100 * self.retained_words / self.source_words, 1)

    def as_markdown(self, title: str, *, language: str = "en") -> str:
        labels = _REPORT_LABELS.get(language.split("-", 1)[0], _REPORT_LABELS["en"])
        rows = [
            (labels["content_mode"], f"`{self.content_mode}`"),
            (labels["source_words"], self.source_words),
            (labels["retained_words"], self.retained_words),
            (labels["boilerplate_words"], self.removed_boilerplate_words),
            (labels["substantive_cuts"], self.substantive_cut_words),
            (labels["modified_source_words"], self.modified_source_words),
            (labels["modified_edited_words"], self.modified_edited_words),
            (labels["editorial_additions"], self.editorial_addition_words),
            (labels["retention"], f"{self.retention_percent}%"),
        ]
        if self.content_mode == "faithful_synthesis":
            output_words = self.retained_words + self.modified_edited_words + self.editorial_addition_words
            compression = round(100 * output_words / self.source_words, 1) if self.source_words else 0.0
            rows.extend([
                (labels["synthesis_words"], output_words),
                (labels["output_source"], f"{compression}%"),
            ])
        if self.manuscript_blocks is not None:
            rows.append((
                labels["integrity"],
                labels["integrity_value"].format(
                    ledger=self.ledger_blocks,
                    manuscript=self.manuscript_blocks,
                ),
            ))
        text = [
            f"## {title}",
            "",
            f"| {labels['measure']} | {labels['value']} |",
            "|---|---:|",
        ]
        text.extend(f"| {name} | {value} |" for name, value in rows)
        return "\n".join(text)


_REPORT_LABELS = {
    "en": {
        "measure": "Measure",
        "value": "Value",
        "content_mode": "Content mode",
        "source_words": "Original substantive words",
        "retained_words": "Retained verbatim",
        "boilerplate_words": "Removed as boilerplate",
        "substantive_cuts": "Substantive cuts",
        "modified_source_words": "Modified source words",
        "modified_edited_words": "Modified edited words",
        "editorial_additions": "Editorial additions",
        "retention": "Verbatim retention",
        "synthesis_words": "Synthesis output words",
        "output_source": "Output / source",
        "integrity": "Manuscript integrity",
        "integrity_value": "PASS ({ledger} ledger entries / {manuscript} manuscript blocks)",
    },
    "es": {
        "measure": "Medida",
        "value": "Valor",
        "content_mode": "Modo de contenido",
        "source_words": "Palabras sustantivas originales",
        "retained_words": "Conservadas literalmente",
        "boilerplate_words": "Eliminadas como texto accesorio",
        "substantive_cuts": "Recortes sustantivos",
        "modified_source_words": "Palabras modificadas de la fuente",
        "modified_edited_words": "Palabras modificadas de la edición",
        "editorial_additions": "Añadidos editoriales",
        "retention": "Conservación literal",
        "synthesis_words": "Palabras de la síntesis",
        "output_source": "Resultado / fuente",
        "integrity": "Integridad del manuscrito",
        "integrity_value": "APROBADA ({ledger} entradas del registro / {manuscript} bloques del manuscrito)",
    },
}


def _visible_prose(text: str) -> str:
    """Return reader-visible prose, ignoring Markdown presentation syntax."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<([^>]+)>", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return " ".join(text.split())


def _visible_code(text: str) -> str:
    lines = [line.rstrip() for line in text.expandtabs(4).splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _manuscript_blocks(path: Path) -> list[tuple[str, str]]:
    """Parse the source-article portion of a manuscript into visible blocks.

    The blocks come from the same CommonMark parse the renderer typesets
    (:func:`magazine.publication_document.parse_publication_document`), so the
    gate sees ordered lists, nested lists, block quotes and thematic breaks
    exactly as the printed page does.  YAML frontmatter is production metadata,
    while title and author are supplied by the edition manifest during
    rendering; neither is source-article content, and the parser removes it.

    Ledger text is raw Markdown-flavoured prose normalized by
    :func:`_visible_prose`, so the manuscript's flattened text goes through the
    same normalization -- symmetric folding is what makes the word streams
    comparable.  List markers and thematic breaks contribute no words: the
    renderer draws them as furniture, and the ledger never carries them.
    """
    try:
        document = parse_publication_document(path.read_text(encoding="utf-8"))
    except DocumentParseError as exc:
        raise ValidationError(f"{path}: {exc}") from exc
    blocks: list[tuple[str, str]] = []
    for kind, text in visible_blocks(document.blocks):
        if kind == "code":
            blocks.append((kind, _visible_code(text)))
            continue
        value = _visible_prose(text)
        if value:
            blocks.append((kind, value))
    return blocks


def _ledger_blocks(paragraphs: list[dict]) -> list[tuple[str, str, str]]:
    blocks: list[tuple[str, str, str]] = []
    for index, paragraph in enumerate(paragraphs):
        status = paragraph.get("status")
        if status in {"boilerplate_removed", "substantive_cut"}:
            continue
        kind = str(paragraph.get("kind", "p"))
        if kind.startswith("h"):
            kind = "h" + kind[1:]
        text = paragraph.get("edited") if status in {"modified", "editorial_addition"} else paragraph.get("source")
        visible = _visible_code(str(text or "")) if kind == "code" else _visible_prose(str(text or ""))
        if status == "editorial_addition":
            label = _visible_prose(str(paragraph.get("label", ""))).rstrip(":")
            visible = f"{label}: {visible}"
        blocks.append((kind, visible, str(paragraph.get("id", index + 1))))
    return blocks


def _short(text: str, limit: int = 100) -> str:
    one_line = text.replace("\n", " ")
    return one_line if len(one_line) <= limit else one_line[: limit - 3] + "..."


def _sentences(text: str) -> list[str]:
    """Split prose coarsely enough to compare author mentions with source wording."""
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])(?:\s+|$)|\n+", text)
        if sentence.strip()
    ]


def validate_faithful_synthesis_voice(
    path: Path,
    paragraphs: list[dict],
    source_author: str,
) -> None:
    """Reject magazine-narrator framing added to a source-author synthesis.

    A faithful synthesis is already attributed by its byline and mode label. Its
    adapted prose therefore stays in the source's voice instead of repeatedly
    telling the reader what the bylined author says. Exact source sentences are
    exempt so this check never forces a rewrite of source wording.
    """
    author = source_author.strip()
    if not author:
        return
    name_parts = author.casefold().split()
    surname = name_parts[-1]
    first_name = name_parts[0]
    errors: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        if paragraph.get("status") != "modified":
            continue
        source = " ".join(str(paragraph.get("source", "")).split()).casefold()
        for sentence in _sentences(str(paragraph.get("edited", ""))):
            sentence_words: set[str] = set()
            for word in re.findall(r"[\w'-]+", sentence):
                folded = word.casefold()
                sentence_words.add(folded[:-2] if folded.endswith("'s") else folded)
            normalized = " ".join(sentence.split()).casefold()
            names_author = (
                surname in sentence_words
                or author.casefold() in normalized
                or (
                    first_name in sentence_words
                    and re.search(rf"\b(?:{DISTANCING_VERBS})\b", sentence, re.IGNORECASE)
                )
            )
            if (
                not names_author
                and not DISTANCING_NARRATION.search(sentence)
            ) or normalized in source:
                continue
            ledger_id = paragraph.get("id", index + 1)
            errors.append(
                f"{path}: modified entry {ledger_id} adds detached narration about "
                f"the bylined author: {_short(sentence)!r}. Preserve the source's "
                "grammatical person (including first person), or retain the exact "
                "source sentence."
            )
    if errors:
        raise ValidationError(errors)


def _validate_manuscript(path: Path, manuscript: Path, paragraphs: list[dict]) -> tuple[int, int]:
    expected = _ledger_blocks(paragraphs)
    actual = _manuscript_blocks(manuscript)
    expected_code = [(value, ledger_id) for kind, value, ledger_id in expected if kind == "code"]
    actual_code = [value for kind, value in actual if kind == "code"]
    if len(expected_code) != len(actual_code):
        raise ValidationError(
            f"{manuscript}: manuscript has {len(actual_code)} code blocks but {path} derives "
            f"{len(expected_code)}; code blocks must remain ordered and line-faithful"
        )
    for index, ((expected_text, ledger_id), actual_text) in enumerate(zip(expected_code, actual_code)):
        if expected_text != actual_text:
            expected_lines = expected_text.splitlines()
            actual_lines = actual_text.splitlines()
            mismatch = next(
                (
                    line_index
                    for line_index, pair in enumerate(zip(expected_lines, actual_lines))
                    if pair[0] != pair[1]
                ),
                min(len(expected_lines), len(actual_lines)),
            )
            expected_line = expected_lines[mismatch] if mismatch < len(expected_lines) else "<end of ledger block>"
            actual_line = actual_lines[mismatch] if mismatch < len(actual_lines) else "<end of manuscript block>"
            raise ValidationError(
                f"{manuscript}: code block {index + 1} diverges from ledger entry {ledger_id} "
                f"at line {mismatch + 1}; expected {expected_line!r}, found {actual_line!r}. "
                "Code line breaks and indentation are substantive and must match."
            )
    # Source captures do not always agree on paragraph boundaries (a narrated
    # slide can contain two Markdown paragraphs in one ledger entry), so compare
    # the complete reader-visible content stream rather than YAML row counts.
    expected_words = " ".join(value for _, value, _ in expected).split()
    actual_words = " ".join(value for _, value in actual).split()
    if expected_words != actual_words:
        mismatch = next(
            (index for index, pair in enumerate(zip(expected_words, actual_words)) if pair[0] != pair[1]),
            min(len(expected_words), len(actual_words)),
        )
        start = max(0, mismatch - 5)
        expected_excerpt = " ".join(expected_words[start : mismatch + 12]) or "<end of ledger>"
        actual_excerpt = " ".join(actual_words[start : mismatch + 12]) or "<end of manuscript>"
        raise ValidationError(
            f"{manuscript}: source content diverges from ledger-derived edited text at word {mismatch + 1}; "
            f"expected '{_short(expected_excerpt)}', found '{_short(actual_excerpt)}'. "
            f"The ledger derives {len(expected_words)} visible words and the manuscript contains {len(actual_words)}."
        )
    return len(actual), len(expected)


def fidelity_report(
    path: Path,
    manuscript: Path | None = None,
    *,
    source_author: str | None = None,
) -> FidelityReport:
    data = load_structured(path)
    content_mode = str(data.get("content_mode", "faithful_edit"))
    if content_mode not in CONTENT_MODES:
        raise ValidationError(f"{path}: invalid content_mode: {content_mode}")
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
    if manuscript is None and path.parent.name == "fidelity":
        manuscript = path.parent.parent / "articles" / f"{path.stem}.md"
    manuscript_blocks = None
    ledger_blocks = None
    if manuscript is not None:
        if not manuscript.is_file():
            raise ValidationError(f"{path}: corresponding manuscript does not exist: {manuscript}")
        manuscript_blocks, ledger_blocks = _validate_manuscript(path, manuscript, paragraphs)
    source_words = totals["retained"] + totals["boilerplate_removed"] + totals["substantive_cut"] + totals["modified"]
    if content_mode == "faithful_synthesis":
        synthesized_words = totals["retained"] + modified_edited + totals["editorial_addition"]
        if not counts["modified"]:
            raise ValidationError(f"{path}: faithful_synthesis requires source-to-edited mappings")
        if source_words and synthesized_words >= source_words:
            raise ValidationError(f"{path}: faithful_synthesis must materially condense its source")
        if source_author:
            validate_faithful_synthesis_voice(path, paragraphs, source_author)
    return FidelityReport(source_words, totals["retained"], totals["boilerplate_removed"], totals["substantive_cut"], totals["modified"], modified_edited, totals["editorial_addition"], counts, content_mode, manuscript_blocks, ledger_blocks)
