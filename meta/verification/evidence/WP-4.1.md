# WP-4.1 full parity gate (mechanical)

Verifier. Tip `art_directed` `fa3fe15` (docs only since `540bbe8`, WP-3.11).

**Gate: PASS.** `mag parity 010` at Tier E exits 0 on two runs from a clean
checkout, each from an empty output dir, and the verdicts are byte-identical
after one normalization (below). Baseline raised: pages 1 and 56 to E.

## Clean checkout

```sh
G=.../7d99e27f/tmp/g41
git clone -q --branch art_directed /Users/franguijarro/code/magazine $G/clone   # HEAD fa3fe15
git -C $G/clone config core.hooksPath .githooks
(cd $G/clone/mag && cargo build --release)      # fresh target dir, Finished
(cd $G/clone && uv sync)                         # fresh .venv
```

Nothing came from another worktree. Edition 010 and its tracked run
`run-2026-09-13T01-34-51` are committed data, and both legs render from the clone.

## The two runs

```sh
mkdir $G/out1   # 0 entries
MAG_PARITY_OUT_DIR=$G/out1 mag/target/release/mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 0
mkdir $G/out2   # 0 entries
MAG_PARITY_OUT_DIR=$G/out2 mag/target/release/mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 0
```

The two runs printed the same lines:

- mode render, gate all_tiers. Staged inputs fresh `bc49b2aa...` (57 edition
  inputs, 43 renderer files). Domain: reader.pdf pages 1..56.
- ratchet: pass (target E, 56 committed entries checked, 56 recorded, 56
  measured, 0 regressions).
- S page_count 56 vs 56. critic pass (results pass vs pass, 4 issues, 1999
  leaves compared, 1022 excluded, 0 differ; Rust text fields on 111 pages 0
  differ; text_characters 0 pages). boxes pass (168 boxes, 56 rotations). text
  pass (56 pages). color pass (59252 entries). navigation pass (85 links, 51
  outlines, 1 title, 1 lang).
- G: 56 pages, max dx 0.000071 pt, max dy 0.0058 pt, 0 beyond G1/G2.
- E glyph positions pass (59073 glyphs, 1529 shows, 0 violations). E display
  list pass (59304 vs 59304, 0 pages differ).
- V: 56 pages, V1/V2 pass, worst page fraction 0.000336.

"All clauses" means every clause the comparator evaluates. Two clauses print
`not_evaluated`, both by design: `tier S code_blocks` (the comparator has no
code-block comparison; 010's code page set is empty) and `tier E raster`
(withdrawn, rasters are Tier V meters). Neither affects the exit code.

## Verdict hashes

| | out1 | out2 |
|---|---|---|
| verdict.json raw sha256 | `1ae78127...5bb252` | `9e99a10a...a332f1` |
| normalized (below) | `172444721bb321f4d0a55a7b6431ec425c4a283760dae518bb830d580313c3ab` | `172444721bb321f4d0a55a7b6431ec425c4a283760dae518bb830d580313c3ab` |
| baseline-proposed.json sha256 | `29c0ab10...711f87` | `29c0ab10...711f87` (byte-identical) |
| a_reader_sha256 (weasyprint) | `ccd302bb...` | `804edd5f...` |
| b_reader_sha256 (typst) | `6c03dda9ae2714977522d6405e8e23eae6fefc7317c0fe66a7b6e9b440bc4290` | same |

Normalization: delete `inputs.a_reader_sha256`, then take the sha256 of
`json.dumps(v, sort_keys=True)`. The raw `diff` of the two sorted verdicts shows
that one line and no other. No path of the out dir appears in the verdict
(grep count 0). The typst reader is byte-identical across the runs, and equals
the value WP-0.2y and WP-5.4g recorded.

**Correction to earlier evidence** (WP-5.4g-5.3g.md, WP-0.2y.md say WeasyPrint
"dates" its reader): the two WeasyPrint readers carry no date. The Info dict is
Producer/Title/Creator only. They differ in WeasyPrint's random image XObject
names (`/i<33 hex>`) and in the compressed content streams that paint them. With
those names normalized, pypdf gives 1408 of 1408 page-content and XObject-data
chunks equal. So the oracle's bytes vary from run to run, and its content does
not.

A third staged run (`$G/v`, a second clean clone, with the raise below committed
there) also exited 0, with ratchet pass (56 at E, 0 regressions) and the same
normalized hash `17244472...`.

## Baseline raise (verifier's)

`baseline-proposed.json` (both runs identical) against the committed
`meta/verification/baseline.json`:
- The top-level fields are equal: note, entry shape, seeded commit and digest.
- Pages 1 and 56 go from `none` with no clauses to `E` with page_count, boxes,
  text, color, navigation and critic. Re-derived from the verdict: every clause
  passes on both pages, G 0 displacement, V fraction as on the interior.
- Pages 2..55 keep tier E. The only change is `critic` added to their clause
  lists: WP-5.3g made the critic a Tier S clause, and it passes on every page.
  This row set is therefore not identical to the committed one. The proposal
  is the committed rows plus the critic clause, and nothing else.

The whole proposal is committed (pages in numeric order, and one sentence added
to `schema_note`). Checks after the raise:
`cargo test --test parity_ratchet -- --nocapture` printed "MODE: full, 56
committed page entries, exercising page 1 at tier E", and it passed. The
tier-lowering branch that WP-5.4g's seed rows had skipped now runs. The staged
run above passed against the raised baseline.

## Verification of the queued WPs

Replays and injected defects: `WP-5.6`, `WP-0.2y`, `WP-5.4g-5.3g`, `WP-3.10`,
`WP-5.11`, `WP-5.12` and `WP-3.11`, each `.verify.md`. All ACCEPTED. In the
clone, `cargo fmt --check` 0, `cargo clippy --all-targets -D warnings` 0, and
`cargo test` 0 (32 result lines, 953 passed, 0 failed, 0 ignored). A first
`cargo test` failed `model_records library_sources_match_the_python_dump`
because I had copied fixture 906's sources into the clone's `library/` while it
ran. That was my contamination. After I moved them out, the suite passed as
above.

## What is and is not proven

PROVEN: from a clean checkout at `fa3fe15`, `mag parity 010` renders both legs
fresh and exits 0 at Tier E, twice. Every evaluated clause is covered on
reader.pdf pages 1..56, the critic on both sides included. The two verdicts are
byte-identical except the oracle PDF's sha, whose variation is random image
names. The typst leg is byte-deterministic.

NOT PROVEN: code-block sameness (clause not implemented). Any edition but 010 at
Tier E with a baseline (`--adhoc` gates Tier S only; 008 and 906 are in the
verify files). Any language but en under the ratchet. Equality is not
correctness: both engines could agree on something wrong. The critic and fault
suites cover what they check, and nothing more.
