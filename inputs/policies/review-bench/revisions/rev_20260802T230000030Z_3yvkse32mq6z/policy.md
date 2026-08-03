# The review bench

## What the magazine is for

There is an absurd amount of writing about AI. This magazine exists so that a
developer or an engineering manager can consume that information faster and
better than by reading the originals. Every judgment on this bench serves that
one purpose. A piece that is accurate, tidy, correctly capitalised and worthless
is a failure, and the bench must be able to say so.

## Why the old bench failed

The regenerated edition 004 passed every judge and the owner rejected it: too
long, robotic, no added value over the raw sources. Three causes sat in the
bench itself.

**One judge held seven concerns.** `line-review.md` judged structure,
transitions, sentence craft, house style, voice consistency, cadence and
explainer shape in a single pass. Attention spread over seven concerns catches
less than attention on one, which is how twelve broken sentence openings and a
subject-verb error shipped under a verdict of `approved`.

**Nothing asked whether the piece was worth reading.** Every lens on the bench
measured compliance. `mcp-in-a-nutshell` scored 5/4/5/5/5 while being a
paraphrase of its source with every method name, every JSON exchange and every
pseudo-code block removed: 1,900 source words became 1,155, and for that 40%
saving the reader lost everything they would have typed. It is not a shorter
reference, not a deeper explanation, and it has no opinion. Nothing on the bench
was allowed to notice.

**A judge was asked a question it could not see the answer to.** `line-review.md`
is forbidden the source, deliberately, and was also told to check that headings
"state ideas rather than mirroring the source's table of contents". It duly
wrote that every heading stated an idea while the piece reproduced its source's
section order exactly. It had no way to know, and it asserted the opposite.

## The design

Seven narrow lenses. Each reads for one thing, in its own vocabulary. No lens
can cap, soften or excuse another lens's finding, and no lens is asked a
question its inputs cannot answer.

| kind | file | concern | sees source | sees other pieces | scope |
| --- | --- | --- | --- | --- | --- |
| `worth` | `worth-review.md` | is this better than reading the source | yes | no | article |
| `mechanics` | `mechanics-review.md` | is the English correct as typeset | no | no | piece |
| `evidence` | `evidence-review.md` | is every claim the source's | yes | no | piece |
| `shape` | `shape-review.md` | is the piece in the right order | no | no | piece |
| `craft` | `craft-review.md` | did a person write this | no | no | piece |
| `teaching` | `teaching-review.md` | can a novice use the explainer afterwards | yes | no | explainer |
| `edition` | `edition-review.md` | do these belong between one set of covers | no | yes | edition |

"Piece" means the seven articles plus the editorial. "Article" excludes the
editorial: the editorial has no source of its own, so its worth question is
whether it says something no single article says, and that is `edition`'s
`single_source_editorial` and `thin_derivation`.

### Source visibility, and the check audit

Source-blindness is a good rule with a real cost. A judge who can see the source
starts fact-checking and stops reading for flow; a judge who cannot see it
cannot say anything about the relationship between the manuscript and the
source. Both are true, so the rule is now stated as an assignment constraint:

> Every check about the relationship between manuscript and source belongs to a
> lens that reads both. Every check answerable from the manuscript alone belongs
> to a lens that reads only the manuscript.

Applied, that moves four checks off their old homes:

- "headings mirror the source's table of contents" moved from `line` (blind) to
  `worth` (reads both), where it is the `source_shaped` check: if our section
  order is their section order, our ordering added nothing.
- "the piece stripped the identifiers a reader must type" is new, and is a
  manuscript-against-source comparison, so it is `worth`'s `stripped_utility`.
- "two pieces sound like the same writer" moved from `line` (one piece at a
  time) to `edition` (sees all of them). A per-piece lens cannot judge a
  relation between pieces.
- "the furniture over-promises against the body" is a support relation inside
  the manuscript, so it is `evidence`, which already reads both and gets it for
  no extra call.

