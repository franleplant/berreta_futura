"""The three properties every judge brief has to have, proved structurally.

Each of these was a rule that existed in prose before it existed in code, and
each of them failed in the way prose rules fail: followed literally, sideways.
``prompts/line-review.md`` was told not to open the source and was asked, in the
same file, whether the headings mirrored the source's table of contents -- so it
answered a question it could not see, confidently and wrongly.  The severity cap
was honoured exactly as written and produced the sentence "the actionable
surface is clean" over twelve broken sentence openings.

So these are tests about *construction*, not about intent:

**A source-blind lens cannot be handed a source.**  Not "is told not to look".
:class:`~magazine.produce_prompts.SourceBlindReviewInput` has no field an
extraction could occupy, its composer takes no other type, and the composed text
is scanned against the very extractions the lens was denied.

**One lens reads one piece.**  No per-piece composer can be handed two pieces,
so a call site cannot batch two articles into one judge call and re-split the
attention that seven narrow lenses exist to concentrate.

**A brief is complete on its own.**  A worker under the cooperative backend is
often a subagent with no repository, so a brief that cites a file is a brief
that cannot be answered.  The two lenses whose prompts name the house-style
corpus carry the corpus.
"""

from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

from magazine.extraction import Extraction
from magazine.produce_graph import (
    BENCH_REVIEW_KINDS,
    PIECE_JUDGE_LENSES,
)
from magazine.produce_prompts import (
    HOUSE_STYLE_PATH,
    JUDGE_PROMPTS,
    EditionReviewInput,
    EvidenceReviewInput,
    ProduceError,
    SourceBlindReviewInput,
    TeachingReviewInput,
    WorthReviewInput,
    assert_source_withheld,
    compose_edition_prompt,
    compose_evidence_prompt,
    compose_source_blind_prompt,
    compose_teaching_prompt,
    compose_worth_prompt,
    load_prompt,
)

ROOT = Path(__file__).resolve().parents[1]

# A sentence long enough that its presence in a brief is a leak rather than a
# coincidence of English, and distinctive enough that no manuscript below could
# have written it independently.
SOURCE_SENTENCE = (
    "The protocol negotiates capabilities once per session and the server "
    "advertises exactly three primitives to the client."
)

MANUSCRIPT = (
    "---\ntitle: A piece\n---\n\n"
    "## What it does\n\n"
    "A short paragraph of our own prose that does not quote the source at all.\n"
)

OTHER_MANUSCRIPT = (
    "---\ntitle: A different piece\n---\n\n"
    "## Somewhere else\n\n"
    "Sentences belonging to an entirely different article in this edition.\n"
)


def extraction(source_id: str = "a-source") -> Extraction:
    return Extraction(
        path=Path("library/sources") / source_id / "extracted.md",
        source_id=source_id,
        raw_bundle="bundle",
        method="manual",
        body=f"# The source\n\n{SOURCE_SENTENCE}\n",
        file_sha256="0" * 64,
    )


def blind_input() -> SourceBlindReviewInput:
    return SourceBlindReviewInput(
        piece_id="a-piece",
        content_mode="faithful_edit",
        byline="Someone",
        max_pages=7,
        manuscript=MANUSCRIPT,
    )


SOURCE_BLIND_KINDS = tuple(
    lens.kind for lens in PIECE_JUDGE_LENSES if lens.is_source_blind
)


class PromptTableTests(unittest.TestCase):
    def test_every_declared_lens_has_a_prompt_file_that_exists(self):
        """A lens with no prompt is dispatched and then refused mid-run.

        The graph decides what to ask for and this table decides what to ask
        it with, and the expensive moment to discover they disagree is after a
        writer round has already been paid for.  Both directions are checked:
        a lens with no prompt cannot run, and a prompt with no lens is a file
        nothing will ever load.
        """

        self.assertEqual(tuple(JUDGE_PROMPTS), BENCH_REVIEW_KINDS)
        for kind, relative in JUDGE_PROMPTS.items():
            with self.subTest(kind=kind):
                self.assertTrue(
                    (ROOT / relative).is_file(),
                    f"{kind} names {relative}, which is not on disk",
                )

    def test_the_house_style_corpus_the_briefs_embed_is_on_disk(self):
        self.assertTrue((ROOT / HOUSE_STYLE_PATH).is_file())


