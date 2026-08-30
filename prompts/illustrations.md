# Illustration process

Every edition carries four kinds of generated artwork. All of them are
author-time creative assets: generation happens only when the editor invokes
`mag art`, never inside `mag produce` or `mag render`. Text is cheap and
rewritten freely; images are expensive and reused. Once an asset is approved
it persists in `edition.yaml` across every subsequent rewrite, and nothing in
the pipeline may regenerate or replace it without an explicit new `mag art`
round and an explicit new selection.

## The four slots

- **Cover** — one per edition, derived from a one-sentence reading of the
  whole edition. Governed entirely by `prompts/cover-art-candidates.md`
  (three branches, full rounds, square ≥1000 px, no typography). This
  document adds nothing to the cover rules; briefs for the cover restate
  that document's constraints.
- **Article openers** — exactly one per article, placed at the article's
  start. Each opener illustrates its own article's core proposition, in the
  edition's art direction. The opener frame is landscape, 348 x 203 pt (1.71:1),
  filled edge to edge, so compose for that shape with the essential subject
  and every head well inside it, legible at A5.
- **Article tails** — exactly one per article, a wide single vignette drawn
  in the whitespace at the end of an article when the final page has room.
  Whether a tail *prints* is the typesetter's call at render time; whether a
  tail *exists* is not optional. Every article must have an approved tail on
  file, because rewrites move the page breaks: a manuscript that today ends
  flush can tomorrow end on a 70 %-blank page, and the fill must already be
  approved and waiting. Essential action stays inside the safe horizontal
  crop. An article that declares a key-ideas closing box does not print a
  tail, but still keeps one approved for the rewrite that drops the box.
- **Closing plates** — full-page titled plates that fill the blank pages at
  the end of the edition (the booklet signature rarely lands exactly).
  Maintain an approved pool of at least three; the render takes however many
  the final page count demands. Genuinely vertical, poster-weight subjects
  belong here.

Curated source figures (screenshots and diagrams captured with a source) are
a separate, non-generated pipeline and are out of scope here.

## Art direction

Reusable art directions live in `art-directions/<name>.yaml` with their
reference images beside them in `art-directions/references/`. An edition
never invents a style from nothing in a prompt: it either adopts a library
direction or evolves one, and records the result — direction plus per-asset
records — in the file named by `edition.yaml`'s `art_direction_path`
(conventionally `editions/<id>/art/illustrations.yaml`, schema in
`schemas/illustrations.schema.json`).

An evolved direction states what changed and why (edition 004 evolved
`playful-science-vignettes` into a recurring single boy-and-robot cast for
continuity across seven openers). When an evolution proves durable, promote
it back into `art-directions/` as a new named direction.

Interior illustrations (openers, tails, plates) all share the edition's one
art direction. The cover follows its own three-branch grammar and only
borrows the direction when the `art_directed` branch chooses to.

## Recurring cast

A direction may define recurring characters in a `direction.cast` list
(each entry: `name`, `prompt`). The cast prompts are canon — written for
the image generator, pinning every attribute that must not vary, including
what the character is *not*. `mag art` appends them verbatim to every
interior generation prompt, and to cover prompts that name a cast member.
Briefs therefore never restate a cast member's appearance: they name the
character and describe only pose, action, expression, props, and setting.
Continuity lives in the one canonical text, never in a paraphrase.

A cast entry may also carry a `reference` image path — the character's
canonical sheet. `mag art` expands the gen-cmd's `{ref}` placeholder to the
references of the briefs that carry the cast (and to nothing elsewhere), and
`tools/imagegen` attaches them to `codex exec` with `--image=`. A cast with
references and a gen-cmd without `{ref}` is a loud refusal, not a silent
text-only round.

The sheet itself has the same candidate → approved lifecycle as every other
asset. `mag cast-sheet <direction.yaml>` renders sheet candidates into
`art-directions/rounds/<name>/<stamp>/` from a prompt composed verbatim
from the direction file (no brief-writer call), evolving from the current
`reference` when one exists. Every invocation rewrites the direction's
review page, `art-directions/rounds/<name>/showcase.html` — current canon
on top, every round's candidates below, the variant whose bytes match the
installed reference badged CANON (`--showcase` rebuilds it from disk
without generating). Approval is the editor copying the chosen variant
over the cast's `reference:` path.

A direction may also carry `direction.cast_license` — per-slot editorial
license text (keyed `cover` / `opener` / `tail` / `closing`) that loosens
cast *presentation* while identity holds. On a licensed slot the injected
cast block says identities are canon and appends the license, explicitly
overriding fixed outfits; unlicensed slots keep the strict "draw exactly
as specified" regime. Openers stay strict by convention — they are the
cast's canonical appearances; tails and closing plates are where the world
breathes (older Pedro, painterly light, seasonal clothes).

