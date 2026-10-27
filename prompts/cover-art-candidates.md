# Cover-art candidate process

Every edition gets a round of EIGHT cover briefs. Each brief is one
standalone image-generation prompt for a portrait (2:3), text-free,
full-page cover. The editor picks one; unpicked candidates stay in their
round.

## Eight directions, not eight variations

The section "covers already printed in past editions" holds the briefs
behind earlier covers. They show the level of intent the editor expects
and, above all, a formula that is now used up: one glossy object caught
mid-splash or mid-shatter, centred on a seamless flat color sweep, lit
like a product shot. The editor finds that look plain, flat, and
machine-made. At most ONE brief in the round may use it.

Every brief takes a different direction, and the directions differ in
kind, not in object. Spread the round across registers such as:

- an editorial photograph with a real place in it: depth, weather,
  architecture, a scene with a before and an after;
- a printmaking piece (risograph, linocut, woodcut, screenprint) with
  visible ink overlap, grain, and misregistration;
- a cut-paper or collage construction with real shadows between layers;
- a painting with a point of view (gouache, oil, poster painting) and a
  composition that is not centred;
- a built miniature or diorama photographed with a shallow focus;
- a graphic, typographic-free poster made of bold shapes and pattern;
- a surreal, deadpan still life that tells a joke or a small story;
- a strange angle: aerial, worm's-eye, extreme close-up, cutaway.

Each brief must have an idea, not only an object: a situation, a
contradiction, a visual pun, or a moment with consequences that a reader
could explain in one sentence. Plain "object on a colored background" is
not an idea.

Avoid the marks of generated art: plastic sheen everywhere, perfect
symmetry, dead-centre subjects, glowing rim light on everything, airbrushed
smoothness, generic studio sweeps. Ask for texture, imperfection, a light
source with a reason, and a composition that uses the whole page.

Never reuse a past cover's object, event, or formula.

## Where the motif comes from

Read the articles, not the title. Each brief takes its idea from a
concrete thing in one of the articles (an object, a mechanism, a place, a
moment where something moves, breaks, opens, or pays) and turns it into a
picture. Spread the eight briefs across at least five different articles,
and name the article each brief comes from to yourself. A drafted issue
title is a suggestion, not a brief: at most one brief may illustrate it.

## Write the prompt for the image generator

The image generator reads only the prompt. Write it the way an art
director would brief an illustrator or photographer:

- Open with the medium, technique, and finish in specific words.
- Then the scene and its idea, in plain concrete words.
- Then light, viewpoint, and where things sit in the frame.
- Close with the constraints below, restated in one or two sentences.

Keep each prompt under about 120 words. Do not write checklists, counts
of forms, rule names, or meta-commentary; the generator cannot use them.
No two prompts in a round share a sentence skeleton or an opening phrase.

## Hard constraints (every brief, restated in its prompt)

- Portrait 2:3 artwork, 1440 x 2160. Full-bleed under a small wordmark
  in the top-left corner, a red-orange spine band on the right edge, and
  one line of type in the bottom strip: nothing critical top-left or
  along the bottom.
- Light and color must survive uncoated paper: the picture's dominant
  field is a color or a light tone, never a black, near-black, or muddy
  dark ground. Dark belongs to forms and accents.
- No text, letters, numerals, logos, pseudo-writing, or watermark in the
  artwork; layout owns all typography.
- No swarms, confetti, or scattered debris as the subject, no circuit
  boards, network graphs, glowing brains, robots, neon cyberpunk, or other
  AI clichés.
- No two briefs in a round share a dominant color.

## Review and selection

The editor reviews candidates as rendered covers in the showcase and
selects by setting `cover.art_path`. If none is picked, the next round is
eight fresh briefs in eight new directions.
