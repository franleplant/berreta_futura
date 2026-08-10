#!/bin/sh
# Experimental Flopaz-led tail art. Not part of any edition; outputs stay in
# the scratchpad. Prompts mirror what mag art would emit for a licensed tail:
# scene + restated direction + licensed cast block, canon sheet attached.
set -eu
cd /Users/franguijarro/code/magazine
OUT=/private/tmp/claude-501/-Users-franguijarro-code-magazine/bdf58a74-0a22-41e6-a63c-31a2a9273989/scratchpad/flopaz-tails
REF=art-directions/references/story-led-boy-and-robot-cast.png

STYLE='Original family-friendly children'"'"'s science-comedy manga with simple charcoal contours, rounded readable expressions, economical watercolor washes, minimal hatching, restrained halftone, and quiet print grain. Scene-led gentle historical magazine color at low to medium saturation: softened cyan and cobalt, brick coral, muted green, dusty lavender, small warm-ochre accents, warm off-white breathing room, and charcoal ink. Entirely wordless: no letters, numerals, labels, captions, or speech balloons. Wide three-to-one strip at least 1024 pixels tall, essential action inside the safe central band. Avoid photorealism, glossy modern anime rendering, neon, steampunk clutter, and any resemblance to a franchise character.'

FLOPAZ='Flopaz, a school-age girl, Pedro'"'"'s height: chestnut-brown hair in one low side ponytail with straight bangs; soft rose-pink pinafore dress with side pockets over a white short-sleeve top; white socks, muted-green flat shoes. Calm and observant. Always this outfit. Never twin pigtails, never a hat, never glasses.'

MARO='Maro, a small helper robot, waist-high to Pedro: off-white rounded rectangular body; black face screen with two friendly curved white eyes; cobalt side panels, shoulder joints, mitten hands, and rounded feet; one short antenna with a cobalt ball tip; coral tool pouch at the waist. Never a single eye, a visor face, tank treads, wheels, tin-toy styling, humanoid proportions, or extra limbs.'

LICENSE='This slot is licensed to vary presentation, overriding the fixed outfits above where they conflict: Tails may drift toward the edition'"'"'s quieter register: more painterly rendering, softer light, Flopaz reading a few years older, wardrobe following the hour and season instead of the canon outfits. Identity anchors hold: Flopaz'"'"'s chestnut side ponytail and bangs; Maro'"'"'s black screen face with two curved white eyes, rounded silhouette and antenna.'

CAST_SOLO="Recurring cast — identities below are canon: $FLOPAZ

$LICENSE"

CAST_DUO="Recurring cast — identities below are canon: $FLOPAZ $MARO

$LICENSE"

tools/imagegen "Flopaz kneels at the right end of a long window bench at dusk, repotting a small plant, a trail of empty clay pots and scattered soil running to the left edge. $STYLE

$CAST_SOLO" --out "$OUT/tail-flopaz-plants.png" --ref "$REF" &

tools/imagegen "Flopaz, reading a few years older, sits wrapped in a wool cardigan under a single desk lamp at the right of the strip, a long shelf of books receding into shadow to the left, one book open on her knees. $STYLE

$CAST_SOLO" --out "$OUT/tail-flopaz-reading.png" --ref "$REF" &

tools/imagegen "Flopaz walks along a low garden wall at golden hour holding a small kite shaped like a plain square tile, the kite string running the whole length of the strip to the kite far at the left, her ponytail caught in the wind. $STYLE

$CAST_SOLO" --out "$OUT/tail-flopaz-kite.png" --ref "$REF" &

tools/imagegen "Flopaz pins folded paper notes to a laundry line strung across the whole strip in soft morning light, while Maro, small at the far left end, hands her the next note from a basket. $STYLE

$CAST_DUO" --out "$OUT/tail-flopaz-maro-line.png" --ref "$REF" &

wait
ls -la "$OUT"
