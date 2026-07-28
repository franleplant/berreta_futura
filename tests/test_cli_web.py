"""The web seam: a browsable directory per language, outside every gate.

Two properties carry the seam and are pinned here.  First, placement:
``Magazine.web`` writes the screen adapter's self-contained output under
``output/<edition_id>/web/<language>/``, one directory per configured
language in configuration order, exactly where the other per-language proofs
(``cover-proof/<language>``) taught readers of this tree to look.  Second,
independence: the command loads like ``measure`` and ``cover_proof`` -- not
like ``build`` -- so a browsable proof is askable before ledgers and pins are
finished, and its output never joins a package or a release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from magazine import Magazine, ValidationError
from magazine.cli import main as cli_main
from test_manifest import add_spanish_translation, make_project



def _spy_on_adapter(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record what ``Magazine.web`` hands the adapter, then let it write.

    The compiler owns the two facts the adapter cannot know -- where the
    publication's wordmark was materialized, and which canonical URL each
    source id resolves to -- so the seam between them is exactly these
    keyword arguments, and the spy pins them without repeating the adapter's
    own rendering tests.
    """

    import magazine.web_edition as web_edition_module

    real = web_edition_module.write_web_edition
    calls: list[dict] = []

    def spy(edition, destination, **kwargs):
        calls.append({"language": edition.language, **kwargs})
        return real(edition, destination, **kwargs)

    monkeypatch.setattr(web_edition_module, "write_web_edition", spy)
    return calls


