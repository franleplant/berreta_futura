from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_opening_editorial_prompt_keeps_the_house_contract() -> None:
    prompt = (ROOT / "prompts" / "opening-editorial.md").read_text(encoding="utf-8")
    normalized = " ".join(prompt.lower().split())

    assert "`docs/writing_rules.md`" in normalized
    assert "emergent narrative" in normalized
    assert "prose table of contents" in normalized
    assert "never summarize the articles one by one" in normalized
    assert "visible title" in normalized
    assert "byline" in normalized
    assert "original editor text" in normalized
    assert "one rendered a5 page" in normalized


def test_editorial_policy_and_writing_method_assign_the_same_default() -> None:
    policy = (ROOT / "docs" / "EDITORIAL_POLICY.md").read_text(encoding="utf-8")
    rules = (ROOT / "docs" / "WRITING_RULES.md").read_text(encoding="utf-8")
    normalized_policy = " ".join(policy.lower().split())
    normalized_rules = " ".join(rules.lower().split())

    assert "`docs/WRITING_RULES.md`" in policy
    # The writing method is no longer an opt-in default for two piece kinds: it
    # governs everything the magazine publishes, and a mode's prompt may only
    # add to it.  The scope sentence is pinned so a later narrowing of it has to
    # be a deliberate edit here too.
    assert (
        "it applies to everything we publish: source articles in every content "
        "mode, in-a-nutshell explainers, opening editorials, captions, and "
        "social posts."
    ) in normalized_rules
    assert "none may suspend these." in normalized_rules
    assert "must not summarize the articles one by one" in normalized_policy
    assert "prose table of contents" in normalized_policy
    assert "a human must approve" in normalized_policy

    # The rewrite replaced the paraphrased six with Orwell's own wording, each
    # its own section, because a paraphrase of a rule about paraphrase was the
    # joke the old file did not get.  The headings are pinned rather than the
    # paraphrases: `craft-review.md` and `edition-review.md` both cite this
    # corpus by name, and a rule that quietly loses its section stops being
    # citable.
    expected_rules = (
        "never use a metaphor, simile or other figure of speech which you are "
        "used to seeing in print.",
        "never use a long word where a short one will do.",
        "if it is possible to cut a word out, always cut it out.",
        "never use the passive where you can use the active.",
        "never use a foreign phrase, a scientific word or a jargon word if you "
        "can think of an everyday english equivalent.",
        "break any of these rules sooner than say anything outright barbarous.",
    )
    numerals = ("i", "ii", "iii", "iv", "v", "vi")
    for numeral, rule in zip(numerals, expected_rules):
        assert f'### {numeral}. "{rule}"' in normalized_rules
