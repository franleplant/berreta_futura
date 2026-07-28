# Cover-art candidate process

Every new edition produces exactly three square, text-free cover-art candidates
before the editor selects one. Candidate generation is an author-time creative
step, never part of deterministic packaging. The production compiler continues
to consume only `cover.art_path` from `edition.yaml`.

Before generating images, write a one-sentence reading of the edition as a
whole. Derive each candidate from that reading and the complete article roster,
not from one convenient article or from generic AI imagery.

## Shared constraints

- Generate `synthetic`, `art_directed`, and `wildcard` exactly once each as the
  initial slate. Iterations remain versioned siblings; never overwrite or
  silently discard them.
- Produce square PNG artwork at least 1000 × 1000 pixels.
- Keep all typography in layout code: no masthead, title, issue number,
  caption, logo, pseudo-writing, or watermark in the artwork.
- Design for the fixed cover crop, thumbnail recognition, and clean print
  reproduction. Preserve a legible silhouette and avoid important detail at the
  extreme edges.
- Judge anatomy, materials, lighting, intersections, and physical relationships
  as strictly as composition. Reject generic-AI incoherence.
- Record the three promoted candidates and their SHA-256 digests in
  `art/cover-candidates.yaml` using schema version 2 and declare each branch's
  `generation_method`. The `synthetic` branch must declare `imagegen`.
  `edition.yaml` selects one production candidate.

## `synthetic`

Preserve the existing synthetic cover grammar: one compact abstract
proposition, three to seven large geometric components, a substantial field of
negative space, and the publication ink set. Generate this branch with the
image model, using an existing approved synthetic cover as an art-direction
reference when one is available. The reference controls visual language,
geometric confidence, palette discipline, and print character; it does not
license copying the earlier composition, motif, or spatial arrangement.

Controlled dimensional shading and synthetic material depth are welcome when
they strengthen the proposition. Avoid literal diagrams, icon systems,
generic-AI futurism, or ornamental complexity. This branch provides continuity
through recognizable art direction rather than deterministic construction.

## `art_directed`

Create an edition-specific artistic interpretation using the publication
palette. Choose the medium that best serves the editorial proposition:
photography, painting, printmaking, sculpture, staged work, collage, drawing,
textile, or another deliberate form are all eligible.

This is not a collage template. It has no required subject or motif. Humans and
hands may appear when the concept needs them, but must never be requested by
default. Likewise, do not repeat string, knots, diagrams, paper scraps, or any
other feature merely because a previous edition used it. Reuse the level of art
direction, material conviction, and compositional intent—not the objects.

## `wildcard`

Choose medium, metaphor, subject, and composition from the edition's contents.
Do not imitate either of the other two branches. Seek a single surprising,
inspiring proposition rather than maximalism: one improbable idea, immediately
legible, with enough formal discipline to remain convincing in print.

The wildcard may depart from the publication palette only when the cover proof
shows that the result remains compatible with the fixed cover system. Surprise
does not excuse darkness, muddy reproduction, visual clutter, arbitrary
symbols, incoherent physics, or familiar AI-futurist imagery.

## Review and selection

Review the three candidates together at full size, as thumbnails, and inside the
unchanged cover frame. An independent reviewer checks conceptual relevance,
generic-generation artifacts, crop safety, tonal reproduction, and whether the
three branches are meaningfully distinct. The editor selects the production
asset by updating only `cover.art_path`; unselected candidates remain preserved
as process evidence.
