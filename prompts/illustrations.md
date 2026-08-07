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
  edition's art direction. Square compositions are preferred; the essential
  subject must survive the opener frame crop and remain legible at A5.
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
