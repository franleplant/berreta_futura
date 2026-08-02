"""Seven finding sets in, one revision brief out.

``prompts/README.md``'s section "Composing one brief from seven verdicts" is a
short list of rules, and every one of them exists because the previous bench
broke it.  So these tests are written against the rules rather than against the
implementation: ordering is repair order and not severity order, a merge keeps
the highest severity and never averages, an ``editor_decision`` finding is never
the writer's and never disappears, a volume cap counts what it holds, and no
score reaches the writer at any point.

:mod:`magazine.revision_brief` is a pure function over mappings.  There is no
fixture directory here, no edition on disk, and -- deliberately, structurally --
no way for any of this to reach a model: ``compose`` takes findings and returns
a dataclass.
"""

from __future__ import annotations

import inspect
import unittest

from magazine.produce_graph import PIECE_JUDGE_KINDS
from magazine.revision_brief import (
    MINOR_LIMIT,
    TRUTH_PRECEDENCE,
    compose,
    normalize_locator,
)


REPAIR_ORDER = ("worth", "evidence", "shape", "teaching", "craft", "mechanics")

MANUSCRIPT = """## Where the problem lives

The protocol keeps no state between calls, which is the whole trick.

## What it costs

Every tool definition is re-sent on each turn, and that is the bill.

## What to do about it

Cache the definitions and measure the difference.
"""


def finding(**overrides) -> dict:
    """One authored finding, in the verdict contract's shape.

    ``disposition`` is defaulted rather than omitted because
    ``prompts/README.md`` makes it required on every authored finding, on every
    kind: "a parser that drops it reintroduces the bug".  A fixture that left it
    out would be testing a record the bench refuses to write.
    """

    row = {
        "severity": "major",
        "article": "mcp-in-a-nutshell",
        "locator": "- | a sentence | 1",
        "category": "unspecified",
        "disposition": "fix",
        "note": "What is wrong with it.",
    }
    row.update(overrides)
    return row


def rendered(brief) -> str:
    return "\n".join(brief.render())