Checks that stayed blind and are answerable blind: duplication inside a piece,
orphan referents, one running example, argument order, sentence shapes, register,
dead words, banned tics, capitalisation, grammar, typography.

### The severity cap is gone, replaced by routing

The old rule capped findings on the author's retained sentences at `minor` in
author-voiced modes. It did not merely shield defects, it certified cleanliness:
a round-3 line review approved a piece with the note that the actionable surface
was clean *because* everything remaining was uncapped-able. Twelve lowercase
openings, a subject-verb error and six identical constructions in 495 words were
inside that sentence.

Ownership is now a routing decision, never a severity ceiling. Every finding on
every lens carries:

```
disposition: fix              # the writer resolves it
disposition: editor_decision  # a human chooses the remedy
```

`editor_decision` means the sentence is the source author's own retained text in
`faithful_edit` or `faithful_synthesis`, where `docs/EDITORIAL_POLICY.md` makes
changing wording review-required. The human picks between a silent repair,
`[sic]`, leaving it, or not printing the piece. An editor's note is not on that
list: the magazine does not print editorial apparatus inside an article, and a
note is how a piece keeps its defect while appearing to answer one. The severity is
whatever the defect deserves. An `editor_decision` finding still blocks the
release until a human dispositions it, is never dropped, never softened, and
never counted as clean.

**Capitalisation and grammar are never voice.** `mechanics` has no
`editor_decision` discount at all in the sense that mattered: it files at true
severity and routes. It is also a judgment task, not a regex one. A regex cannot
tell whether a lowercase sentence opening is a typo or the writer's convention,
so the lens establishes the piece's own convention first and then reasons about
intent.

### An approval must earn itself

Judges scored compliance and called it quality. So on every lens, `notes` opens
with one sentence naming what you verified in **this** piece, not which checks
you ran. An approval you cannot warrant in that sentence is `changes_required`.
On `worth` that sentence must name concretely what the piece gives a reader that
the source does not, and "it is a clean summary" is not an answer.

Scores never reach the writer. They are advisory telemetry, and the failed
edition scored fives, so a number a writer can see is a number a writer can
optimise. The revision brief carries findings only.

## Staging

Cheap and blocking-if-failed first. A lens runs only when the stage above it
left the piece alive.

**Stage 1, admission.** `worth` and `mechanics` on every piece.
Worth is the gate because a piece that should not exist at this length makes
every downstream finding worthless: craft notes on a paragraph about to be cut
are wasted calls. Mechanics is here because it is the cheapest call on the
bench, manuscript only, and because its findings survive any later change.
- `worth: changes_required` with a `blocking` finding stops the piece. Stages 2
  and 3 do not run on it this round.
- Mechanics blocking does not stop the piece: its repairs are local and do not
  move what the other lenses read.

**Stage 2, substance.** `evidence` and `shape`, on pieces that cleared stage 1.

**Stage 3, finish.** `craft` on every piece, `teaching` on the explainer, only
where stages 1 and 2 produced no `blocking` finding. Craft runs last because
sentence work is destroyed by every structural or factual repair above it, and
because craft is the lens most sensitive to text churn: running it early buys a
re-run.

**Stage 4, the issue.** `edition`, once, only when every piece has cleared
stages 1 to 3. Its findings route to named pieces, and only those pieces
re-enter the bench.

### Re-run rule

A lens re-runs only when its own declared inputs moved. Cache key is the hash of
those inputs.

| lens | inputs |
| --- | --- |
| `mechanics`, `craft`, `shape` | manuscript bytes |
| `worth`, `evidence`, `teaching` | manuscript bytes + every declared extraction body |
| `edition` | every manuscript's bytes + the `edition.yaml` fields it reads (title, cover, contents order, modes) |

Extractions are pinned and do not move, so in practice a source-reading lens
re-runs exactly when its own manuscript is revised. An unrevised piece carries
its verdicts forward untouched. `edition` re-runs whenever any manuscript or the
running order changed, which is at most once per round.

