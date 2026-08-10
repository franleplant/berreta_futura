#!/bin/sh
# Experimental Flopaz-led closing-plate (filler) art. Not bound to any
# edition. Prompts mirror a licensed closing brief: poster-weight vertical
# scene + restated direction + licensed cast block, canon sheet attached.
set -eu
cd "$(dirname "$0")/../../.."
OUT=art-directions/experiments/flopaz-fillers
REF=art-directions/references/story-led-boy-and-robot-cast.png

STYLE='Original family-friendly children'"'"'s science-comedy manga with simple charcoal contours, rounded readable expressions, economical watercolor washes, minimal hatching, restrained halftone, and quiet print grain. Scene-led gentle historical magazine color at low to medium saturation: softened cyan and cobalt, brick coral, muted green, dusty lavender, small warm-ochre accents, warm off-white breathing room, and charcoal ink. Entirely wordless: no letters, numerals, labels, captions, or speech balloons. A genuinely vertical, poster-weight full-page closing plate, tall two-to-three portrait aspect, at least 1536 pixels tall, quiet and atmospheric. Avoid photorealism, glossy modern anime rendering, neon, steampunk clutter, and any resemblance to a franchise character.'

FLOPAZ='Flopaz, a school-age girl, Pedro'"'"'s height: chestnut-brown hair in one low side ponytail with straight bangs; soft rose-pink pinafore dress with side pockets over a white short-sleeve top; white socks, muted-green flat shoes. Calm and observant. Always this outfit. Never twin pigtails, never a hat, never glasses.'

MARO='Maro, a small helper robot, waist-high to Pedro: off-white rounded rectangular body; black face screen with two friendly curved white eyes; cobalt side panels, shoulder joints, mitten hands, and rounded feet; one short antenna with a cobalt ball tip; coral tool pouch at the waist. Never a single eye, a visor face, tank treads, wheels, tin-toy styling, humanoid proportions, or extra limbs.'

LICENSE='This slot is licensed to vary presentation, overriding the fixed outfits above where they conflict: closing plates carry the tail license at full-page poster weight — mood leads, more painterly rendering, softer light, Flopaz reading a few years older, wardrobe following the hour and season. Identity anchors hold: Flopaz'"'"'s chestnut side ponytail and bangs; Maro'"'"'s black screen face with two curved white eyes, rounded silhouette and antenna.'

CAST_SOLO="Recurring cast — identities below are canon: $FLOPAZ

$LICENSE"

CAST_DUO="Recurring cast — identities below are canon: $FLOPAZ $MARO

$LICENSE"

tools/imagegen "Flopaz, a few years older, stands at a tall arched window at night watering a single plant on the sill, the town's rooftops and one lit clocktower far below, her reflection faint in the dark glass. $STYLE

$CAST_SOLO" --out "$OUT/plate-flopaz-window.png" --ref "$REF" &

tools/imagegen "Flopaz and Maro sit side by side on a rooftop ridge at first light, seen from behind, a sky full of distant round balloons drifting up from the waking town, Maro's antenna catching the first sun. $STYLE

$CAST_DUO" --out "$OUT/plate-flopaz-maro-rooftop.png" --ref "$REF" &

tools/imagegen "Flopaz asleep in a deep armchair under a plaid blanket, an open book slipping from her hand, while Maro on a stool reaches up to dim the tall reading lamp, night blue in the window behind. $STYLE

$CAST_DUO" --out "$OUT/plate-flopaz-maro-lamp.png" --ref "$REF" &

tools/imagegen "Flopaz walks up a narrow greenhouse aisle at dusk carrying a watering can, tall shelves of potted seedlings rising on both sides into the glass roof, one warm lantern hanging ahead of her. $STYLE

$CAST_SOLO" --out "$OUT/plate-flopaz-greenhouse.png" --ref "$REF" &

wait
ls -la "$OUT"