class SourceBlindnessTests(unittest.TestCase):
    """``mechanics``, ``shape`` and ``craft`` cannot be shown the source."""

    def test_the_blind_input_type_has_no_field_a_source_could_occupy(self):
        """The guarantee is the type, and this is the test of the type.

        A future edit that adds ``extractions`` to this dataclass to make one
        lens "a bit smarter" is the whole failure mode, and it would pass every
        behavioural test in this file, because a brief only leaks a source when
        somebody passes one.  So the field list itself is pinned.
        """

        fields = {field.name for field in dataclasses.fields(SourceBlindReviewInput)}
        self.assertEqual(
            fields,
            {"piece_id", "content_mode", "byline", "max_pages", "manuscript"},
        )
        for name in fields:
            self.assertNotIn("source", name)
            self.assertNotIn("extraction", name)
            self.assertNotIn("peer", name)

    def test_a_blind_lens_brief_carries_no_line_of_the_source(self):
        """Composed, not asserted about: the brief is built and then searched."""

        source = extraction()
        for kind in SOURCE_BLIND_KINDS:
            with self.subTest(kind=kind):
                prompt = load_prompt(ROOT, JUDGE_PROMPTS[kind])
                house_style = (
                    load_prompt(ROOT, HOUSE_STYLE_PATH).text if kind == "craft" else ""
                )
                text = compose_source_blind_prompt(
                    prompt, blind_input(), kind=kind, house_style=house_style
                )
                self.assertNotIn(SOURCE_SENTENCE, text)
                self.assertIn("A short paragraph of our own prose", text)
                # And the second line of the guarantee agrees with the first.
                assert_source_withheld(
                    text, [source], manuscript=MANUSCRIPT, label=f"{kind} lens"
                )

    def test_the_leak_guard_refuses_a_brief_that_smuggled_the_source_in(self):
        """Prove the guard can actually fail, not merely that it did not.

        A guard nobody has ever seen refuse is a guard that may be comparing two
        empty strings.  This feeds it the case it exists for -- source prose in
        the brief that the manuscript does not carry -- and requires the
        refusal to name the lens and the source.
        """

        leaked = "some brief text\n" + SOURCE_SENTENCE + "\nmore brief text"
        with self.assertRaises(ProduceError) as caught:
            assert_source_withheld(
                leaked, [extraction()], manuscript=MANUSCRIPT, label="craft lens"
            )
        message = str(caught.exception)
        self.assertIn("craft lens", message)
        self.assertIn("a-source", message)
        self.assertIn("forbidden the source", message)

    def test_a_faithful_manuscript_that_is_the_source_is_not_a_leak(self):
        """The case that makes a naive content scan unsound.

        A ``faithful_edit`` manuscript legitimately *is* the source's sentences,
        and the manuscript legitimately *is* in the brief.  A guard that flagged
        that would fire on every faithful piece every round, which is how a
        guard gets deleted.
        """

        faithful = f"---\ntitle: Faithful\n---\n\n{SOURCE_SENTENCE}\n"
        prompt = load_prompt(ROOT, JUDGE_PROMPTS["mechanics"])
        item = dataclasses.replace(blind_input(), manuscript=faithful)
        text = compose_source_blind_prompt(prompt, item, kind="mechanics")
        assert_source_withheld(
            text, [extraction()], manuscript=faithful, label="mechanics lens"
        )


class OnePiecePerCallTests(unittest.TestCase):
    """No per-piece composer can be handed two pieces."""

    def test_no_per_piece_input_type_can_hold_a_second_piece(self):
        """One ``piece_id`` and one ``manuscript``, on every per-piece type.

        The one field that carries other pieces' prose is
        ``EvidenceReviewInput.peer_manuscripts``, and it is not batching:
        ``prompts/evidence-review.md`` says the editorial's sources *are* the
        edition's article manuscripts, so for that one piece the peers are the
        extraction and there is nothing else to check it against.  It is
        allowed by name here so that a second such field cannot appear quietly.
        """

        allowed_multi = {(EvidenceReviewInput, "peer_manuscripts")}
        for cls in (
            SourceBlindReviewInput,
            WorthReviewInput,
            EvidenceReviewInput,
            TeachingReviewInput,
        ):
            with self.subTest(cls=cls.__name__):
                names = [field.name for field in dataclasses.fields(cls)]
                self.assertEqual(names.count("piece_id"), 1)
                self.assertEqual(names.count("manuscript"), 1)
                for name in names:
                    if name in ("piece_id", "manuscript", "extractions"):
                        continue
                    if (cls, name) in allowed_multi:
                        continue
                    self.assertNotIn(
                        "manuscripts",
                        name,
                        f"{cls.__name__}.{name} could carry a second piece",
                    )

    def test_a_per_piece_brief_never_carries_another_piece_s_prose(self):
        source = extraction()
        briefs = {
            "mechanics": compose_source_blind_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["mechanics"]),
                blind_input(),
                kind="mechanics",
            ),
            "worth": compose_worth_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["worth"]),
                WorthReviewInput(
                    piece_id="a-piece",
                    content_mode="faithful_edit",
                    byline="Someone",
                    title="A piece",
                    manuscript=MANUSCRIPT,
                    extractions=(source,),
                ),
            ),
            "teaching": compose_teaching_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["teaching"]),
                TeachingReviewInput(
                    piece_id="a-piece",
                    content_mode="in_a_nutshell",
                    byline="Someone",
                    manuscript=MANUSCRIPT,
                    furniture={"title": "An issue"},
                    extractions=(source,),
                ),
            ),
            "evidence": compose_evidence_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["evidence"]),
                EvidenceReviewInput(
                    piece_id="a-piece",
                    content_mode="faithful_edit",
                    byline="Someone",
                    manuscript=MANUSCRIPT,
                    extractions=(source,),
                ),
            ),
        }
        for kind, text in briefs.items():
            with self.subTest(kind=kind):
                self.assertNotIn("Sentences belonging to an entirely different", text)

    def test_the_editorial_is_the_one_piece_evidence_reads_peers_for(self):
        """And it reads them as its sources, which the brief has to say.

        The editorial declares no ``source_ids``; if the peers arrived unlabelled
        the fact-checker would read them as background and check the editorial
        against nothing.
        """

        text = compose_evidence_prompt(
            load_prompt(ROOT, JUDGE_PROMPTS["evidence"]),
            EvidenceReviewInput(
                piece_id="editorial",
                content_mode="original_editorial",
                byline="The editors",
                manuscript=MANUSCRIPT,
                peer_manuscripts=(("another-piece", OTHER_MANUSCRIPT),),
            ),
        )
        self.assertIn("This piece's sources: the edition's own articles", text)
        self.assertIn("Sentences belonging to an entirely different", text)