### Call count, eight pieces

Seven articles, one of them the explainer, plus the editorial.

| stage | calls |
| --- | --- |
| 1 | 7 worth + 8 mechanics = 15 |
| 2 | 8 evidence + 8 shape = 16 |
| 3 | 8 craft + 1 teaching = 9 |
| 4 | 1 edition |
| **worst case, one round** | **41** |

The worst case is a round in which nothing blocks, because blocking is what
skips stages. A round in which four articles fail `worth` costs 41 minus
4 × (evidence + shape + craft) minus the edition call, so 28. Round 1 typically
lands between 26 and 32; the 41-call round is the last one.

Across the standard three-round cap the ceiling is 123 calls, but rounds 2 and 3
re-judge only revised pieces: a realistic full production is about 41 + 16 + 8,
roughly 65 calls. The old bench cost 18 calls a round. The increase is real and
it is spent on smaller prompts: three of the seven lenses never load an
extraction, so the expensive source-reading calls go from 9 a round to 16, and
the rest of the growth is short manuscript-only passes.

## Composing one brief from seven verdicts

Seven lenses produce seven finding sets. A writer gets one document.

**Ordering is repair order, not severity and not lens.** The brief lists
findings in the order the work should be done:

    worth -> evidence -> shape -> teaching -> craft -> mechanics

Fixing a worth or shape finding deletes and moves text that craft and mechanics
findings point at, so any other order wastes the writer's work. Within a tier,
order by `repair_from` position in the manuscript, earliest first, falling back
to `locator`. Severity prints inline on every entry; the brief opens with the
verdict and a count of blocking and major findings per lens, so nothing is
hidden by the ordering.

**Deduplication.**

- Same article, same normalised locator, same concern: merge. Keep the highest
  severity, keep the earliest-tier lens as owner, append the other lenses' notes
  as "also flagged by". Never average severities.
- Same locator, different concerns: do not merge. Print adjacent in tier order,
  higher tier first, and annotate the lower one "moot if <id> is resolved by
  deletion". Two lenses landing on one sentence for two reasons is information,
  not noise.
- Any finding whose locator sits inside a passage a higher-tier finding proposes
  to cut carries the same annotation.
- Deduplication never removes a `blocking` finding.

**Conflict.** Two lenses can give contradictory instructions: `worth` says the
section does not pay for its length, `teaching` says question four is
unanswerable without it; `evidence` says restore the qualification, `worth` says
you are already longer than your source. The composer does not resolve these. It
prints one `conflict` block naming both findings and the tension, and the writer
must satisfy both or say in the revision reply which he could not and why.

When both genuinely cannot hold, one rule decides: **no lens may be satisfied by
making the piece less true.** Precedence for truth-bearing conflicts is
`evidence` > `teaching` > `worth` > `shape` > `craft` > `mechanics`. Length is
always paid for by cutting something else, never by dropping a qualification,
which is already the cut order in `faithful-synthesis.md`. Any conflict between
two `blocking` findings, and any conflict that recurs in two consecutive rounds,
escalates to a human instead of to the writer.

**Obligations versus advice.** Three sections, labelled:

- **Must fix.** Every `blocking` and `major` finding with `disposition: fix`.
  The defect must be gone. The writer is judged on the defect, not on whether
  the reviewer's line was taken.
- **Consider.** Every `minor` finding. The writer may decline any of them in one
  line.
- **For the editor.** Every finding with `disposition: editor_decision`, at any
  severity. Not the writer's to fix, and blocking on the release until a human
  rules.

`suggestion` is advice at every severity, always, and the brief says so beside
each one: the finding is the obligation, the suggestion is one way and not the
way. Scores do not appear in the brief at all.

**Volume.** Every blocking and major finding prints. Minor findings print up to
ten per piece in tier order; the remainder are held in the record with a count,
and reappear in the next round's brief if still present. A writer who is
drowning fixes nothing.

