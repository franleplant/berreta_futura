# Cover-art candidate process

Every new edition produces exactly three square, text-free cover-art
candidates before the editor selects one. Candidate generation is an
author-time creative step, never part of deterministic packaging. The
production compiler continues to consume only `cover.art_path` from
`edition.yaml`.

The cover is the synthetic branch: one bold abstract-graphic proposition in
poster inks. A round is three DIFFERENT synthetic propositions (not three
styles), each derived from its own one-sentence reading of the edition.
Write those readings first, from the complete article roster; a reading
that produces only a still life is too abstract, so go back to the articles
for the moment where something moves, breaks, opens, or pays.

(The `cast_poster`, `art_directed`, and `wildcard` branches from earlier
rounds are retired after editor review; their candidates stay on disk. The
recurring cast lives inside the magazine, not on the cover.)

## The frame it lives in

The artwork is not the cover; it is a square plate placed on the cover.
The fixed frame around it: a warm off-white page, the black masthead with
its red-orange accent above, the headline in heavy black capitals, a
red-orange spine band at the right edge, credits in small capitals below.
Every brief must say in one sentence how the plate sits in that frame.

Consequences, non-negotiable:

- The plate must hold a hard-edged, high-contrast silhouette against a
  WHITE page. A mid-tone ground (photographic gray sky, dusk haze, muddy
  field) dissolves into the page and reads as a dull rectangle.
- The ink set should shake hands with the masthead: pick up its
  red-orange, its black, or the page's bone white somewhere prominent.
  A plate whose colors ignore the frame looks pasted in from another
  magazine.
- Grounds are either confident-dark (near-black, deep navy, oxblood) for
  a lantern-slide effect inside the white page, or pale (bone, cream)
  for a constructivist effect where the page and plate breathe together.
  Nothing in between.

## The cover ink discipline

The cover NEVER uses the interior art direction's palette. Interior
directions are tuned for gentle print reading; on a cover they read as
dull. Ignore any palette, style, or constraint text from the edition's
art direction file when writing cover briefs: covers have their own rules.

- Choose a cover ink set per edition: TWO or THREE saturated, committed
  inks plus one ground, plus ONE luminous accent. Deep and bright beat
  pale and dusty: oxblood, cobalt, violet-navy, emerald, vermilion,
  chrome yellow, a near-black. Name the exact inks in the brief.
- The ground is one color and generous: either a pale field (cream,
  bone) or a deep dark (navy-black, oxblood-black). No mid-tone grounds,
  no textured wallpaper grounds.
- Exactly one luminous focal accent: one glowing, hot, or white element
  that owns the frame and is the image's event. If the thumbnail does not
  lead the eye there in one beat, the brief fails.
- Print-flat color: hard edges, confident fills, controlled shading in
  service of depth on the few big forms. No gradients that muddy, no
  pigment-wash softness, no all-over grain doing the work color should do.

## The proposition

- ONE compact editorial metaphor, stated in the brief in one sentence
  before the visual description. The image argues it; it does not
  illustrate a list.
- THREE TO SEVEN large forms. Count them in the brief. Anything the
  proposition does not need is deleted, and a form smaller than a
  fingernail at print size is noise, not a form.
- Banned as primary subject matter: swarms, confetti, particle clouds,
  grids or arrays of repeated small elements, scattered debris. A
  multitude may be IMPLIED (three envelopes and a shadow suggest a
  million) but never drawn.
- The impact test, at thumbnail size: an unmistakable visual event,
  a memorable silhouette, one strong source of tension (scale shock,
  precarious balance, spatial invasion, arrested motion). A composition
  whose verb is "sits" fails.
- Figuration is allowed at emblem level (a hand, a door, a coin, one
  tiny human for scale) but no scenes, no characters, no narrative
  staging.

## Shared constraints

- Square PNG artwork at least 1000 × 1000 pixels.
- All typography lives in layout code: no masthead, title, issue number,
  caption, logo, pseudo-writing, numerals, or watermark in the artwork.
- Design for the fixed cover crop, thumbnail recognition, and clean print
  reproduction; no important detail at the extreme edges.
- Judge anatomy, materials, lighting, intersections, and physical
  relationships as strictly as composition. Reject generic-AI incoherence:
  no circuit motifs, network graphs, neon cyberpunk, or AI-futurist
  clichés.
- Rounds are append-only versioned siblings; never overwrite or silently
  discard candidates.

## Review and selection

Review the three propositions together at full size, as thumbnails, and
inside the unchanged cover frame. Check conceptual relevance, ink
discipline, generation artifacts, crop safety, tonal reproduction, and
that the three propositions are meaningfully distinct. The editor selects
by updating only `cover.art_path`; unselected candidates remain preserved
in their round.

If the editor selects none, generate a complete new round of three fresh
propositions: change the reading, metaphor, subject, and composition;
keep the ink discipline and shared constraints. Continue until the editor
explicitly selects; never infer selection from approval of the process.
