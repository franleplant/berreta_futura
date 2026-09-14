# WP-0.2a evidence: comparator text, geometry, boxes, verdicts

## Base

86e41b44db9e309d9e06bfaff38b63a2aaeac813

## Commands

All from the repo root. The two render trees are untracked; regenerate them
first (each ~70 s; they are deterministic per WP-0.1, so fresh trees give the
same comparison results; verdict digests below will differ only if the PDFs
differ, which WP-0.1 proved they do not):

```sh
cp -R <main-repo>/editions/010/run-2026-09-13T01-34-51 editions/010/ 2>/dev/null || true
cd mag && cargo build && cd ..
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51
```

Name the two resulting `editions/010/render-*` dirs A and B (this run used
A=render-2026-09-14T01-47-59, B=render-2026-09-14T01-49-02). Then:

```sh
cd mag && cargo fmt --check && cargo clippy -q --all-targets -- -D warnings && cargo test -q && cd ..
./mag/target/debug/mag parity 010 --pre-rendered $A $A; echo "exit=$?"
shasum -a 256 output/parity/010/verdict.json
./mag/target/debug/mag parity 010 --pre-rendered $A $A >/dev/null
shasum -a 256 output/parity/010/verdict.json
./mag/target/debug/mag parity 010 --pre-rendered $A $B; echo "exit=$?"
shasum -a 256 output/parity/010/verdict.json
```

Expected: exit 0 each time; the first two digests byte-identical (verdict
determinism); Tier S page_count/boxes/text pass; Tier G max dx/dy 0.000,
beyond-G1/G2 0, structure mismatches 0 on both comparisons.

## Tool versions

poppler 25.08.0 (pdfinfo/pdftotext, asserted at startup against
parity.yaml tools.poppler), rustc 1.96.0, cargo 1.96.0. New crate:
unicode-normalization 0.1.25 (NFC step of the normalization spec).

## Metrics

- Interior domain: pages 2..55 of 56.
- Self-test A vs A: page_count pass (56/56), boxes pass (0 mismatches at
  0.05 pt), text pass (0 pages differ), G max dx 0.000 pt, max dy 0.000 pt,
  0 beyond G1, 0 beyond G2, 0 structure mismatches. Exit 0.
- A vs B (independent renders): identical results, all pass, all zeros.
  Exit 0.
- Verdict determinism: two A-vs-A runs byte-identical.

## Verdicts

- A vs A: sha256 38de6b73b50359875dd7baa74076ee4d4ddd94ab5a89a23b6783248d4891a709
  (tier S evaluated clauses pass; code_blocks/color/navigation/critic
  not_evaluated with owners; tier G zeros; tier V/E not_evaluated)
- A vs B: sha256 2d6bfbfeab1763fd94e981562874530e150f4ad1a39afe78d1cd14c6966949b2
  (same tier summary; differs from A-vs-A only in inputs.b_reader_sha256)

## Critique round (critiquer-added)

One defect fixed in mag/src/parity/geometry.rs: `layout_pages` now fails
loud when `-bbox-layout` parses fewer pages than the requested range;
before, a parse regression would have produced an all-zero Tier G meter
indistinguishable from perfect agreement. Self-test verdict bytes are
unchanged by the fix (digests above re-verified).

Negative checks (worker's self-tests compared only agreeing inputs; these
prove the comparator fails when it should). Fixture build, from the repo
root with the two render trees present (T is any scratch dir):

    T=<scratch>/wp02a-neg
    mkdir -p $T/short/en $T/swap/en $T/pages
    pdfseparate editions/010/render-2026-09-14T01-49-02/en/reader.pdf $T/pages/p-%03d.pdf
    pdfunite $T/pages/p-0{01..55}.pdf $T/short/en/reader.pdf
    seq -f "p-%03g.pdf" 1 56 | sed 's/p-010/SWAPA/; s/p-011/p-010/; s/SWAPA/p-011/' \
      | sed "s|^|$T/pages/|" | tr '\n' ' ' | xargs -J % pdfunite % $T/swap/en/reader.pdf
    cargo run --manifest-path mag/Cargo.toml -- parity 010 \
      --pre-rendered editions/010/render-2026-09-14T01-47-59 $T/short   # then $T/swap

Results: short (dropped last page): page_count fail 56 vs 55, exit 1,
later clauses not evaluated. swap (pages 10 and 11 swapped): page_count
and boxes pass, text fail on exactly 2 pages, Tier G structure mismatches
2, exit 1.

## Residuals

- Orchestrator grant recorded: the WP-0.2 preamble's "module registration,
  driver wiring" was read to cover the minimal `Parity` subcommand
  registration in mag/src/main.rs (enum variant + dispatch arm); nothing
  else there was touched.
- Verdict inputs are content digests (reader.pdf sha256), never paths, so
  verdict.json stays byte-deterministic regardless of where the compared
  trees live.
- `mag parity 010` without --pre-rendered fails loud naming WP-2.0b.
- Tier S clauses owned by later WPs (code_blocks, color, navigation,
  critic) are explicit not_evaluated entries naming their owners, never
  silent passes; exit code considers only evaluated clauses.
- The pdfinfo strip keys (dates, File size, trailer ID) are structurally
  honored: only Pages and the three plan-named boxes are extracted, so
  stripped fields never reach a comparison.
- baseline.json is the schema + empty state only; no page rows were written
  (verifier-only territory from here on).

## Status

done
