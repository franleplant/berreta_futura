# Cover-art candidate process

Every edition gets a round of EIGHT cover briefs. Each brief is one
standalone image-generation prompt for a portrait (2:3), text-free,
full-page cover. The editor picks one; unpicked candidates stay in their
round.

## Match the editor's taste

The section "covers the editor approved in past editions" holds the
briefs behind every cover the editor actually picked. They are the
target. Read them before writing anything and name to yourself what they
share; at the time of writing it is this: a hyperreal photograph of one
physical EVENT caught at its peak, where a material changes state (metal
pours, glass shatters, a chain bursts out of a hull, a ball punches
through a sign, liquid floods a keyhole), one or two objects, glossy
studio or hard natural light, on one saturated flat color ground.

- SIX of the eight briefs work inside that taste, each with a different
  object, a different material event, and a different ground color.
- TWO briefs are deliberate outliers: a different medium or register
  (a printmaking or flat-ink poster, a staged sculpture, a painting),
  still a single striking event, still print-safe.
- Never reuse a past cover's object or event; reuse only its level of
  intent and finish.

## Where the motif comes from

Read the articles, not the title. Each brief takes its object from a
concrete thing in one of the articles (an object, a mechanism, a moment
where something moves, breaks, opens, or pays) and turns it into one
physical event. Spread the eight briefs across at least four different
articles. A drafted issue title is a suggestion, not a brief: at most two
briefs may illustrate it.

## Write the prompt for the image generator

The image generator reads only the prompt. Write it the way a
photographer or art director would describe the shot:

- Open with the medium and finish (for example "hyperreal studio
  photograph, high-speed flash, glossy").
- Then the object, the event at its most violent instant, the material
  change, and the ground color, in plain concrete words.
- Then light, camera position, and where the object sits in the frame.
- Close with the constraints below, restated in one or two sentences.

Keep each prompt under about 120 words. Do not write checklists, counts
of forms, rule names, or meta-commentary ("the proposition is", "five
forms, no more"); the generator cannot use them and they dilute the
picture. No two prompts in a round share a sentence skeleton.

## Hard constraints (every brief, restated in its prompt)

- Portrait 2:3 artwork, 1440 x 2160. Full-bleed under a small wordmark
  in the top-left corner, a red-orange spine band on the right edge, and
  one line of type in the bottom strip: keep the subject in the middle
  three-fifths and nothing critical top-left or along the bottom.
- The ground is one SATURATED color that stays a color in print (cobalt,
  emerald, vermilion, violet, chrome yellow, teal, magenta, tangerine) or
  a pale bone/cream. Never black, near-black, or a dark or mid-tone or
  textured ground: uncoated stock prints them as mud. Dark belongs to
  forms, never to the ground.
- No text, letters, numerals, logos, pseudo-writing, or watermark in the
  artwork; layout owns all typography.
- No people as the subject (a hand or one tiny figure only when the event
  needs it), no swarms, confetti, or scattered debris as the subject, no
  circuit boards, network graphs, neon cyberpunk, or AI clichés.
- No two briefs in a round share a ground color.

## Review and selection

The editor reviews candidates as rendered covers in the showcase and
selects by setting `cover.art_path`. If none is picked, the next round is
eight fresh briefs: new objects and events, same taste and constraints.
