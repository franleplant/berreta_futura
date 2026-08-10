#!/bin/sh
# Experimental four-panel dialog vignette — deliberately breaks the wordless
# rule. All three cast members, canon outfits, one shared setting.
set -eu
cd "$(dirname "$0")/../../../.."
OUT=art-directions/experiments/vignette-wilted-sprout/es
REF=art-directions/references/story-led-boy-and-robot-cast.png

STYLE='Original family-friendly children'"'"'s science-comedy manga with simple charcoal contours, rounded readable expressions, economical watercolor washes, minimal hatching, restrained halftone, and quiet print grain. Scene-led gentle color at low to medium saturation: softened cyan and cobalt, brick coral, muted green, dusty lavender, warm off-white, charcoal ink. Square single panel of a four-panel story; the setting is the same sunlit kitchen windowsill with a small clay pot in every panel. Dialog appears in small round speech balloons hand-lettered in CAPITAL letters containing EXACTLY the quoted words and nothing else; no other text, labels, or captions anywhere. Avoid photorealism, glossy modern anime, neon, and any resemblance to a franchise character.'

CAST='Recurring cast — draw exactly as specified, never redesign: Pedro, a school-age boy: black tousled hair, big round glasses, teal crew-neck top, khaki shorts, red sneakers. Maro, a small helper robot, waist-high to Pedro: off-white rounded rectangular body; black face screen with two friendly curved white eyes; cobalt side panels, shoulder joints, mitten hands, and rounded feet; one short antenna with a cobalt ball tip; coral tool pouch at the waist. Flopaz, a school-age girl, Pedro'"'"'s height: chestnut-brown hair in one low side ponytail with straight bangs; soft rose-pink pinafore dress with side pockets over a white short-sleeve top; white socks, muted-green flat shoes.'

tools/imagegen "Panel 1: Pedro and Maro lean in close over a drooping, wilted seedling in the clay pot on the windowsill, alarmed. Pedro's speech balloon says exactly: \"¡SE MUERE!\" $STYLE

$CAST" --out "$OUT/panel-1.png" --ref "$REF" &

tools/imagegen "Panel 2: Maro proudly holds up a wrench pulled from his coral tool pouch, antenna perked, while Pedro looks doubtful with a hand behind his head. Maro's speech balloon says exactly: \"¡YO LO ARREGLO!\" $STYLE

$CAST" --out "$OUT/panel-2.png" --ref "$REF" &

tools/imagegen "Panel 3: Flopaz steps in between them holding a small watering can, gently lowering Maro's wrench arm with her other hand, calm and knowing, and waters the seedling. Flopaz's speech balloon says exactly: \"MIRAD ESTO.\" $STYLE

$CAST" --out "$OUT/panel-3.png" --ref "$REF" &

tools/imagegen "Panel 4: the seedling stands tall with one small coral flower; Pedro cheers with both fists up, Maro's eyes curve extra happy holding the wrench limp at his side, Flopaz smiles with the empty watering can. Maro's speech balloon says exactly: \"¡LO ARREGLASTE!\" Flopaz's smaller balloon says exactly: \"SOLO AGUA.\" $STYLE

$CAST" --out "$OUT/panel-4.png" --ref "$REF" &

wait
ls -la "$OUT"
