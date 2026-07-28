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
import yaml
from PIL import Image

from magazine import Magazine, ValidationError
from magazine.cli import main as cli_main
from test_manifest import add_spanish_translation, make_project

REPO_ROOT = Path(__file__).resolve().parents[1]


def _spy_on_adapter(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record what ``Magazine.web`` hands the adapter, then let it write.

    The compiler owns the two facts the adapter cannot know -- where the
    composed cover face was compiled, and which canonical URL each source id
    resolves to -- so the seam between them is exactly these keyword
    arguments, and the spy pins them without repeating the adapter's own
    rendering tests.
    """

    import magazine.web_edition as web_edition_module

    real = web_edition_module.write_web_edition
    calls: list[dict] = []

    def spy(edition, destination, *, cover_face=None, source_urls=None):
        calls.append(
            {
                "language": edition.language,
                "cover_face": cover_face,
                "source_urls": source_urls,
            }
        )
        return real(edition, destination, cover_face=cover_face, source_urls=source_urls)

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


def test_a_project_without_the_cover_system_gets_no_face_and_full_source_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """No design file means ``cover_face=None`` -- never an error.

    The design file is the marker that a project carries the cover system;
    every minimal fixture lacks it, and ``mag web`` must keep working there
    rather than demanding resvg, Poppler and cover art it cannot have.  The
    source-id -> canonical-url mapping rides along regardless, because the
    records exist in any project that captured a source.
    """

    make_project(tmp_path)
    calls = _spy_on_adapter(monkeypatch)

    results = Magazine(tmp_path).web("issue-001")

    (call,) = calls
    assert call["cover_face"] is None
    assert call["source_urls"] == {"source-one": "https://example.com/source"}
    assert results[0].index.is_file()


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


def test_a_project_with_the_cover_system_hands_the_composed_face_to_the_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """With the design file present, the adapter receives the compiled face.

    The face is the cover compiler's own ``cover.png``, compiled into the
    canonical ``cover-proof/<language>`` location (memoized by input digest,
    so a later ``mag cover-proof`` finds its work already done).  The fixture
    borrows the repository's real design geometry and sets a solid-color art
    plate, which is enough for the whole SVG -> PDF -> PNG chain to run.
    """

    make_project(tmp_path)
    design = REPO_ROOT / "design" / "covers" / "canto-vivo" / "design.toml"
    target = tmp_path / "design" / "covers" / "canto-vivo" / "design.toml"
    target.parent.mkdir(parents=True)
    target.write_text(design.read_text(encoding="utf-8"), encoding="utf-8")
    art = tmp_path / "editions" / "issue-001" / "art" / "cover-art.png"
    Image.new("RGB", (1200, 1200), "#5332C8").save(art)
    manifest_path = tmp_path / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["cover"]["art_path"] = "editions/issue-001/art/cover-art.png"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    calls = _spy_on_adapter(monkeypatch)

    Magazine(tmp_path).web("issue-001")

    (call,) = calls
    face = call["cover_face"]
    assert face is not None and face.is_file()
    assert face.resolve() == (
        tmp_path / "output" / "issue-001" / "cover-proof" / "en" / "cover.png"
    ).resolve()
