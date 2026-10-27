# Cover-art candidate process

Every edition gets a round of TWELVE cover briefs, each generated once.
Each brief is one standalone image-generation prompt for a portrait (2:3),
text-free, full-page cover. The editor picks one; unpicked candidates stay
in their round.

## The job: stop someone across the room

A cover is a poster. It has one second to make a stranger walk over and
pick the magazine up. Judge every brief by that test before writing it:
would this image grab you from three meters away, at the size of a
postcard, in a pile of other magazines?

What grabs:

- ONE huge, simple, instantly readable shape that fills the page, with a
  silhouette you could cut out with scissors.
- Violent color: two or three saturated colors at full strength, hard
  figure-ground contrast, nothing grey, beige, or muted.
- A surprise or a joke the eye gets before the brain does: an object at
  the wrong scale, in the wrong material, in the wrong place, doing the
  wrong thing; a visual pun; a contradiction.
- Scale and drama: extreme close-up, impossible size, an object breaking
  out of the frame, a strong diagonal.

What does not grab, and is banned: quiet scenes, landscapes, rooms, aerial
views, small objects lost in space, muted or pastel palettes, soft natural
light, documentary realism, anything you would call "nice" or "calm", and
the glossy single object centred on a seamless studio sweep that earlier
covers already used.

## Twelve different ideas

The section "covers already printed in past editions" holds the briefs
behind earlier covers: never repeat their object, event, or formula.

Each brief is a different idea and a different look. Spread them across
media that print bold: graphic poster with flat shapes, pop-art
screenprint, bold collage, oversized 3D object render with hard shadows,
cut-paper, bold painted illustration, high-contrast photograph with flash.
No two briefs share a medium and a dominant color.

## Where the idea comes from

Read the articles, not the title. Each brief takes its idea from a concrete
thing in one of the articles (an object, a mechanism, a moment where
something moves, breaks, opens, or pays) and turns it into one striking
picture. Spread the twelve across at least six articles. The drafted issue
title may inspire at most two briefs.

## Write the prompt for the image generator

The image generator reads only the prompt. Write it the way an art
director briefs a poster illustrator: medium and finish first, then the one
big shape and its surprise, then color, light, and framing, then the
constraints below in one or two sentences. Under about 110 words. No
checklists or meta-commentary. No two prompts share an opening phrase.

## Hard constraints (every brief, restated in its prompt)

- Portrait 2:3 artwork, 1440 x 2160. Full-bleed under a small wordmark
  in the top-left corner, a red-orange spine band on the right edge, and
  one line of type in the bottom strip: nothing critical top-left or
  along the bottom.
- The dominant field is a saturated color or a light tone, never black,
  near-black, or a muddy dark ground: uncoated stock prints them as mud.
- No text, letters, numerals, logos, pseudo-writing, or watermark in the
  artwork; layout owns all typography.
- No swarms, confetti, or scattered debris, no circuit boards, network
  graphs, glowing brains, robots, neon cyberpunk, or other AI clichés.

## Review and selection

The editor reviews candidates as rendered covers in the showcase and
selects by setting `cover.art_path`. If none is picked, the next round is
twelve fresh briefs.
