# Cover-art candidate process

Every new edition produces exactly three square, text-free cover-art
candidates before the editor selects one. Candidate generation is an
author-time creative step, never part of deterministic packaging. The
production compiler continues to consume only `cover.art_path` from
`edition.yaml`.

Before generating images, write a one-sentence reading of the edition as a
whole. Derive each candidate from that reading and the complete article
roster, not from one convenient article or from generic AI imagery.

## The impact test (every branch)

A cover is a poster, not a statement of theme. Before a brief is accepted it
must pass, at thumbnail size, the test previous rounds reserved for the
wildcard alone:

- an unmistakable visual event: something is HAPPENING, not arranged;
- a memorable silhouette readable at postage-stamp scale;
- at least one strong source of tension: scale shock, precarious balance,
  spatial invasion, arrested motion, a held breath.

A tidy grid of theme-objects, a neat array of rooms, boxes, shelves, or
tools, or any composition whose verb is "sits" fails the test. If the
one-sentence reading of the edition produces only still lifes, the reading
is too abstract: re-read the articles for the moment where something moves,
breaks, opens, or is caught mid-air, and start from there.

## `cast_poster`

The cover face of the magazine's own world. Pedro, Maro, and Flopaz (the
edition art direction's recurring cast) in one dramatic, story-charged
moment at full poster weight, the key art of an adventure the reader has
not seen yet, derived from the edition reading. The closing-plate license
applies: mood leads, identity anchors hold, and the moment may be grand
(vast machinery, deep space of small lit rooms, weather, night) while the
cast stays exactly themselves. Composed for the cover crop with the event in
the safe area; wordless as always.

This branch exists because the cast is the magazine's most loved asset and
the interior's story-led language deserves a poster. It is not a scaled-up
opener: openers illustrate one article's proposition; the cast poster stages
the edition's stakes.

## `art_directed`

An edition-specific artistic interpretation using the publication palette.
Choose the medium that best serves the editorial proposition: photography,
painting, printmaking, sculpture, staged work, collage, drawing, textile, or
another deliberate form. No required subject or motif; nothing repeated from
earlier editions merely because it was approved once. Reuse the level of art
direction, material conviction, and compositional intent, not the objects.
The impact test applies in full: material beauty does not excuse stillness.

## `wildcard`

Choose metaphor, subject, and composition from the edition's contents. Do
not imitate the other branches. One improbable idea, immediately legible,
with enough formal discipline to remain convincing in print.

The wildcard is always rendered photorealistically: a convincing photograph
of the improbable thing, with real materials, real optics, and coherent
physical light — never a painting, illustration, or render that reads as
digital art. The impossibility lives in the subject; the camera plays it
straight. It may depart from the publication palette only when the cover
proof shows the result remains compatible with the fixed cover system.

## Shared constraints

- Generate `cast_poster`, `art_directed`, and `wildcard` exactly once each
  per round. Rounds are append-only versioned siblings; never overwrite or
  silently discard candidates.
- Square PNG artwork at least 1000 × 1000 pixels.
- All typography lives in layout code: no masthead, title, issue number,
  caption, logo, pseudo-writing, or watermark in the artwork.
- Design for the fixed cover crop, thumbnail recognition, and clean print
  reproduction; no important detail at the extreme edges.
- Judge anatomy, materials, lighting, intersections, and physical
  relationships as strictly as composition. Reject generic-AI incoherence.

## Review and selection

Review the three candidates together at full size, as thumbnails, and inside
the unchanged cover frame. Check conceptual relevance, generation artifacts,
crop safety, tonal reproduction, and that the branches are meaningfully
distinct. The editor selects by updating only `cover.art_path`; unselected
candidates remain preserved in their round.

If the editor selects none, generate a complete new round of all three
branches with a changed editorial proposition, subject, metaphor, and prompt
input per branch, keeping the branch definitions and shared constraints. Continue
until the editor explicitly selects; never infer selection from approval of
the process.
