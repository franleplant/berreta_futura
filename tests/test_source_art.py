"""Artistic source codes: authored artwork around the article-tail QR.

Three seams are under test and none of them runs the real image model.  The
*acceptance gate* is judged against images composed right here with segno and
Pillow -- a true symbol pasted onto cover-palette shapes, which is exactly the
pixel-preserving composition the generator is prompted toward -- so "accepted"
and "rejected" are facts about pixels and never about a stubbed verdict.  The
*authoring command* runs against a stub generator standing where codex would,
because the command's obligations (retry, give up loudly, save nothing that
failed, never edit the manifest) are deterministic even though the generator is
not.  And the *build integration* renders real pages, because the artwork's
whole contract is that `_validate_source_codes` still reads the finished sheet
with a general barcode reader and refuses anything that does not decode to the
canonical URL in the placed box.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import segno
import yaml
from PIL import Image, ImageDraw

import magazine.source_art as source_art
import magazine.weasyprint_adapter as adapter
from magazine import Magazine, ValidationError
from magazine.cli import parser
from magazine.errors import DependencyError
from magazine.manifest import _edition_copy_sha256, load_translation
from magazine.source_art import (
    generate_source_art,
    measure_source_code_art,
    review_source_code_art,
)
from magazine.weasyprint_adapter import _apply_source_codes, render_a5_weasyprint
from test_manifest import add_spanish_translation, make_project
from test_weasyprint_adapter import (
    _FONT_SAFE_MANUSCRIPT,
    _parse_article_fragment,
    _raster_edition,
)

# The fixture source's canonical URL (test_manifest.make_project) and the
# adapter fixture's (test_html_edition._edition).
_FIXTURE_URL = "https://example.com/source"
_ADAPTER_URL = "https://example.test/source?a=1&b=2"

_FILLER_PARAGRAPH = (
    "It continues with a further considered paragraph of measured prose that "
    "keeps the argument moving without ornament, so the page fills at a known "
    "and steady rate for the experiment. "
)


def compose_art(
    path: Path,
    url: str,
    *,
    fraction: float = 0.65,
    pixels: int = 1024,
    dark: str = "#11131A",
    ground: str = "#FFFFFF",
    decorate: bool = True,
    center_offset: int = 0,
) -> Path:
    """A composed artwork of the pixel-preserving kind the generator is asked for.

    A true segno symbol, resized nearest-neighbour so no module is resampled,
    pasted at ``fraction`` of a white-ground canvas (offset by
    ``center_offset``), with hard-edged violet, ink and orange fields engaging
    the symbol from outside its own quiet zone -- and staying clear of the
    canvas borders' white majority, the label band right of the symbol's foot,
    and the quiet ring, exactly as the prompt instructs the generator.
    """
    symbol = segno.make(url, error="H", micro=False)
    modules = symbol.symbol_size(border=0)[0]
    buffer = io.BytesIO()
    symbol.save(buffer, kind="png", scale=16, border=0, dark=dark, light=ground)
    qr = Image.open(buffer).convert("RGB")
    canvas = Image.new("RGB", (pixels, pixels), ground)
    target = round(fraction * pixels)
    offset = (pixels - target) // 2 + center_offset
    canvas.paste(qr.resize((target, target), Image.NEAREST), (offset, offset))
    if decorate:
        quiet = -(-4 * target // modules)
        margin = (pixels - target) // 2 - quiet
        draw = ImageDraw.Draw(canvas)
        if margin > 16:
            draw.rectangle([0, 0, int(0.5 * pixels), margin - 9], fill="#5332C8")
            draw.rectangle(
                [0, pixels - margin + 8, int(0.45 * pixels), pixels - 1], fill="#11131A"
            )
            draw.polygon(
                [(0, pixels - margin), (int(0.10 * pixels), pixels - margin + 8), (0, pixels - 1)],
                fill="#FF5A1F",
            )
    canvas.save(path)
    return path


def _stub_runner(url: str, *, fraction: float = 0.65, pixels: int = 1024, **kwargs):
    """A generator double: composes a candidate where codex would have."""
    calls: list[tuple[list[str], Path]] = []

    def run(command: list[str], cwd: Path) -> None:
        calls.append((command, cwd))
        compose_art(cwd / "art.png", url, fraction=fraction, pixels=pixels, **kwargs)

    run.calls = calls
    return run


# ---------------------------------------------------------------------------
# The acceptance gate, judged on real pixels.
# ---------------------------------------------------------------------------


def test_a_composed_artwork_with_a_true_symbol_passes_the_whole_gate(tmp_path: Path):
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL)

    assert review_source_code_art(art, _ADAPTER_URL) == []
    measurement = measure_source_code_art(art)
    assert measurement.payload == _ADAPTER_URL
    assert measurement.fraction == pytest.approx(0.65, abs=0.02)
    assert measurement.pixels == 1024
    # The module count is the decoded symbol's own -- the adapter's cell
    # arithmetic divides the printed ink span by it, so it must describe the
    # symbol the artwork carries (ECC-H for this URL: version 5, 37 modules).
    assert measurement.modules == segno.make(
        _ADAPTER_URL, error="H", micro=False
    ).symbol_size(border=0)[0]


def test_the_gate_rejects_a_symbol_carrying_the_wrong_payload(tmp_path: Path):
    art = compose_art(tmp_path / "art.png", "https://example.test/somewhere-else")

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("canonical URL" in failure for failure in failures)


def test_the_gate_rejects_a_raster_too_small_for_the_largest_tail_square(tmp_path: Path):
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL, pixels=640)

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("300 ppi" in failure for failure in failures)


def test_the_gate_rejects_artwork_outside_the_cover_ink_set(tmp_path: Path):
    art = compose_art(
        tmp_path / "art.png", _ADAPTER_URL, ground="#7A9E4F", decorate=False
    )

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("cover ink set" in failure for failure in failures)


def test_the_gate_holds_signal_orange_under_five_percent(tmp_path: Path):
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL, decorate=False)
    with Image.open(art) as image:
        canvas = image.convert("RGB")
    ImageDraw.Draw(canvas).rectangle([0, 0, 1023, 120], fill="#FF5A1F")
    canvas.save(art)

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("signal orange" in failure.lower() for failure in failures)


def test_the_gate_rejects_an_image_with_no_decodable_symbol(tmp_path: Path):
    art = tmp_path / "art.png"
    Image.new("RGB", (1024, 1024), "#F1EADB").save(art)

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert failures
    assert any("decodable QR" in failure for failure in failures)


def test_the_gate_rejects_modules_set_in_violet_that_a_mono_printer_would_screen(
    tmp_path: Path,
):
    """A violet symbol decodes in this room and halftones into holes on paper."""
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL, dark="#5332C8")

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("INK" in failure for failure in failures)


def test_the_gate_enforces_the_symbol_s_span_and_placement_contract(tmp_path: Path):
    """The build derives the placed box from the measured footprint, so the
    footprint must be one the position gate can always satisfy.  WHERE the
    symbol stands is the composition's business -- the position is measured --
    so an off-centre symbol is accepted as long as its whole quiet zone stays
    on the canvas, and rejected the moment the zone would be borrowed from the
    page."""
    oversized = compose_art(
        tmp_path / "big.png", _ADAPTER_URL, fraction=0.95, decorate=False
    )
    undersized = compose_art(
        tmp_path / "small.png", _ADAPTER_URL, fraction=0.40, decorate=False
    )
    adrift = compose_art(
        tmp_path / "adrift.png", _ADAPTER_URL, fraction=0.60,
        decorate=False, center_offset=90,
    )
    # fraction 0.60 of 1024px leaves a 205px margin; +170px pushes the far
    # edge to 35px, under the ~66px four-module quiet zone.
    over_edge = compose_art(
        tmp_path / "over-edge.png", _ADAPTER_URL, fraction=0.60,
        decorate=False, center_offset=170,
    )

    assert any("spans" in failure for failure in review_source_code_art(oversized, _ADAPTER_URL))
    assert any("spans" in failure for failure in review_source_code_art(undersized, _ADAPTER_URL))
    assert review_source_code_art(adrift, _ADAPTER_URL) == []
    assert any(
        "quiet zone runs off the canvas" in failure
        for failure in review_source_code_art(over_edge, _ADAPTER_URL)
    )


def test_a_non_square_or_unreadable_file_is_a_named_refusal(tmp_path: Path):
    landscape = tmp_path / "landscape.png"
    Image.new("RGB", (1200, 900), "#F1EADB").save(landscape)
    with pytest.raises(ValidationError, match="must be square"):
        measure_source_code_art(landscape)

    hollow = tmp_path / "hollow.png"
    hollow.write_bytes(b"not a png")
    with pytest.raises(ValidationError, match="cannot be decoded"):
        measure_source_code_art(hollow)

    with pytest.raises(ValidationError, match="cannot be read"):
        measure_source_code_art(tmp_path / "absent.png")


# ---------------------------------------------------------------------------
# The authoring command, with the generator stubbed out.
# ---------------------------------------------------------------------------


def test_the_command_saves_accepted_art_and_reports_the_manifest_lines(tmp_path: Path):
    make_project(tmp_path)
    runner = _stub_runner(_FIXTURE_URL)

    report = Magazine(tmp_path).source_art("issue-001", runner=runner)

    destination = tmp_path / "editions" / "issue-001" / "art" / "source-codes" / "article.png"
    assert destination.is_file()
    assert review_source_code_art(destination, _FIXTURE_URL) == []
    assert any("accepted attempt 1" in line for line in report)
    # The command names the declaration but never edits authored space itself.
    assert any(
        "source_code_art_path: editions/issue-001/art/source-codes/article.png" in line
        for line in report
    )
    manifest = yaml.safe_load(
        (tmp_path / "editions" / "issue-001" / "edition.yaml").read_text(encoding="utf-8")
    )
    assert "source_code_art_path" not in manifest["articles"][0]
    # The invocation shape is the codex CLI's: prompt on stdin, image by -i.
    command, cwd = runner.calls[0]
    assert command[:2] == ["codex", "exec"]
    assert command[-3:] == ["-i", "qr.png", "-"]
    assert "gpt-5.5" in command
    assert (cwd / "prompt.txt").is_file() and (cwd / "qr.png").is_file()
    prompt = (cwd / "prompt.txt").read_text(encoding="utf-8")
    for ink in ("#F1EADB", "#11131A", "#5332C8", "#FF5A1F"):
        assert ink in prompt
    assert _FIXTURE_URL in prompt


def test_rejected_candidates_are_retried_and_exhaustion_leaves_no_art(tmp_path: Path):
    make_project(tmp_path)
    runner = _stub_runner("https://example.test/never-the-right-url")

    report = Magazine(tmp_path).source_art("issue-001", runner=runner, attempts=2)

    assert len(runner.calls) == 2
    destination = tmp_path / "editions" / "issue-001" / "art" / "source-codes" / "article.png"
    assert not destination.exists()
    line = next(line for line in report if line.startswith("article:"))
    assert "no candidate passed the acceptance gate in 2 attempt(s)" in line
    assert "keeps the plain vector code" in line
    assert "canonical URL" in line


def test_a_generator_that_produces_nothing_is_reported_not_raised(tmp_path: Path):
    make_project(tmp_path)

    def barren(command: list[str], cwd: Path) -> None:
        return None

    report = Magazine(tmp_path).source_art("issue-001", runner=barren, attempts=1)

    assert any("no PNG" in line for line in report)


def test_existing_accepted_art_is_kept_unless_regenerate_is_asked(tmp_path: Path):
    make_project(tmp_path)
    destination = tmp_path / "editions" / "issue-001" / "art" / "source-codes" / "article.png"
    destination.parent.mkdir(parents=True)
    compose_art(destination, _FIXTURE_URL)
    first_bytes = destination.read_bytes()
    runner = _stub_runner(_FIXTURE_URL, fraction=0.70)

    report = Magazine(tmp_path).source_art("issue-001", runner=runner)
    assert runner.calls == []
    assert any("already accepted" in line for line in report)
    assert destination.read_bytes() == first_bytes

    Magazine(tmp_path).source_art("issue-001", runner=runner, regenerate=True)
    assert runner.calls
    assert destination.read_bytes() != first_bytes


def test_the_command_scopes_to_named_articles_and_refuses_unknown_ones(tmp_path: Path):
    make_project(tmp_path)
    runner = _stub_runner(_FIXTURE_URL)

    with pytest.raises(ValidationError, match="no article missing-article"):
        Magazine(tmp_path).source_art("issue-001", articles=["missing-article"], runner=runner)
    assert runner.calls == []

    report = Magazine(tmp_path).source_art("issue-001", articles=["article"], runner=runner)
    assert any("accepted" in line for line in report)


def test_a_missing_codex_cli_is_an_actionable_refusal_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    make_project(tmp_path)
    monkeypatch.setattr(source_art.shutil, "which", lambda _name: None)

    with pytest.raises(DependencyError, match="codex.*CLI"):
        Magazine(tmp_path).source_art("issue-001")


def test_the_cli_parses_the_source_art_command_and_its_flags():
    arguments = parser().parse_args(
        [
            "source-art", "issue-003",
            "--article", "first", "--article", "second",
            "--regenerate", "--model", "gpt-6", "--attempts", "5",
        ]
    )

    assert arguments.command == "source-art"
    assert arguments.edition_id == "issue-003"
    assert arguments.article == ["first", "second"]
    assert arguments.regenerate is True
    assert arguments.model == "gpt-6"
    assert arguments.attempts == 5

    defaults = parser().parse_args(["source-art", "issue-003"])
    assert defaults.article == []
    assert defaults.regenerate is False
    assert defaults.model is None
    assert defaults.attempts is None


# ---------------------------------------------------------------------------
# The manifest declaration.
# ---------------------------------------------------------------------------


def _declare_art(root: Path, path: Path | str) -> None:
    manifest_path = root / "editions" / "issue-001" / "edition.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["articles"][0]["source_code_art_path"] = (
        path.relative_to(root).as_posix() if isinstance(path, Path) else path
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def test_validate_resolves_optional_source_code_art(tmp_path: Path):
    make_project(tmp_path)
    art = tmp_path / "editions" / "issue-001" / "art" / "code-art.png"
    compose_art(art, _FIXTURE_URL)
    _declare_art(tmp_path, art)

    edition = Magazine(tmp_path).validate("issue-001")

    assert edition.articles[0].source_code_art == art.resolve()


def test_validate_rejects_missing_escaping_and_non_png_source_code_art(tmp_path: Path):
    make_project(tmp_path)

    _declare_art(tmp_path, "editions/issue-001/art/absent.png")
    with pytest.raises(ValidationError, match="does not exist"):
        Magazine(tmp_path).validate("issue-001")

    _declare_art(tmp_path, "../outside.png")
    with pytest.raises(ValidationError, match="escapes project root"):
        Magazine(tmp_path).validate("issue-001")

    stray = tmp_path / "editions" / "issue-001" / "art" / "code-art.jpg"
    Image.new("RGB", (1024, 1024), "#F1EADB").save(stray)
    _declare_art(tmp_path, stray)
    with pytest.raises(ValidationError, match="must name a PNG"):
        Magazine(tmp_path).validate("issue-001")


def test_declared_artwork_joins_the_copy_hash_and_the_translation_reuses_the_file(
    tmp_path: Path,
):
    """The artwork is copy the translation renders, so declaring it stales the
    pin; and the Spanish overlay inherits the same file with no declaration of
    its own, because the code is provenance and the URL is language-free."""
    make_project(tmp_path)
    add_spanish_translation(tmp_path)
    before = _edition_copy_sha256(Magazine(tmp_path).validate("issue-001"))

    art = tmp_path / "editions" / "issue-001" / "art" / "code-art.png"
    compose_art(art, _FIXTURE_URL)
    _declare_art(tmp_path, art)

    with pytest.raises(ValidationError, match="stale"):
        Magazine(tmp_path).validate("issue-001")

    # Re-pin the overlay against the new copy hash, as a real translation pass
    # would; the base is loaded directly because the stale overlay blocks the
    # validating loader that add_spanish_translation leans on.
    from test_manifest import load_edition_with_records

    translation_manifest = (
        tmp_path / "editions" / "issue-001" / "translations" / "es" / "edition.yaml"
    )
    pinned = yaml.safe_load(translation_manifest.read_text(encoding="utf-8"))
    pinned["base_copy_sha256"] = _edition_copy_sha256(load_edition_with_records(tmp_path))
    translation_manifest.write_text(
        yaml.safe_dump(pinned, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    editions = Magazine(tmp_path)._validate_languages("issue-001")
    assert _edition_copy_sha256(editions["en"]) != before
    assert editions["es"].articles[0].source_code_art == art.resolve()
    translated_row = editions["es"].raw["articles"][0]
    assert translated_row["source_code_art_path"] == art.relative_to(tmp_path).as_posix()


# ---------------------------------------------------------------------------
# The build: artwork in the tail slot, the plain code everywhere else, and the
# same decode gate over the finished page.
# ---------------------------------------------------------------------------


def _art_article(tmp_path: Path, **kwargs) -> SimpleNamespace:
    art = compose_art(tmp_path / "code-art.png", _ADAPTER_URL, **kwargs)
    return SimpleNamespace(
        id="article", source_url=_ADAPTER_URL, tail_art=None, source_code_art=art
    )


def test_the_tail_slot_wears_the_artwork_and_the_foot_slot_never_does(tmp_path: Path):
    article = _art_article(tmp_path)

    dressed = adapter._measured_source_code(article, 300.0)
    footed = adapter._measured_source_code(article, 40.0)

    assert dressed.slot == "tail" and dressed.art == article.source_code_art
    # The square grows so the symbol does not shrink: the symbol prints at the
    # plain element's own side, and the composition takes the difference.
    plain = dressed.modules * dressed.module
    assert dressed.side == pytest.approx(plain / measure_source_code_art(article.source_code_art).fraction, rel=1e-6)
    assert dressed.side <= adapter._tail_code_room(300.0)
    # Flush is the element: the canvas is inked to its edges, so it stands on
    # the measure's origin where the plain square hangs its quiet zone outside.
    assert dressed.left == adapter._CODE_MEASURE_LEFT_POINTS
    # The label's edges come from the measured footprint, inside the box.
    assert dressed.left < dressed.symbol_left < dressed.symbol_right < dressed.left + dressed.side
    assert dressed.top - dressed.side < dressed.symbol_bottom < dressed.top
    # The position gate's demand -- the symbol spans at least half the box --
    # is guaranteed by the measured contract, not by luck.
    assert dressed.symbol_right - dressed.symbol_left >= dressed.side / 2

    assert footed.slot == "foot" and footed.art is None


def test_an_article_that_ends_very_high_still_gives_the_artwork_up_for_the_foot(
    tmp_path: Path,
):
    """The white ceiling is judged under the element that will actually print:
    the artwork absorbs more of the page than the bare square, and past the
    ceiling even the artwork reads as a poster over silence."""
    article = _art_article(tmp_path)

    code = adapter._measured_source_code(article, 500.0)

    assert code.slot == "foot" and code.art is None


def test_declared_artwork_that_fails_its_own_contract_refuses_the_build(tmp_path: Path):
    wrong_payload = SimpleNamespace(
        id="article", source_url=_ADAPTER_URL, tail_art=None,
        source_code_art=compose_art(tmp_path / "wrong.png", "https://example.test/else"),
    )
    with pytest.raises(ValidationError, match="not the article's canonical URL"):
        adapter._measured_source_code(wrong_payload, 300.0)

    low_res = _art_article(tmp_path, pixels=512)
    with pytest.raises(ValidationError, match="ppi"):
        adapter._measured_source_code(low_res, 300.0)

    off_contract = SimpleNamespace(
        id="article", source_url=_ADAPTER_URL, tail_art=None,
        source_code_art=compose_art(
            tmp_path / "sticker.png", _ADAPTER_URL, fraction=0.40, decorate=False
        ),
    )
    with pytest.raises(ValidationError, match="outside the"):
        adapter._measured_source_code(off_contract, 300.0)


def test_the_artwork_travels_as_the_committed_bytes_and_the_label_still_stands(
    tmp_path: Path,
):
    article = _art_article(tmp_path)
    code = adapter._measured_source_code(article, 300.0)

    source = adapter._source_code_source(code)
    assert source == "data:image/png;base64," + base64.b64encode(
        article.source_code_art.read_bytes()
    ).decode("ascii")

    tree = _parse_article_fragment("<p>Body.</p>", source_label="Source / 01")
    _apply_source_codes(tree, {"article": code})
    image = next(element for element in tree.iter("img") if element.get("class") == "source-code")
    assert image.get("data-source-code") == "tail"
    assert image.get("src") == source
    assert f"width: {code.side:.4f}pt" in image.get("style")
    label = next(element for element in tree.iter("p") if element.get("class") == "source-label")
    assert f"left: {code.symbol_right + adapter._CODE_LABEL_GAP_POINTS:.4f}pt" in label.get("style")


def test_a_rendered_reader_carries_the_artwork_and_its_code_reads_back(tmp_path: Path):
    """The whole adapter, end to end: the artwork is embedded untreated, the
    final gate decodes it off the rasterised page, and an article without art
    on the same build keeps the plain vector code."""
    import pypdf

    manuscript = (
        _FONT_SAFE_MANUSCRIPT + "\n"
        + "\n\n".join(_FILLER_PARAGRAPH for _ in range(9)) + "\n"
    )
    edition = _raster_edition(tmp_path, manuscript=manuscript)
    art = compose_art(tmp_path / "code-art.png", _ADAPTER_URL)
    edition = replace(
        edition,
        articles=(replace(edition.articles[0], source_code_art=art),),
    )
    output = tmp_path / "reader.pdf"

    render_a5_weasyprint(edition, output)

    with Image.open(art) as image:
        art_size = image.size
    reader = pypdf.PdfReader(str(output))
    embedded = set()
    for page in reader.pages:
        xobjects = (page.get("/Resources") or {}).get("/XObject") or {}
        if hasattr(xobjects, "get_object"):
            xobjects = xobjects.get_object()
        for value in xobjects.values():
            obj = value.get_object()
            if obj.get("/Subtype") == "/Image":
                embedded.add((int(obj["/Width"]), int(obj["/Height"])))
    assert art_size in embedded

    sys.path.insert(0, str(Path(__file__).parent))
    from test_weasyprint_adapter import _decoded

    assert list(_decoded(output).values()) == [[_ADAPTER_URL]]


def test_a_full_build_records_the_artwork_s_hash_beside_its_other_inputs(tmp_path: Path):
    make_project(tmp_path)
    paragraphs = [_FILLER_PARAGRAPH.strip() for _ in range(9)]
    (tmp_path / "editions" / "issue-001" / "articles" / "article.md").write_text(
        "The original article.\n\n" + "\n\n".join(paragraphs) + "\n", encoding="utf-8"
    )
    ledger = {
        "schema_version": 1,
        "source_ids": ["source-one"],
        "paragraphs": [
            {"status": "retained", "source": "The original article.", "edited": "The original article."},
            *(
                {"status": "retained", "source": paragraph, "edited": paragraph}
                for paragraph in paragraphs
            ),
        ],
    }
    (tmp_path / "editions" / "issue-001" / "fidelity" / "article.yaml").write_text(
        yaml.safe_dump(ledger), encoding="utf-8"
    )
    art = tmp_path / "editions" / "issue-001" / "art" / "source-codes" / "article.png"
    art.parent.mkdir(parents=True)
    compose_art(art, _FIXTURE_URL)
    _declare_art(tmp_path, art)

    result = Magazine(tmp_path).build("issue-001")

    manifest = json.loads(
        (result.output_dir / "edition-manifest.json").read_text(encoding="utf-8")
    )
    recorded = manifest["inputs"]["articles"][0]["source_code_art"]
    assert recorded["path"] == art.relative_to(tmp_path).as_posix()
    import hashlib

    assert recorded["sha256"] == hashlib.sha256(art.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# The quiet zone, the ground, and the label band: the checks that make the
# artwork printable furniture rather than a decodable sticker.
# ---------------------------------------------------------------------------


def test_the_gate_rejects_a_shape_parked_in_the_quiet_zone(tmp_path: Path):
    """A violet bar one module below the symbol's ink decodes in this room and
    fails on a phone held at an angle over the creased print this magazine is."""
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL, decorate=False)
    assert review_source_code_art(art, _ADAPTER_URL) == []
    measurement = measure_source_code_art(art)
    left, _top, right, bottom = (edge * 1024 for edge in measurement.box)
    module = (right - left) / measurement.modules
    with Image.open(art) as image:
        canvas = image.convert("RGB")
    ImageDraw.Draw(canvas).rectangle(
        [int(left) + 20, int(bottom + module), int(right) - 20, int(bottom + 2 * module)],
        fill="#5332C8",
    )
    canvas.save(art)

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("quiet zone" in failure for failure in failures)


def test_the_gate_refuses_a_warm_paper_ground_that_reads_as_a_sticker(tmp_path: Path):
    """The canvas prints on the white sheet; a warm-paper ground sits on it as
    a visibly tinted pasted rectangle.  The warm paper survives as a shape
    colour only."""
    art = compose_art(
        tmp_path / "art.png", _ADAPTER_URL, ground="#F1EADB", decorate=False
    )

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("unprinted" in failure and "sheet" in failure for failure in failures)
    assert any("warm paper" in failure for failure in failures)


def test_a_white_ground_with_edge_reaching_shapes_still_passes_the_ground_gate(
    tmp_path: Path,
):
    """Shapes may reach the canvas edges -- the gate demands that the sheet
    show through the border band, not that the border be empty."""
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL)

    assert review_source_code_art(art, _ADAPTER_URL) == []


def test_the_gate_keeps_the_label_band_clear_of_artwork_ink(tmp_path: Path):
    """The build sets SOURCE / nn right of the symbol on its bottom edge,
    inside the canvas; artwork ink there would put type over ink."""
    art = compose_art(tmp_path / "art.png", _ADAPTER_URL, decorate=False)
    assert review_source_code_art(art, _ADAPTER_URL) == []
    with Image.open(art) as image:
        canvas = image.convert("RGB")
    measurement = measure_source_code_art(art)
    _left, _top, right, bottom = (int(edge * 1024) for edge in measurement.box)
    # Clear of the quiet ring (72px here) but square in the label's own band.
    ImageDraw.Draw(canvas).rectangle(
        [right + 95, bottom - 85, right + 165, bottom - 15], fill="#11131A"
    )
    canvas.save(art)

    failures = review_source_code_art(art, _ADAPTER_URL)

    assert any("label band" in failure for failure in failures)


def test_vandalised_art_is_refused_by_the_build_that_would_print_it(tmp_path: Path):
    """The decode gate cannot catch ink-discipline damage -- a violet module or
    a dirtied quiet zone still decodes off the colour raster and only fails on
    the monochrome printer -- so the build re-runs the ink review on every plan
    pass and refuses, naming the repair."""
    violet_modules = SimpleNamespace(
        id="article", source_url=_ADAPTER_URL, tail_art=None,
        source_code_art=compose_art(
            tmp_path / "violet.png", _ADAPTER_URL, dark="#5332C8"
        ),
    )
    with pytest.raises(ValidationError, match=r"ink review.*mag source-art"):
        adapter._measured_source_code(violet_modules, 300.0)

    art = compose_art(tmp_path / "accepted.png", _ADAPTER_URL)
    assert review_source_code_art(art, _ADAPTER_URL) == []
    article = SimpleNamespace(
        id="article", source_url=_ADAPTER_URL, tail_art=None, source_code_art=art
    )
    assert adapter._measured_source_code(article, 300.0).art == art
    measurement = measure_source_code_art(art)
    left, _top, right, bottom = (edge * 1024 for edge in measurement.box)
    module = (right - left) / measurement.modules
    with Image.open(art) as image:
        canvas = image.convert("RGB")
    ImageDraw.Draw(canvas).rectangle(
        [int(left) + 20, int(bottom + module), int(right) - 20, int(bottom + 2 * module)],
        fill="#5332C8",
    )
    canvas.save(art)

    with pytest.raises(ValidationError, match=r"quiet zone.*mag source-art"):
        adapter._measured_source_code(article, 300.0)


def test_the_placed_box_and_label_follow_an_off_centre_symbol(tmp_path: Path):
    """The centring requirement is gone because nothing needed it: every edge
    the page aligns or labels against is read off the measured footprint."""
    art = compose_art(
        tmp_path / "art.png", _ADAPTER_URL, fraction=0.60,
        decorate=False, center_offset=90,
    )
    article = SimpleNamespace(
        id="article", source_url=_ADAPTER_URL, tail_art=None, source_code_art=art
    )

    code = adapter._measured_source_code(article, 300.0)

    measurement = measure_source_code_art(art)
    assert code.art == art
    assert code.symbol_left == pytest.approx(code.left + measurement.box[0] * code.side)
    assert code.symbol_right == pytest.approx(code.left + measurement.box[2] * code.side)
    assert code.symbol_bottom == pytest.approx(code.top - measurement.box[3] * code.side)
    # The position gate's demand: the symbol spans at least half the placed box.
    assert code.symbol_right - code.symbol_left >= code.side / 2


# ---------------------------------------------------------------------------
# The tight slot: the artwork must never print the symbol smaller than the
# plain code the page fitted, nor under the module floor.
# ---------------------------------------------------------------------------


def test_a_tight_tail_slot_keeps_the_plain_code_rather_than_shrink_the_symbol(
    tmp_path: Path,
):
    """The reviewer's reproduction: an 81.7pt slot, a 0.56-fraction artwork and
    a 73-character URL put the artwork's symbol at a 0.33mm module -- under the
    0.35mm floor -- and 30% smaller in ink span than the fitted plain code
    (which the tight room sets at ECC-L where the artwork carries the roomy
    reference's ECC-H).  The page keeps the plain code, which is proven to fit."""
    url = "https://example.test/library/2026/a-long-canonical-article-slug?ref=print"
    art = compose_art(tmp_path / "art.png", url, fraction=0.56)
    article = SimpleNamespace(
        id="article", source_url=url, tail_art=None, source_code_art=art
    )
    flow_bottom = 163.7  # the tightest page that still earns the tail slot

    code = adapter._measured_source_code(article, flow_bottom)

    assert code.slot == "tail" and code.art is None
    assert code.module >= adapter._CODE_MIN_MODULE_POINTS
    plain = adapter._fitted_source_code(
        "article", "tail", url,
        adapter._tail_code_room(flow_bottom),
        top=adapter._tail_code_slot(flow_bottom),
    )
    assert code == plain
    # The demotion is the slot's, not the artwork's: a roomy page still wears it.
    assert adapter._measured_source_code(article, 300.0).art == art


# ---------------------------------------------------------------------------
# The authoring command's operational fixes: fresh attempt directories, crash
# tolerance, a lazy generator, and pastable declarations.
# ---------------------------------------------------------------------------


def test_a_failed_run_does_not_poison_the_next_with_a_stale_candidate(tmp_path: Path):
    """The prompt mandates one fixed output name, so a reused attempt directory
    still holds the last rejected art.png; a run that only trusted files that
    appeared would see nothing new and report a produced image as no image."""
    make_project(tmp_path)
    bad = _stub_runner("https://example.test/never-the-right-url")
    report = Magazine(tmp_path).source_art("issue-001", runner=bad, attempts=1)
    assert any("no candidate passed" in line for line in report)

    good = _stub_runner(_FIXTURE_URL)
    report = Magazine(tmp_path).source_art("issue-001", runner=good, attempts=1)

    assert any("accepted attempt 1" in line for line in report)
    destination = (
        tmp_path / "editions" / "issue-001" / "art" / "source-codes" / "article.png"
    )
    assert destination.is_file()
    assert review_source_code_art(destination, _FIXTURE_URL) == []


def test_a_crashing_generator_costs_one_attempt_not_the_edition(tmp_path: Path):
    make_project(tmp_path)
    calls: list[Path] = []

    def flaky(command: list[str], cwd: Path) -> None:
        calls.append(cwd)
        if len(calls) == 1:
            raise source_art.GenerationError("codex did not finish within 600s")
        compose_art(cwd / "art.png", _FIXTURE_URL)

    report = Magazine(tmp_path).source_art("issue-001", runner=flaky, attempts=2)

    assert len(calls) == 2
    assert any("accepted attempt 2" in line for line in report)


def test_the_default_runner_turns_timeouts_and_bad_exits_into_failed_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(source_art.shutil, "which", lambda _name: "/stub/codex")
    runner = source_art._codex_runner()
    (tmp_path / "prompt.txt").write_text("brief", encoding="utf-8")

    def timeout(*_args, **_kwargs):
        raise source_art.subprocess.TimeoutExpired("codex", 600)

    monkeypatch.setattr(source_art.subprocess, "run", timeout)
    with pytest.raises(source_art.GenerationError, match="did not finish"):
        runner(["codex", "exec"], tmp_path)

    monkeypatch.setattr(
        source_art.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=2, stderr=b"model unavailable", stdout=b""
        ),
    )
    with pytest.raises(source_art.GenerationError, match="codex failed"):
        runner(["codex", "exec"], tmp_path)


def test_already_accepted_art_never_demands_the_codex_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The runner is built lazily: an edition whose artwork already stands
    reports without the CLI installed at all."""
    make_project(tmp_path)
    destination = (
        tmp_path / "editions" / "issue-001" / "art" / "source-codes" / "article.png"
    )
    destination.parent.mkdir(parents=True)
    compose_art(destination, _FIXTURE_URL)
    monkeypatch.setattr(source_art.shutil, "which", lambda _name: None)

    report = Magazine(tmp_path).source_art("issue-001")

    assert any("already accepted" in line for line in report)


def test_the_declaration_lines_are_pastable_yaml_for_an_article_row(tmp_path: Path):
    import textwrap

    make_project(tmp_path)

    report = Magazine(tmp_path).source_art(
        "issue-001", runner=_stub_runner(_FIXTURE_URL)
    )

    index = next(
        number for number, line in enumerate(report) if line.strip() == "# article"
    )
    snippet = textwrap.dedent("\n".join(report[index:index + 2]))
    assert yaml.safe_load(snippet) == {
        "source_code_art_path": "editions/issue-001/art/source-codes/article.png"
    }
