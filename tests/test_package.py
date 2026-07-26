"""The release package's own write discipline."""

import json
from pathlib import Path

import pytest

import magazine.package as package_module
from magazine import Magazine
from test_manifest import make_project


def test_manifest_is_written_before_the_render_critic_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fresh PDFs must never sit beside a stale manifest, even mid-crash.

    ``package_release`` writes ``edition-manifest.json`` as soon as the PDFs it
    describes exist and before the render critic runs -- the critic reads
    nothing from it -- so a crash (or a critic failure) anywhere later in
    packaging cannot leave ``reader.pdf`` paired with the previous build's
    manifest.  Pinned by crashing the critic itself: the manifest must already
    be on disk describing the new reader, and no critic report may exist.
    """
    make_project(tmp_path)
    magazine = Magazine(tmp_path)

    def crash(*args, **kwargs):
        raise RuntimeError("critic crashed")

    monkeypatch.setattr(package_module, "inspect_render", crash)
    with pytest.raises(RuntimeError, match="critic crashed"):
        magazine.build("issue-001")

    destination = tmp_path / "output" / "issue-001"
    assert (destination / "reader.pdf").is_file()
    assert not (destination / "render-critic.json").exists()
    manifest = json.loads((destination / "edition-manifest.json").read_text(encoding="utf-8"))
    assert manifest["layout"]["design_direction"]