## The verdict contract

Identical across all seven lenses, so one parser serves all.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: major             # blocking | major | minor
    article: pragmatic-leverage # article id, `editorial`, or `edition`
    locator: "Where the problem lives | factories is not a token | 1"
    repair_from: "- | software factories (almost lights out) | 1"
    category: agreement
    disposition: editor_decision
    note: |
      Block scalar, always, because it quotes sentences.
    suggestion: "Optional. Always advice, never the obligation."
scores:
  <lens-specific key>: 3
notes: |
  One sentence naming what you verified in this piece, then a short paragraph.
```

- `locator` is one string, `"<section heading> | <exact quote> | <1-based
  occurrence index>"`. Normalise curly quotes and apostrophes to straight ones on
  both sides before matching. `-` as the heading when the quote precedes the
  first one. Omit `locator` only when the finding has no single site.
- `repair_from` is a second locator on the earliest sentence at which the defect
  could be repaired, required whenever the cause sits earlier than the symptom.
- `findings: []` for a clean pass. `changes_required` needs at least one
  finding, and any `blocking` forces it.
- Scores are integers 1 to 5, advisory, and never gate a release. No finding is
  ever softened or dropped to protect one.

**Change for the wiring:** `disposition` is a new required field on every
finding, on every kind. It is what replaces the severity cap, so a parser that
drops it reintroduces the bug.

## Superseded files

| file | disposition |
| --- | --- |
| `prompts/line-review.md` | **delete.** Split into `mechanics-review.md`, `shape-review.md` and `craft-review.md`; its source-relative checks moved to `worth-review.md` and `teaching-review.md`. Kind `line` retires. |
| `prompts/learning-review.md` | **delete.** Replaced by `teaching-review.md`. Kind `learning` retires, kind `teaching` replaces it. |
| `prompts/evidence-review.md` | rewritten in place. Kind `evidence` is unchanged: the concern is the same one, narrowed, and the name is load-bearing in `src/` and in committed review records. |
| `prompts/edition-review.md` | rewritten in place. Kind `edition` unchanged, same reason. |

Writer prompts (`faithful-edit.md`, `faithful-synthesis.md`, `in-a-nutshell.md`,
`opening-editorial.md`) are untouched by this design except for their closing
"How this will be judged" sections, which now describe the wrong bench. They
belong to whoever owns the writer prompts.

## What is deliberately not a lens

**House style.** It splits cleanly and a lens holding it would be the broad
judge returning under a new name. Typography, heading form, banned characters
and missing labels are mechanical, so they are `mechanics`. Banned tics, idiom
and register are voice, so they are `craft`.

**Voice consistency.** Nothing a single-piece lens can see. It is a relation
between pieces and it lives in `edition`'s swap test.

**Length.** Length is not a concern, it is a price. A lens that counted words
against the seven-page cap is exactly what taught writers to treat a ceiling as
a target, and a deterministic limit is what produced the bloat the owner hates.
Length is judged only inside `worth`, always as a ratio against what the source
charged for the same information, never against a budget. The seven-page cap
stays where it belongs: in the renderer, as a build failure, not a judgment.

**Marcus and Priya.** Two of the three reader personas bought one lens's worth
of information for two extra calls each. Marcus's furniture-versus-body
adjudication is a support relation `evidence` already reads for free; Priya's
furniture-versus-source check is literally `evidence`'s job applied to non-body
text. Nadia survives as `teaching`, because a closed-book comprehension test is
not obtainable any other way.

**Topical correctness.** Whether MCP is really stateless is not on this bench.
The extraction is the only truth by policy, and a lens with open-web knowledge
would relitigate sourcing instead of judging the piece.

**Originality.** Faithful modes are supposed to reproduce the source. The only
version of that question worth asking is `worth`'s, and it is already asked.

**A quality score.** Rejected explicitly. The failed edition scored fives across
the bench. A rating is not a judgment, and the bench now produces findings.
