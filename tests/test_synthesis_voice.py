from __future__ import annotations

from pathlib import Path

import yaml

from magazine.fidelity import fidelity_report


ROOT = Path(__file__).resolve().parents[1]


def test_existing_faithful_syntheses_do_not_narrate_the_source_author() -> None:
    edition_path = ROOT / "editions" / "001-the-work-left-to-us" / "edition.yaml"
    edition = yaml.safe_load(edition_path.read_text(encoding="utf-8"))

    for article in edition["articles"]:
        if article.get("content_mode") != "faithful_synthesis":
            continue
        fidelity_report(
            ROOT / article["fidelity"],
            ROOT / article["manuscript"],
            source_author=article["author"],
        )


def test_faithful_synthesis_prompt_requires_source_voice() -> None:
    prompt = (ROOT / "prompts" / "faithful-synthesis.md").read_text(encoding="utf-8")

    assert "source author's" in prompt
    assert "grammatical point of view" in prompt
    assert "distancing scaffolding" in prompt
