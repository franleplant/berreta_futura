from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
import pytest

from magazine import Magazine
from magazine.capture import index_existing_captures, verify_snapshots
from magazine.errors import ValidationError


def _inventory(root: Path, record) -> Path:
    bundle = record.raw_captures[0]["id"]
    return root / "library" / "sources" / record.id / "media" / f"{bundle}.json"


def test_capture_indexes_image_hash_mime_and_dimensions() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        image_path = snapshot / "figure.png"
        Image.new("RGB", (13, 7), (80, 20, 140)).save(image_path)
        (snapshot / "page.html").write_text("<main>Evidence</main>", encoding="utf-8")

        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/evidence",
            snapshot=snapshot,
            title="Evidence",
        )
        inventory = json.loads(_inventory(root, record).read_text(encoding="utf-8"))

        assert inventory["bundle_sha256"] == record.raw_captures[0]["id"]
        assert inventory["artifact_count"] == 2
        assert inventory["image_count"] == 1
        assert inventory["images"] == [
            {
                "path": "figure.png",
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "bytes": image_path.stat().st_size,
                "mime_type": "image/png",
                "pixel_width": 13,
                "pixel_height": 7,
                "aspect_ratio": 1.857143,
                "color_mode": "RGB",
                "icc_profile_present": False,
                "has_alpha": False,
                "frame_count": 1,
                "animated": False,
            }
        ]
        assert inventory["duplicate_groups"] == []
        assert record.media_reviews[0].status == "media_rejected"
        assert record.media_reviews[0].assets == ()
        verify_snapshots(record, magazine.sources_dir)


def test_capture_writes_explicit_zero_image_inventory() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "page.html"
        snapshot.write_text("<main>Text only</main>", encoding="utf-8")

        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/text",
            snapshot=snapshot,
            title="Text",
        )
        inventory = json.loads(_inventory(root, record).read_text(encoding="utf-8"))

        assert inventory["artifact_count"] == 1
        assert inventory["image_count"] == 0
        assert inventory["images"] == []
        assert record.media_reviews[0].status == "no_media"


def test_reindex_restores_legacy_inventory_without_mutating_raw_bundle() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "page.html"
        snapshot.write_text("<main>Legacy</main>", encoding="utf-8")
        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/legacy",
            snapshot=snapshot,
            title="Legacy",
        )
        raw_manifest = (
            root / "library" / "sources" / record.id / record.raw_captures[0]["path"]
        )
        raw_before = raw_manifest.read_bytes()
        inventory_path = _inventory(root, record)
        inventory_path.unlink()

        indexed = index_existing_captures([record], magazine.sources_dir)

        assert indexed == (inventory_path.resolve(),)
        assert inventory_path.is_file()
        assert raw_manifest.read_bytes() == raw_before
        verify_snapshots(record, magazine.sources_dir)


def test_snapshot_verification_rejects_stale_media_inventory() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "page.html"
        snapshot.write_text("<main>Text only</main>", encoding="utf-8")
        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/text",
            snapshot=snapshot,
            title="Text",
        )
        path = _inventory(root, record)
        inventory = json.loads(path.read_text(encoding="utf-8"))
        inventory["image_count"] = 99
        path.write_text(json.dumps(inventory), encoding="utf-8")

        with pytest.raises(ValidationError, match="stale or changed"):
            verify_snapshots(record, magazine.sources_dir)


def test_verification_rejects_missing_local_html_image_reference() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        (snapshot / "page.html").write_text(
            '<img src="media/missing.png">', encoding="utf-8"
        )
        magazine = Magazine(root)

        with pytest.raises(ValidationError, match="missing local image references"):
            magazine.capture(
                "https://example.com/missing-image",
                snapshot=snapshot,
                title="Missing image",
            )


def test_srcset_and_remote_data_references_are_inventoried_deterministically() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "snapshot"
        (snapshot / "media").mkdir(parents=True)
        Image.new("RGB", (8, 5), "white").save(snapshot / "media" / "one.png")
        Image.new("RGB", (16, 10), "black").save(snapshot / "media" / "two.jpg")
        (snapshot / "page.html").write_text(
            "<picture>"
            '<source srcset="media/one.png 1x, media/two.jpg 2x">'
            '<img src="https://cdn.example/hero.png" '
            'srcset="data:image/png;base64,AAAA 1x">'
            "</picture>",
            encoding="utf-8",
        )
        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/references",
            snapshot=snapshot,
            title="References",
        )
        inventory = json.loads(_inventory(root, record).read_text(encoding="utf-8"))

        assert inventory["referenced_image_count"] == 4
        assert [item["resolved_path"] for item in inventory["local_references"]] == [
            "media/one.png",
            "media/two.jpg",
        ]
        assert inventory["missing_references"] == []
        assert [item["kind"] for item in inventory["unresolved_acquisition_references"]] == [
            "remote",
            "data",
        ]
        assert inventory["complete"] is False


def test_media_manifest_preserves_validated_browser_source_context() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        Image.new("RGB", (1200, 700), "white").save(snapshot / "factory.jpg")
        (snapshot / "media-manifest.json").write_text(json.dumps({
            "schema_version": 2,
            "assets": [{
                "relative_url": "factory.jpg",
                "source_url": "https://cdn.example/factory.jpg",
                "source_position": 3,
                "role": "diagram",
                "heading": "The factory",
                "title": "Closed loop",
                "description": "Intent returns as production signals.",
                "alt_text": "A closed software factory loop.",
            }],
        }), encoding="utf-8")

        magazine = Magazine(root)
        record = magazine.capture(
            "https://example.com/factory", snapshot=snapshot, title="Factory"
        )
        inventory = json.loads(_inventory(root, record).read_text(encoding="utf-8"))

        reference = inventory["local_references"][0]
        assert reference["resolved_path"] == "factory.jpg"
        assert reference["source_url"] == "https://cdn.example/factory.jpg"
        assert reference["source_position"] == 3
        assert reference["role"] == "diagram"
        assert reference["heading"] == "The factory"
        assert reference["title"] == "Closed loop"
        assert inventory["complete"] is True
