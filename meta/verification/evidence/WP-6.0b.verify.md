# WP-6.0b verify

Verdict: **ACCEPTED**.

Tip `41ea889`, worktree `<scratch>/v6`, release build.

## Replay

| Command | Exit | Result |
|---|---|---|
| `mag source-codes 010 --check` | 0 | `10 files reproduce byte-for-byte` |
| positive control: the same check with one live 010 record's url edited (WP-6.0d.verify.md) | 1 | `content differs: source-code-the-third-era-...svg`, `codes.json` |

## Independent decode (zxing-cpp 2.x via `uvx --with zxing-cpp --with pillow`, not rqrr)

- Web SVGs rasterized with `mutool draw -r 300`, decoded:
  `source-code-the-third-era-...svg` -> `cursor.com/blog/third-era`;
  `source-code-dario-amodei-...svg` -> `darioamodei.com/post/we-must-pace-the-frontier`.
  Both equal their `codes.json` payloads.
- Print matrices (the ones typst draws) for the first three `codes.json` entries,
  drawn by my own script at 10 px/module with a 4-module quiet zone: all three
  decode to their payload (rietta.com..., anthropic.com/threat-intelligence...,
  anthropic.com/research/alignment-assessment...).

## Injected defect

Mask penalty weight for N2 changed from 3 to 2 (`sourcecodes.rs:133`).
`cargo test --test sourcecodes`: `rust_writes_every_committed_expected_file_byte_for_byte`
FAILED (`008: content differs: source-code-running-a-software-factory-...svg`,
`codes.json`). Note `every_code_decodes_to_its_payload` stayed green: a wrong
mask still gives a valid QR, so only the byte oracle guards segno's mask choice.
Restored.
