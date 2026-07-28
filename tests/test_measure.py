"""The measurement seam: fast page budgets off the reader's real pagination.

Two properties carry the module's whole value and are pinned here.  First,
honesty: a measured article span must equal the ``layout.article_pages`` a
full build writes into ``edition-manifest.json`` for the same bytes, because
measurement reuses the adapter's own pagination path rather than
approximating it.  Second, timing: a budget breach is a *report* from
``measure`` and an exit code from ``fit``, never an exception, because the
seam exists to deliver the build's verdict before the ledger, translation and
pins that a refusing build would waste.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from magazine import Magazine, ValidationError
from magazine.cli import main as cli_main
from test_manifest import make_project

_LONG_PARAGRAPH = " ".join(["alpha bravo charlie delta echo foxtrot golf hotel"] * 10)


def _overflow_editorial(root: Path) -> None:
    """Declare the one-page house cap and write an editorial that breaks it.

    The fixture editorial is one paragraph; six long ones flow onto a second
    reader page, which is exactly the state an author needs to hear about
    *before* finishing the rest of the edition -- a build refuses it outright.
    """

    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["format"] = {"max_editorial_pages": 1}
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (root / "editions" / "issue-001" / "editorial.md").write_text(
        "---\ntitle: A Test Editorial\nbyline: The editors\nlabel: ORIGINAL EDITORIAL\n---\n\n"
        + "\n\n".join([_LONG_PARAGRAPH] * 6),
        encoding="utf-8",
    )


def test_measurement_reports_real_spans_and_matches_a_build(tmp_path: Path):
    """Measured spans are the build's own layout facts, written by neither."""

    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    measurement = magazine.measure("issue-001")

    assert measurement.edition_id == "issue-001"
    assert measurement.engine == "weasyprint"
    assert measurement.ok and measurement.breaches == ()
    assert [language.language for language in measurement.languages] == ["en"]
    language = measurement.languages[0]
    # A reader is an A4-fold signature, opened by two cover slots and the
    # contents on logical page three.
    assert language.total_pages % 4 == 0
    assert language.contents_pages >= 1
    assert language.content_pages + language.closing_plates + 2 == language.total_pages
    assert language.editorial is not None
    assert language.editorial.pages == 1 and not language.editorial.over
    (article,) = language.articles
    assert article.id == "article"
    assert article.cap == 7 and not article.over and not article.under_minimum
    assert article.first_page <= article.last_page
    assert article.pages <= article.last_page - article.first_page + 1
    assert article.last_page_body_lines >= 1
    assert article.flow_bottom > 0

    # The honesty property: a full build of the same bytes records the same
    # spans in its packaged manifest, because both counted the same box tree.
    result = magazine.build("issue-001")
    layout = json.loads(
        (result.output_dir / "edition-manifest.json").read_text(encoding="utf-8")
    )["layout"]
    assert layout["article_pages"] == {
        item.id: item.pages for item in language.articles
    }
    assert layout["editorial_pages"] == language.editorial.pages


def test_a_budget_breach_is_reported_by_measure_and_an_exit_code_from_fit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    make_project(tmp_path)
    _overflow_editorial(tmp_path)

    # ``measure`` reports the breach rather than raising: this edition would
    # not build, and hearing why without building is the point of the seam.
    measurement = Magazine(tmp_path).measure("issue-001")
    assert not measurement.ok
    assert any(
        "editorial" in breach and "maximum 1" in breach
        for breach in measurement.breaches
    )
    editorial = measurement.languages[0].editorial
    assert editorial is not None and editorial.over and editorial.pages > editorial.cap
    # Six long paragraphs give the rag table something to say: multi-line
    # blocks only, each last line a fraction of its own measure.
    paragraphs = measurement.languages[0].paragraphs
    assert paragraphs
    assert all(row.lines >= 2 for row in paragraphs)
    assert all(0 < row.last_line_fraction <= 1 for row in paragraphs)
    assert all(row.runt == (row.last_line_words == 1) for row in paragraphs)

    # ``fit`` turns the same breach into exit code 1 -- distinct from the 2 a
    # MagazineError exits with -- and names it on stdout.
    assert cli_main(["--root", str(tmp_path), "fit", "issue-001"]) == 1
    table = capsys.readouterr().out
    assert "OVER" in table and "over budget" in table

    # ``measure`` stays exit 0 on the same breach: it is a dump, not a gate.
    assert cli_main(["--root", str(tmp_path), "measure", "issue-001"]) == 0
    dumped = json.loads(capsys.readouterr().out)
    assert dumped["ok"] is False and dumped["breaches"]


def test_fit_passes_and_exits_zero_within_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    make_project(tmp_path)

    assert cli_main(["--root", str(tmp_path), "fit", "issue-001"]) == 0
    table = capsys.readouterr().out
    assert "every page budget holds" in table
    assert "article" in table and "/7" in table and "editorial" in table


def test_measure_json_shape_is_stable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """The dump is an agent interface, so its keys are part of the contract."""

    make_project(tmp_path)
    destination = tmp_path / "reports" / "measure.json"
    assert (
        cli_main(
            ["--root", str(tmp_path), "measure", "issue-001", "--json", str(destination)]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == str(destination)
    dumped = json.loads(destination.read_text(encoding="utf-8"))

    assert sorted(dumped) == ["breaches", "edition_id", "engine", "languages", "ok"]
    language = dumped["languages"]["en"]
    assert sorted(language) == [
        "articles", "closing_plates", "content_pages", "contents_pages",
        "editorial", "language", "paragraphs", "total_pages",
    ]
    assert sorted(language["editorial"]) == [
        "cap", "first_page", "last_page", "over", "pages",
    ]
    for article in language["articles"]:
        assert sorted(article) == [
            "cap", "end_mark_offset", "first_page", "flow_bottom", "id",
            "last_page", "last_page_body_lines", "minimum", "over", "pages",
            "tail_art_height", "under_minimum",
        ]
    for paragraph in language["paragraphs"]:
        assert sorted(paragraph) == [
            "key", "last_line_fraction", "last_line_words", "lines", "page", "runt",
        ]


def test_refusals_name_measurement_and_come_before_any_layout(tmp_path: Path):
    """A wrong language or a wrong engine fails fast, in measurement's words."""

    make_project(tmp_path)
    with pytest.raises(ValidationError, match="Measurement languages are not configured"):
        Magazine(tmp_path).measure("issue-001", language="fr")

    # The guard reads configuration alone, so flipping the engine key is the
    # whole fixture: a ReportLab project's page counts are not WeasyPrint's,
    # and a measurement that pretended otherwise would be the drift this
    # module exists to make impossible.
    (tmp_path / "magazine.toml").write_text(
        '[publication]\nname = "Test Review"\n[render]\nengine = "reportlab"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="WeasyPrint reader"):
        Magazine(tmp_path).measure("issue-001")
