from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from magazine import Magazine
from magazine.media_curator import verify_source_curation


def _diagram(index: int) -> str:
    return f"""
    <h2>System stage {index}</h2>
    <style>.cb-fig .stroke {{ stroke: #a93613; fill: none; }}</style>
    <svg viewBox="0 0 900 420" role="img">
      <title>System retrieval flow {index}</title>
      <desc>Sources, embeddings, search, evidence, and synthesis.</desc>
      <rect class="stroke" x="20" y="30" width="180" height="90"/>
      <rect class="stroke" x="250" y="30" width="180" height="90"/>
      <rect class="stroke" x="480" y="30" width="180" height="90"/>
      <path class="stroke" d="M200 75H250M430 75H480"/>
      <text x="40" y="80">SOURCE SEARCH PIPELINE {index}</text>
    </svg>
    """


def test_capture_automatically_curates_only_three_substantive_inline_diagrams() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        html = "<main><h1>Knowledge system</h1>" + "".join(_diagram(i) for i in range(1, 5))
        html += '<h2>Decoration</h2><svg viewBox="0 0 640 20" aria-hidden="true"><path d="M0 1H640"/></svg></main>'
        html += '<h2>Quote card</h2><svg viewBox="0 0 900 420"><text x="20" y="40">A paragraph rendered as an image adds no editorial value.</text></svg>'
        (snapshot / "capture.json").write_text(
            json.dumps({"main_html": html}), encoding="utf-8"
        )
        Image.new("RGB", (900, 9000), "white").save(snapshot / "page-full.png")

        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/knowledge-system", snapshot=snapshot,
            title="Knowledge system", author="Example Author",
        )

        review = record.media_reviews[0]
        assert review.status == "media_curated"
        assert len(review.assets) == 3
        assert all(asset.artifact_path.startswith("media/derived/") for asset in review.assets)
        source_dir = magazine.sources_dir / record.id
        plan_path = source_dir / "media" / f"{review.capture_id}.curation.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["candidate_count"] == 7
        assert len(plan["selected"]) == 3
        rejected = {row["id"]: row for row in plan["candidates"] if row["decision"] == "reject"}
        assert any("decorative_or_aria_hidden" in row["rejection_reasons"] for row in rejected.values())
        assert any("extreme_aspect_ratio_or_full_page_capture" in row["rejection_reasons"] for row in rejected.values())
        assert any("pure_text_image" in row["rejection_reasons"] for row in rejected.values())
        for asset in review.assets:
            image = Image.open(source_dir / asset.artifact_path)
            assert image.width == 1800
            assert image.getbbox() is not None
        verify_source_curation(record, magazine.sources_dir)


def test_media_index_preserves_a_legacy_decision_without_an_automatic_audit() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "source.html"
        snapshot.write_text("<main>Text only</main>", encoding="utf-8")
        magazine = Magazine(root)
        record = magazine.capture("https://example.com/text", snapshot=snapshot, title="Text")
        plan = magazine.sources_dir / record.id / "media" / f"{record.raw_captures[0]['id']}.curation.json"
        plan.unlink()
        before = record.to_dict()["media_reviews"]

        magazine.index_media()
        reloaded = next(row for row in magazine.sources_dir.glob("*/record.yaml"))

        from magazine.records import SourceRecord
        from magazine.io import load_structured

        assert SourceRecord.from_dict(load_structured(reloaded)).to_dict()["media_reviews"] == before