class SelfContainedBriefTests(unittest.TestCase):
    """Everything a worker needs arrives in the brief text."""

    def test_the_craft_brief_carries_the_house_style_corpus_in_full(self):
        """``prompts/craft-review.md`` names the corpus as an input.

        Citing the path would be fine for a judge with a checkout and useless
        for a subagent without one, and the cooperative backend's whole premise
        is that the brief is the entire contract.  So the corpus travels.
        """

        corpus = load_prompt(ROOT, HOUSE_STYLE_PATH).text
        text = compose_source_blind_prompt(
            load_prompt(ROOT, JUDGE_PROMPTS["craft"]),
            blind_input(),
            kind="craft",
            house_style=corpus,
        )
        for marker in (
            "Never use a long word where a short one will do.",
            "Banned tics",
        ):
            self.assertIn(marker, text)

    def test_the_edition_brief_carries_the_house_style_corpus_in_full(self):
        corpus = load_prompt(ROOT, HOUSE_STYLE_PATH).text
        text = compose_edition_prompt(
            load_prompt(ROOT, JUDGE_PROMPTS["edition"]),
            EditionReviewInput(
                edition_id="issue-001",
                manifest={"title": "An issue"},
                editorial=MANUSCRIPT,
                articles=(("a-piece", "faithful_edit", MANUSCRIPT),),
                house_style=corpus,
            ),
        )
        self.assertIn("Never use a long word where a short one will do.", text)

    def test_a_blind_lens_that_is_not_craft_does_not_carry_the_corpus(self):
        """Self-containment is not an excuse to send everything.

        ``mechanics`` and ``shape`` do not judge against the corpus, and the
        corpus is four hundred lines. Context a lens has no use for is the
        cost this whole redesign was supposed to spend deliberately.
        """

        for kind in ("mechanics", "shape"):
            with self.subTest(kind=kind):
                text = compose_source_blind_prompt(
                    load_prompt(ROOT, JUDGE_PROMPTS[kind]), blind_input(), kind=kind
                )
                self.assertNotIn("Banned tics", text)

    def test_every_brief_states_its_own_output_contract_and_the_disposition_rule(self):
        """A worker that omits ``disposition`` has its whole reply rejected.

        After the call has been paid for. The sentence that prevents that costs
        nothing, so every brief carries it.
        """

        source = extraction()
        briefs = [
            compose_source_blind_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["shape"]), blind_input(), kind="shape"
            ),
            compose_worth_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["worth"]),
                WorthReviewInput(
                    piece_id="a-piece",
                    content_mode="faithful_edit",
                    byline="Someone",
                    title="A piece",
                    manuscript=MANUSCRIPT,
                    extractions=(source,),
                ),
            ),
            compose_edition_prompt(
                load_prompt(ROOT, JUDGE_PROMPTS["edition"]),
                EditionReviewInput(
                    edition_id="issue-001",
                    manifest={"title": "An issue"},
                    editorial=None,
                    articles=(),
                ),
            ),
        ]
        for text in briefs:
            self.assertIn("## Output contract", text)
            self.assertIn("Every finding must carry `disposition`", text)
            self.assertIn("editor_decision", text)
            self.assertIn(
                "Never soften or drop a finding because it is the author's", text
            )

    def test_a_brief_opens_with_the_whole_prompt_file(self):
        """The rubric is in the brief, not behind a path.

        The prompt file is the rubric, and a worker that had to fetch it would
        be a worker who could be given the wrong revision of it.
        """

        prompt = load_prompt(ROOT, JUDGE_PROMPTS["mechanics"])
        text = compose_source_blind_prompt(prompt, blind_input(), kind="mechanics")
        self.assertTrue(text.startswith(prompt.text.rstrip()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
