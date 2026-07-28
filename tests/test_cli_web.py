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