class RepairOrderTest(unittest.TestCase):
    """The brief is a worklist, so its order is the order of the work."""

    def test_the_tiers_are_the_lens_table_read_top_to_bottom(self) -> None:
        """The order is declared once, and this is the surface that consumes it.

        ``PIECE_JUDGE_LENSES`` is repair order by construction, and the brief
        must not keep a second copy that can drift from it.  The literal is
        spelled out beside the derived tuple on purpose: if somebody reorders
        the lens table for the *running* schedule -- mechanics is the cheapest
        call and runs in stage 1 -- this test is what says the writer's worklist
        is a different order and must not follow.
        """

        self.assertEqual(PIECE_JUDGE_KINDS, REPAIR_ORDER)

    def test_findings_arrive_in_any_order_and_leave_in_repair_order(self) -> None:
        """A writer who fixes sentences first loses that work to a later cut.

        The lenses run on two threads across four stages, so the order verdicts
        arrive in is thread scheduling.  Here they arrive backwards, and the
        brief must still walk worth -> evidence -> shape -> teaching -> craft ->
        mechanics.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                (lens, [finding(category=lens, locator=f"- | quote {lens} | 1")])
                for lens in reversed(REPAIR_ORDER)
            ],
        )

        self.assertEqual([entry.lens for entry in brief.must_fix], list(REPAIR_ORDER))

    def test_a_blocking_mechanics_finding_does_not_jump_a_minor_worth_one(
        self,
    ) -> None:
        """Repair order, explicitly not severity order.

        Severity says how bad a defect is; the tier says when fixing it is not
        wasted.  A blocking typo in a paragraph ``worth`` has just said does not
        pay for its length is still work done in the wrong order, so the brief
        prints the worth finding first and prints the severity inline instead of
        sorting by it.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "mechanics",
                    [
                        finding(
                            severity="blocking",
                            category="agreement",
                            locator="What it costs | the bill | 1",
                        )
                    ],
                ),
                (
                    "worth",
                    [
                        finding(
                            severity="major",
                            category="stripped_utility",
                            locator="Where the problem lives | the whole trick | 1",
                        )
                    ],
                ),
            ],
        )

        self.assertEqual([entry.lens for entry in brief.must_fix], ["worth", "mechanics"])
        text = rendered(brief)
        self.assertLess(text.index("stripped_utility"), text.index("agreement"))
        # Nothing is hidden by the ordering: the severity prints on the entry
        # and the headline counts it.
        self.assertIn("[blocking] agreement", text)
        self.assertIn("mechanics: 1 blocking, 0 major", text)

    def test_within_a_tier_the_order_is_where_the_repair_starts(self) -> None:
        """``repair_from``, not ``locator``, because that is where the cursor goes.

        A pilot review filed a frame contradiction at paragraph five whose cause
        was a mis-stated promise in paragraph two.  Sorting that finding by its
        symptom would send the writer to the end of the piece and then back to
        the beginning; sorting by the earliest repair point walks him forward
        once.
        """

        late_symptom_early_cause = finding(
            category="frame",
            locator="What to do about it | measure the difference | 1",
            repair_from="Where the problem lives | The protocol keeps no state | 1",
        )
        middle = finding(
            category="cadence",
            locator="What it costs | Every tool definition | 1",
        )

        brief = compose(
            "mcp-in-a-nutshell",
            [("craft", [middle, late_symptom_early_cause])],
            manuscript=MANUSCRIPT,
        )

        self.assertEqual(
            [entry.category for entry in brief.must_fix], ["frame", "cadence"]
        )

    def test_a_finding_with_no_repair_from_is_placed_by_its_locator(self) -> None:
        """The fallback, and it has to be a real one.

        ``repair_from`` is required only when the cause sits earlier than the
        symptom, so most findings do not carry it.  Those still have to be
        ordered by where they live rather than by the order the lens happened to
        file them, or the fallback would be no ordering at all.
        """

        last = finding(
            category="ending", locator="What to do about it | Cache the definitions | 1"
        )
        first = finding(
            category="opening",
            locator="Where the problem lives | The protocol keeps no state | 1",
        )
        middle = finding(
            category="order", locator="What it costs | Every tool definition | 1"
        )

        brief = compose(
            "mcp-in-a-nutshell",
            [("shape", [last, middle, first])],
            manuscript=MANUSCRIPT,
        )

        self.assertEqual(
            [entry.category for entry in brief.must_fix],
            ["opening", "order", "ending"],
        )

    def test_without_a_manuscript_the_tier_order_still_holds(self) -> None:
        """A caller with no manuscript gets filing order inside a tier, not chaos.

        Positional ordering is an improvement on filing order, not a
        precondition for composing a brief.  Losing it must cost the intra-tier
        sort and nothing else.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                ("craft", [finding(category="cadence", locator="- | b | 1")]),
                ("worth", [finding(category="source_shaped", locator="- | a | 1")]),
            ],
        )

        self.assertEqual([entry.lens for entry in brief.must_fix], ["worth", "craft"])


class DeduplicationTest(unittest.TestCase):
    """Merge the same complaint; never merge two complaints."""

    def test_one_complaint_filed_twice_merges_and_keeps_the_worst_severity(
        self,
    ) -> None:
        """A merge is a summary of two lenses agreeing, never a compromise.

        Averaging two severities would produce a severity nobody filed, and it
        would do it in the direction that hurts: a ``blocking`` folded together
        with a ``minor`` would print as ``major`` and move out of the section
        that makes it non-negotiable.  So the merged entry carries the highest
        severity of the two, exactly as filed.
        """

        locator = "What it costs | Every tool definition is re-sent | 1"
        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "worth",
                    [
                        finding(
                            severity="minor",
                            category="duplication",
                            locator=locator,
                            note="Worth saw it too.",
                        )
                    ],
                ),
                (
                    "craft",
                    [
                        finding(
                            severity="blocking",
                            category="duplication",
                            locator=locator,
                            note="Craft filed it as blocking.",
                        )
                    ],
                ),
            ],
        )

        self.assertEqual(len(brief.must_fix), 1)
        self.assertEqual(brief.consider, ())
        (entry,) = brief.must_fix
        self.assertEqual(entry.severity, "blocking")
        # Earliest tier keeps ownership: the writer is sent to the lens whose
        # repair comes first, not to whichever lens shouted loudest.
        self.assertEqual(entry.lens, "worth")
        self.assertEqual(entry.also_flagged_by, (("craft", "Craft filed it as blocking."),))
        text = rendered(brief)
        self.assertIn("also flagged by craft", text)
        self.assertIn("Craft filed it as blocking.", text)

    def test_deduplication_never_removes_a_blocking_finding(self) -> None:
        """The rule that stops a merge from being a quiet downgrade.

        Two lenses on one defect is one obligation, so a merge is right.  What
        would be wrong is the obligation getting weaker for having been found
        twice: the merged entry must still be blocking, must still sit in
        ``Must fix``, and the second lens's words must still be in the brief.
        """

        locator = "Where the problem lives | keeps no state | 1"
        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "evidence",
                    [
                        finding(
                            severity="blocking",
                            category="unsupported",
                            locator=locator,
                            note="The source says the opposite.",
                        )
                    ],
                ),
                (
                    "mechanics",
                    [
                        finding(
                            severity="minor",
                            category="unsupported",
                            locator=locator,
                            note="Mechanics noticed the same sentence.",
                        )
                    ],
                ),
            ],
        )

        (entry,) = brief.must_fix
        self.assertEqual(entry.severity, "blocking")
        self.assertEqual(entry.lens, "evidence")
        self.assertEqual(brief.consider, ())
        self.assertIn("The source says the opposite.", rendered(brief))
        self.assertIn("Mechanics noticed the same sentence.", rendered(brief))

    def test_curly_and_straight_quotes_in_one_locator_are_one_locator(self) -> None:
        """A writer's typographic quotes are not a second defect site.

        ``prompts/README.md`` requires both sides to be normalised to straight
        quotes before matching.  Without it, the lens that copied the quote out
        of the rendered page and the lens that copied it out of the manuscript
        file would file the same complaint at two locators, and the brief would
        ask for the same repair twice.
        """

        curly = "What it costs | the reader's “bill” | 1"
        straight = "What it costs | the reader's \"bill\" | 1"
        self.assertNotEqual(curly, straight)
        self.assertEqual(normalize_locator(curly), normalize_locator(straight))

        brief = compose(
            "mcp-in-a-nutshell",
            [
                ("worth", [finding(category="dead_words", locator=curly)]),
                ("craft", [finding(category="dead_words", locator=straight)]),
            ],
        )

        self.assertEqual(len(brief.must_fix), 1)
        self.assertEqual(brief.must_fix[0].also_flagged_by[0][0], "craft")

    def test_one_locator_and_two_concerns_stay_two_findings_printed_adjacent(
        self,
    ) -> None:
        """Two lenses on one sentence for two reasons is information, not noise.

        Merging them would silently retire one obligation, so the key includes
        the category.  What the brief owes the writer instead is the ordering
        and the warning: higher tier first, and the lower one annotated, because
        polishing a comma in a paragraph that is about to be cut is work done
        for nothing.
        """

        locator = "What it costs | that is the bill | 1"
        brief = compose(
            "mcp-in-a-nutshell",
            [
                ("craft", [finding(category="cadence", locator=locator)]),
                ("worth", [finding(category="length_not_earned", locator=locator)]),
            ],
        )

        self.assertEqual(
            [(entry.lens, entry.category) for entry in brief.must_fix],
            [("worth", "length_not_earned"), ("craft", "cadence")],
        )
        owner, lower = brief.must_fix
        self.assertEqual(owner.moot_if, "")
        self.assertEqual(lower.moot_if, owner.id)
        self.assertIn(
            f"moot if {owner.id} is resolved by deletion", rendered(brief)
        )

    def test_a_finding_with_no_locator_never_merges_with_another(self) -> None:
        """``locator`` is optional for a defect with no single site.

        Two such findings are two whole-piece problems, and folding them
        together on the strength of a shared empty string would retire one of
        them.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "shape",
                    [
                        finding(category="order", locator="", note="Argument order."),
                        finding(category="order", locator="", note="One running example."),
                    ],
                )
            ],
        )

        self.assertEqual(len(brief.must_fix), 2)
        self.assertEqual([entry.also_flagged_by for entry in brief.must_fix], [(), ()])


