# Canto vivo cover direction

`design.toml` is the single authored geometry and color contract for both outer
covers. The compiler combines it with localized edition copy, bundled Inter and
Source Serif fonts, and the edition artwork to materialize self-contained SVGs.
Every visible letter is converted to SVG paths; neither face has a system-font
or network dependency.

Cover-art, selection, proof, and review work is issued by `RunEngine` as
durable offers. Use `npm run engine -- ...` to start, inspect, answer, or run
the worker for that work. Do not use the retained `mag` proof commands or proof
directories to advance an edition.

A proof result is an immutable selected-art or render artifact. The active
visual-review offer must name its exact render artifacts; a later render cannot
inherit the old decision. Rendering consumes registered selected art and never
generates it.

The front and back reference directories freeze legacy comparison material. They
are not current workflow state and must not be updated through an old build or
proof command. A deliberate redesign requires a new selected-art artifact and
an independent review of the exact current render.