`mag cast-check <edition>` is the advisory on-model judge: a vision model
scores each generated candidate against the cast prompts (design only —
pose, action, props, and setting are free), writes `cast-check.yaml` into
the round, and the showcase badges off-model images with the reason. On
licensed slots the judge scores identity anchors only, so a licensed
variation never reads as drift. Like every critic in this pipeline it
flags and never selects; verdicts inform the editor's eye, they do not
replace it.

The current cast (`art-directions/story-led-boy-and-robot.yaml`): **Pedro**,
the boy with round glasses, and **Maro**, his helper robot.

## Briefs

`mag art` proposes the edition's brief slate in one model call, seeded with
this document, `prompts/cover-art-candidates.md`, the edition's art
direction file, and `edition.yaml`. A complete slate covers:

- the cover, per the cover document's three branches;
- one opener brief per article, carrying that article's `article_id`;
- one tail brief per article, carrying that article's `article_id`;
- closing-plate briefs to keep the approved pool at three or more.

Every brief is a standalone image-generation prompt: the generator sees
nothing but the prompt text, so the art direction's visual language,
palette, constraints, and avoid-list must be restated inside it. Every
interior brief also records `subject`, `composition`, `alt_text`, and
`credit` so approval is a copy into `edition.yaml`, not a writing task.

## Dialog vignettes

Multi-panel cast stories with speech balloons (an experiment that earned
its keep — worked example in
`art-directions/experiments/vignette-wilted-sprout/`). The recipe:

1. Write one `generate.sh` of `tools/imagegen` calls, one per panel: a
   scene sentence naming the speaking cast members, the same setting
   description in every panel, the direction's style text, and the cast
   block. Attach the canon sheet with `--ref`.
2. Two lettering routes, both kept:
   - **Baked** (the editor's preferred look): the panel prompt requests
     "small round speech balloons hand-lettered in CAPITAL letters
     containing EXACTLY: …". Short lines (2–4 words) render reliably.
     A language change is a regeneration.
   - **Typeset**: generate the panels wordless ("compose with quiet open
     space in the upper third") and set the dialog after with
     `python3 tools/letter.py <balloons.json>` — balloon centre, tail
     target, and text per panel; one spec per language, so a Spanish
     edition retypes the balloons without touching the art.
3. Panels are independent generations: continuity props (a plant's wilt,
   a prop's position) drift between panels. Keep continuity-critical
   objects simple, or attach the previous panel as a second `--ref`.
4. Assemble strips or 2×2 grids with Pillow; keep dialog in caps.

## Candidate rounds and the lifecycle

Assets move `candidate → approved`, and only the editor moves them.

1. **Generate** — `mag art <edition> --gen-cmd …` renders N variants of each
   brief into a timestamped `editions/<id>/art/rounds/<stamp>/` directory
   with a proof sheet. Rounds are append-only: nothing is overwritten,
   nothing is deleted, failed variants stay on the record.
2. **Dry run** — `mag art <edition> --dry-run` does everything except spend
   image credits: it writes the slate to `briefs.yaml` and an executable
   `generate.sh` whose commands can be run later (or by hand, one prompt at
   a time) when credits exist. A dry round is marked `dry_run: true` in its
   `round.yaml`.
3. **Review** — every `mag art` invocation rewrites
   `editions/<id>/art/showcase.html`: all generated candidates across all
   rounds, grouped cover → openers → tails → closing plates, with the
   assets `edition.yaml` currently selects badged. `mag art <edition>
   --showcase` rebuilds the page from disk without generating anything.
   Feedback names images as `brief-id vN (round)`.
4. **Approve** — the editor copies a chosen variant's path (with `alt_text`
   and `credit`) into `edition.yaml`: `cover.art_path`,
   `articles[].opener_art`, `articles[].tail_art_path`, `closing_plates[]`.
   Approval is only ever this hand edit; process approval is never
   selection.
5. **Reuse** — `mag produce` rewrites manuscripts; `mag render` stages
   whatever `edition.yaml` points at. Approved art rides through unlimited
   rewrites untouched.

## Coverage and staleness are advisories, never triggers

The render critic reports gaps; it never fills them and never generates:

- an article whose final page ends on a large trailing blank with no printed
  tail art is flagged `article-tail-gap` (review severity);
- a declared tail the typesetter dropped is flagged `tail-art-dropped`;
- sparse pages and whitespace voids are flagged for the reviewer's eye.

When a rewrite meaningfully changes an article's proposition, its opener may
no longer fit. That is a staleness question for the editor — regeneration is
a decision, not a reflex, and the default is always to keep the approved
asset.