class SectionTest(unittest.TestCase):
    """Three labelled sections, and the labels are the contract."""

    def test_must_fix_is_blocking_and_major_with_disposition_fix(self) -> None:
        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "shape",
                    [
                        finding(severity="blocking", category="a", locator="- | a | 1"),
                        finding(severity="major", category="b", locator="- | b | 1"),
                        finding(severity="minor", category="c", locator="- | c | 1"),
                    ],
                )
            ],
        )

        self.assertEqual(
            [entry.severity for entry in brief.must_fix], ["blocking", "major"]
        )
        self.assertEqual([entry.severity for entry in brief.consider], ["minor"])
        self.assertEqual(brief.for_the_editor, ())
        text = rendered(brief)
        self.assertIn("### Must fix", text)
        self.assertIn("### Consider", text)
        self.assertNotIn("### For the editor", text)

    def test_a_blocking_editor_decision_lands_with_the_editor_and_never_in_must_fix(
        self,
    ) -> None:
        """The single most load-bearing routing rule on the bench.

        Severity says how bad the defect is; ``disposition`` says who is allowed
        to repair it.  The two are independent, and conflating them is exactly
        what the retired severity cap did.  A ``blocking`` defect in the source
        author's retained wording is still blocking -- and it is still not the
        writer's, because ``docs/EDITORIAL_POLICY.md`` makes changing that
        wording review-required.  Putting it in ``Must fix`` would instruct the
        writer to commit a policy breach.
        """

        editorial = finding(
            severity="blocking",
            category="agreement",
            locator="Where the problem lives | keeps no state | 1",
            disposition="editor_decision",
            note="The source author's own sentence, retained verbatim.",
        )

        brief = compose("mcp-in-a-nutshell", [("mechanics", [editorial])])

        self.assertEqual(brief.must_fix, ())
        self.assertEqual(brief.consider, ())
        self.assertEqual(len(brief.for_the_editor), 1)
        self.assertEqual(brief.for_the_editor[0].severity, "blocking")
        text = rendered(brief)
        self.assertIn("### For the editor", text)
        self.assertNotIn("### Must fix", text)
        self.assertIn("[blocking] agreement", text)

    def test_editor_decisions_are_collected_at_every_severity(self) -> None:
        """"At any severity" is the phrase, and a minor one is the risky case.

        A minor ``editor_decision`` is the finding a volume cap or a severity
        floor would swallow first, and swallowing it is how the old bench
        certified a piece clean.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "craft",
                    [
                        finding(
                            severity=severity,
                            category=severity,
                            locator=f"- | {severity} | 1",
                            disposition="editor_decision",
                        )
                        for severity in ("blocking", "major", "minor")
                    ],
                )
            ],
        )

        self.assertEqual(
            [entry.severity for entry in brief.for_the_editor],
            ["blocking", "major", "minor"],
        )
        self.assertEqual(brief.must_fix, ())
        self.assertEqual(brief.consider, ())

    def test_the_editor_section_tells_the_writer_not_to_touch_them(self) -> None:
        """Printed in the *writer's* brief, and the preamble is why.

        He can see the defect.  If the brief simply omitted it he would fix it,
        which is the policy breach; and the one remedy he might reach for
        instead -- an editor's note -- is not on the sanctioned list either,
        because the magazine does not print editorial apparatus inside an
        article.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [("craft", [finding(disposition="editor_decision")])],
        )

        text = rendered(brief)
        self.assertIn("NOT yours to fix", text)
        self.assertIn("EDITORIAL_POLICY.md", text)
        self.assertIn("editor's note", text)

    def test_a_suggestion_is_labelled_advice_and_the_finding_is_the_obligation(
        self,
    ) -> None:
        brief = compose(
            "mcp-in-a-nutshell",
            [("craft", [finding(suggestion="Try splitting the sentence.")])],
        )

        text = rendered(brief)
        self.assertIn("suggestion (advice, not the obligation)", text)
        self.assertIn("Try splitting the sentence.", text)
        self.assertIn("never on whether you took the suggested line", text)

    def test_an_empty_brief_renders_nothing_at_all(self) -> None:
        """A clean piece gets no document, not a document saying nothing."""

        brief = compose("mcp-in-a-nutshell", [(lens, []) for lens in REPAIR_ORDER])

        self.assertTrue(brief.is_empty)
        self.assertEqual(brief.render(), [])