def test_web_writes_one_self_contained_directory_per_configured_language(tmp_path: Path):
    """The default is every configured language, in configuration order."""

    make_project(tmp_path)
    add_spanish_translation(tmp_path)

    results = Magazine(tmp_path).web("issue-001")

    assert [written.language for written in results] == ["en", "es"]
    for written in results:
        assert written.output_dir == (
            tmp_path / "output" / "issue-001" / "web" / written.language
        )
        assert written.index == written.output_dir / "index.html"
        assert written.index.is_file()
        # The directory is the adapter's whole contract: stylesheet, fonts and
        # assets ship beside the page, so the folder browses from file://.
        assert (written.output_dir / "edition.css").is_file()
        assert (written.output_dir / "fonts").is_dir()
        assert (written.output_dir / "assets").is_dir()
    # The localized page is the translation, not a relabeled base edition.
    spanish = (tmp_path / "output" / "issue-001" / "web" / "es" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'lang="es-AR"' in spanish
    assert "Artículo" in spanish


def test_web_narrows_to_one_language_and_an_explicit_destination(tmp_path: Path):
    make_project(tmp_path)
    add_spanish_translation(tmp_path)
    destination = tmp_path / "elsewhere"

    results = Magazine(tmp_path).web("issue-001", language="es", destination=destination)

    (written,) = results
    assert written.language == "es"
    assert written.index == destination / "es" / "index.html"
    assert written.index.is_file()
    # Narrowing wrote nothing for the language that was not asked for.
    assert not (destination / "en").exists()
    assert not (tmp_path / "output" / "issue-001" / "web").exists()


def test_web_refuses_an_unconfigured_language_in_its_own_words(tmp_path: Path):
    """The refusal names this command, not the cover proof it borrows from."""

    make_project(tmp_path)

    with pytest.raises(ValidationError, match="Web edition languages are not configured: fr"):
        Magazine(tmp_path).web("issue-001", language="fr")


def test_the_cli_prints_one_line_per_language_and_reports_errors_as_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """``mag web`` speaks the CLI's own conventions: paths out, ``error:`` on 2."""

    make_project(tmp_path)
    add_spanish_translation(tmp_path)

    assert cli_main(["--root", str(tmp_path), "web", "issue-001"]) == 0
    out = capsys.readouterr().out.splitlines()
    web_root = tmp_path / "output" / "issue-001" / "web"
    assert out == [
        f"en: {web_root / 'en' / 'index.html'}",
        f"es: {web_root / 'es' / 'index.html'}",
    ]

    assert cli_main(["--root", str(tmp_path), "web", "issue-001", "--language", "es"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"es: {web_root / 'es' / 'index.html'}"
    ]

    # An unconfigured language and an unknown edition are reported failures --
    # the ``error:`` line and exit 2 every MagazineError gets -- not tracebacks.
    assert cli_main(["--root", str(tmp_path), "web", "issue-001", "--language", "fr"]) == 2
    captured = capsys.readouterr()
    assert "error: Web edition languages are not configured: fr" in captured.err

    assert cli_main(["--root", str(tmp_path), "web", "no-such-edition"]) == 2
    assert "error:" in capsys.readouterr().err


def test_every_project_gets_the_wordmark_and_the_full_source_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The lockup needs only FontTools and the bundled faces, so even a
    minimal fixture project gets it -- outlined from the built-in canto-vivo
    geometry, no design file, resvg or cover art required.  The source-id ->
    canonical-url mapping rides along regardless, because the records exist
    in any project that captured a source.
    """

    make_project(tmp_path)
    calls = _spy_on_adapter(monkeypatch)

    results = Magazine(tmp_path).web("issue-001")

    (call,) = calls
    mark = call["wordmark"]
    assert mark is not None and mark.is_file()
    assert mark == tmp_path / "output" / "issue-001" / "web" / "wordmark.svg"
    svg = mark.read_text(encoding="utf-8")
    assert svg.startswith("<svg ") and 'data-slot="wordmark"' in svg and "viewBox" in svg
    assert call["source_urls"] == {"source-one": "https://example.com/source"}
    assert results[0].index.is_file()
    # The favicon rides beside the lockup, from the same outlined paths.
    icon = call["favicon"]
    assert icon is not None and icon == tmp_path / "output" / "issue-001" / "web" / "favicon.svg"
    assert icon.read_text(encoding="utf-8").startswith("<svg ")
    # The headline break is the cover compiler's own; sibling languages are
    # the alternates, and a single-language project has none.
    assert call["headline_lines"] and " ".join(call["headline_lines"])
    assert call["alternates"] == {}


def test_a_rebuild_clears_its_own_stale_output_and_refuses_foreign_directories(
    tmp_path: Path,
):
    """``Magazine.web`` owns ``output/``, so it may clear a prior web edition.

    A file the previous contract shipped and the current one does not must
    not survive a rebuild -- stale assets ride into any deploy gather -- so
    the language directory is emptied first.  The same clearing refuses a
    non-empty directory with no ``index.html``: that is somebody else's data,
    not a prior web edition, and a refusal beats a wipe.
    """

    make_project(tmp_path)
    magazine = Magazine(tmp_path)
    first = magazine.web("issue-001")
    stale = first[0].output_dir / "assets" / "closing-plate-1.png"
    stale.write_bytes(b"stale plate from an earlier contract")

    second = magazine.web("issue-001")
    assert not stale.exists()
    assert second[0].index.is_file()

    foreign = tmp_path / "output" / "issue-001" / "web" / "en"
    import shutil

    shutil.rmtree(foreign)
    foreign.mkdir(parents=True)
    (foreign / "keep.txt").write_text("not a web edition", encoding="utf-8")
    with pytest.raises(ValidationError, match="refusing to clear"):
        magazine.web("issue-001")
    assert (foreign / "keep.txt").read_text(encoding="utf-8") == "not a web edition"


def test_the_written_pages_link_the_source_by_its_canonical_url(tmp_path: Path):
    """The record's canonical URL appears as a working ``href`` in the output.

    The compiler reads the mapping from the source records and the adapter
    turns it into anchors; this asserts the round trip at the level a reader
    experiences it -- the URL is followable from the written HTML -- without
    pinning which element carries it.
    """

    make_project(tmp_path)

    Magazine(tmp_path).web("issue-001", language="en")

    pages = list((tmp_path / "output" / "issue-001" / "web" / "en").glob("*.html"))
    assert pages
    assert any(
        'href="https://example.com/source"' in page.read_text(encoding="utf-8")
        for page in pages
    )


def test_one_wordmark_serves_every_language_and_lands_on_every_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The lockup is publication identity, never translated: both languages
    receive the same file, written once at the web root, and every written
    page -- cover and pieces alike -- sets it from ``assets/wordmark.svg``.
    """

    make_project(tmp_path)
    add_spanish_translation(tmp_path)
    calls = _spy_on_adapter(monkeypatch)

    results = Magazine(tmp_path).web("issue-001")

    (mark,) = {call["wordmark"] for call in calls}
    assert mark == tmp_path / "output" / "issue-001" / "web" / "wordmark.svg"
    for result in results:
        shipped = result.output_dir / "assets" / "wordmark.svg"
        assert shipped.read_bytes() == mark.read_bytes()
        for page in result.output_dir.glob("*.html"):
            assert 'src="assets/wordmark.svg"' in page.read_text(encoding="utf-8"), page