class VolumeTest(unittest.TestCase):
    """A writer who is drowning fixes nothing -- but the cap has to be honest."""

    @staticmethod
    def _minors(count: int, **overrides) -> list[dict]:
        return [
            finding(
                severity="minor",
                category=f"tic-{index}",
                locator=f"- | minor {index} | 1",
                **overrides,
            )
            for index in range(count)
        ]

    def test_minor_findings_stop_at_the_limit_and_the_rest_are_counted(self) -> None:
        overflow = 4
        brief = compose(
            "mcp-in-a-nutshell",
            [("craft", self._minors(MINOR_LIMIT + overflow))],
        )

        self.assertEqual(MINOR_LIMIT, 10)
        self.assertEqual(len(brief.consider), MINOR_LIMIT)
        self.assertEqual(brief.held_minor, overflow)
        text = rendered(brief)
        self.assertIn(f"{overflow} further minor finding(s) are held", text)
        self.assertIn("next round's brief", text)

    def test_the_held_minors_are_the_ones_latest_in_repair_order(self) -> None:
        """Held, not chosen at random: the cap keeps the earliest work.

        Tier order is repair order, so the ten that print are the ten the writer
        should do first, and the held ones return next round if they survive the
        repairs above them -- which some of them will not.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                ("worth", self._minors(MINOR_LIMIT)),
                (
                    "mechanics",
                    [
                        finding(
                            severity="minor",
                            category="typography",
                            locator="- | held | 1",
                        )
                    ],
                ),
            ],
        )

        self.assertEqual({entry.lens for entry in brief.consider}, {"worth"})
        self.assertEqual(brief.held_minor, 1)
        self.assertNotIn("typography", rendered(brief))

    def test_blocking_and_major_findings_are_never_capped(self) -> None:
        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "evidence",
                    [
                        finding(
                            severity="blocking" if index % 2 else "major",
                            category=f"claim-{index}",
                            locator=f"- | claim {index} | 1",
                        )
                        for index in range(MINOR_LIMIT + 5)
                    ],
                )
            ],
        )

        self.assertEqual(len(brief.must_fix), MINOR_LIMIT + 5)
        self.assertEqual(brief.held_minor, 0)

    def test_editor_decisions_are_never_capped_at_any_severity(self) -> None:
        """The cap is a mercy to a writer; these are not addressed to him.

        Holding one back would be the "counted as clean" ``prompts/README.md``
        forbids, and it would do it to the findings that block the release.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [("craft", self._minors(MINOR_LIMIT + 6, disposition="editor_decision"))],
        )

        self.assertEqual(len(brief.for_the_editor), MINOR_LIMIT + 6)
        self.assertEqual(brief.held_minor, 0)
        self.assertEqual(brief.consider, ())

    def test_a_held_minor_does_not_consume_the_cap_from_an_editor_decision(
        self,
    ) -> None:
        """The two counts are independent, and the interaction is easy to get wrong.

        ``editor_decision`` findings are routed out before the cap is applied,
        so ten of them must not push ten ordinary minor findings into the held
        pile.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                ("craft", self._minors(MINOR_LIMIT, disposition="editor_decision")),
                (
                    "mechanics",
                    [
                        finding(
                            severity="minor",
                            category="typography",
                            locator="- | straight quote | 1",
                        )
                    ],
                ),
            ],
        )

        self.assertEqual(len(brief.for_the_editor), MINOR_LIMIT)
        self.assertEqual(len(brief.consider), 1)
        self.assertEqual(brief.held_minor, 0)


class ScoresTest(unittest.TestCase):
    """The bench that failed scored fives.  A writer never sees a number."""

    def test_compose_has_no_parameter_that_could_carry_a_score(self) -> None:
        """Structural, not editorial: there is nowhere to put one.

        ``prompts/README.md`` says scores "do not appear in the brief at all".
        A rule enforced by remembering not to print something is a rule that
        lasts until the next person adds a debug line, so the composer's
        signature is the enforcement.
        """

        parameters = inspect.signature(compose).parameters
        self.assertEqual(list(parameters), ["piece_id", "findings_by_lens", "manuscript"])
        self.assertNotIn("scores", parameters)

    def test_a_score_smuggled_onto_a_finding_never_reaches_the_rendered_text(
        self,
    ) -> None:
        """The realistic leak: a judge's whole verdict block copied onto a row.

        The entry renderer reads the keys it prints rather than printing the
        keys it is given, which is what makes this safe.  Asserting it on the
        rendered string is the only assertion that would survive somebody
        "helpfully" adding an unknown-key passthrough.
        """

        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "craft",
                    [
                        finding(
                            note="One construction carries a quarter of the piece.",
                            scores={"voice": 5, "economy": 4},
                            score=5,
                        )
                    ],
                ),
                (
                    "worth",
                    [
                        finding(
                            category="value_over_source",
                            locator="- | the whole trick | 1",
                            note="Nothing here the source does not already give.",
                            scores={"value_over_source": 1},
                        )
                    ],
                ),
            ],
        )

        text = rendered(brief)
        self.assertIn("One construction carries a quarter of the piece.", text)
        for forbidden in ("scores", "voice", "economy", "5", "score:"):
            self.assertNotIn(forbidden, text)


class ConflictTest(unittest.TestCase):
    """Contradictions are named, never resolved, and never by this module."""

    @staticmethod
    def _clash(*, wants_less="worth", wants_more="teaching", severity="major"):
        heading = "What it costs"
        return compose(
            "mcp-in-a-nutshell",
            [
                (
                    wants_more,
                    [
                        finding(
                            severity=severity,
                            category="unanswerable",
                            locator=f"{heading} | question four | 1",
                            note="Question four cannot be answered without it.",
                        )
                    ],
                ),
                (
                    wants_less,
                    [
                        finding(
                            severity=severity,
                            category="length_not_earned",
                            locator=f"{heading} | this whole section | 1",
                            note="The section does not pay for its length.",
                        )
                    ],
                ),
            ],
        )

    def test_a_cutting_lens_and_a_wanting_lens_on_one_heading_raise_a_conflict(
        self,
    ) -> None:
        """``prompts/README.md``'s own first example, structurally detected.

        The signature is a lens that can only be satisfied by *less* text and a
        lens that can only be satisfied by *more*, landing on the same passage.
        It is a heuristic and it is offered as one -- a conflict block asks the
        writer to look, it does not assert that two findings are incompatible.
        """

        brief = self._clash()

        self.assertEqual(len(brief.conflicts), 1)
        (conflict,) = brief.conflicts
        self.assertEqual({conflict.first.lens, conflict.second.lens}, {"worth", "teaching"})
        self.assertIn("### Conflicts between lenses", rendered(brief))
        # The block itself names both findings by id and by lens, so the writer
        # can find each one in the list above rather than guessing.
        block = "\n".join(conflict.render())
        self.assertIn(conflict.first.id, block)
        self.assertIn(conflict.second.id, block)
        self.assertIn("worth", block)
        self.assertIn("teaching", block)
        self.assertIn("length_not_earned", block)
        self.assertIn("unanswerable", block)

    def test_the_conflict_block_refuses_to_resolve_and_prints_the_precedence(
        self,
    ) -> None:
        """The composer states the deciding rule; it does not apply it.

        Applying it would mean dropping somebody's finding on a guess about
        which prose contradicts which.  Printing it hands the writer the one
        rule that settles a genuine deadlock -- no lens may be satisfied by
        making the piece less true -- and leaves the judgment where it belongs.
        """

        brief = self._clash()
        text = rendered(brief)

        # Truth precedence is *not* repair order: evidence and teaching rise
        # above worth, because length is paid for by cutting something else and
        # never by dropping a qualification.
        self.assertEqual(
            TRUTH_PRECEDENCE,
            ("evidence", "teaching", "worth", "shape", "craft", "mechanics"),
        )
        self.assertNotEqual(TRUTH_PRECEDENCE, REPAIR_ORDER)
        self.assertIn(" > ".join(TRUTH_PRECEDENCE), text)
        self.assertIn("Nobody has resolved this for you", text)
        self.assertIn("Satisfy both", text)
        self.assertIn(
            "Length is paid for by cutting something else, never by dropping a "
            "qualification",
            text,
        )
        # Neither finding was dropped, softened or reordered out of the way.
        self.assertEqual(len(brief.must_fix), 2)

    def test_two_blocking_findings_in_conflict_escalate_to_a_human(self) -> None:
        """A writer cannot be asked to reconcile two refusals.

        Each blocking finding alone forces ``changes_required``, so giving
        ground on either simply re-fails the piece.  ``prompts/README.md`` sends
        that case to a human, and so does the block.
        """

        brief = self._clash(severity="blocking")

        (conflict,) = brief.conflicts
        self.assertTrue(conflict.escalates)
        self.assertIn("a human's to settle, not yours", rendered(brief))

    def test_a_conflict_short_of_two_blockings_stays_with_the_writer(self) -> None:
        """Escalation is for a deadlock, not for every disagreement.

        Sending every conflict to a human would put the owner back in the loop
        the pipeline exists to take him out of.
        """

        brief = self._clash(severity="major")

        (conflict,) = brief.conflicts
        self.assertFalse(conflict.escalates)
        self.assertNotIn("a human's to settle", rendered(brief))

    def test_two_lenses_pulling_the_same_way_are_not_a_conflict(self) -> None:
        """``worth`` and ``shape`` both want less; agreeing is not a tension.

        A conflict block the writer cannot act on is noise, and noise in a
        section this loud teaches him to skip it.
        """

        brief = self._clash(wants_less="worth", wants_more="shape")

        self.assertEqual(brief.conflicts, ())

    def test_findings_under_different_headings_are_not_a_conflict(self) -> None:
        """The passage is the whole of the claim: same heading or no tension."""

        brief = compose(
            "mcp-in-a-nutshell",
            [
                (
                    "teaching",
                    [
                        finding(
                            category="unanswerable",
                            locator="What it costs | question four | 1",
                        )
                    ],
                ),
                (
                    "worth",
                    [
                        finding(
                            category="length_not_earned",
                            locator="What to do about it | this section | 1",
                        )
                    ],
                ),
            ],
        )

        self.assertEqual(brief.conflicts, ())


if __name__ == "__main__":
    unittest.main()
