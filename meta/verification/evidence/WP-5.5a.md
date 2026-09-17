# WP-5.5a web edition

## Base

e639b32433877dd87d981b151c50a31624b779ed (plan revision 26)

## Status

blocked

Blocked on a plan decision, not on feasibility of the web port itself. The QR
half is a sub-project, and the plan's own instruction was to say so with the
measurement rather than half-build it. No Rust was written; no Cargo change.

The blocker is stated first because it decides the shape of the whole WP: the
oracle is a byte-identical `web/` tree, the nine QR SVGs are in that tree, and
reproducing them byte-for-byte requires reproducing a segno behaviour that is
not ISO/IEC 18004.

## Metrics

### The error-level boost is reproducible, which was the feared part

The plan records segno boosting the requested `error="L"` on 6 of 9 payloads.
Confirmed exactly, and the boost is NOT the obstacle: `qrcodegen`'s
`boost_ecl` reproduces segno's chosen version AND effective error level on
**9 of 9**.

| effective level | version | mask (segno) | payload len | source id |
|---|---|---|---|---|
| M | 4 | 2 | 62 | government-rails-site-hit-hours-after-cve-patch |
| M | 4 | 7 | 55 | countering-misuse-of-ai-september-2026-anthropic |
| L | 4 | 2 | 67 | an-alignment-assessment-of-recent-cybersecurity |
| L | 3 | 7 | 46 | dario-amodei-we-must-pace-the-frontier |
| M | 3 | 5 | 38 | scenarios-for-our-economic-future |
| M | 2 | 3 | 25 | the-third-era-of-ai-software-development |
| M | 3 | 5 | 38 | towards-self-driving-codebases |
| L | 3 | 2 | 46 | deepseek-v4-1-flash-pushing-the-limits-of-kv-cache |
| M | 4 | 7 | 60 | rapidly-scaling-online-storage-to-serve-over-1-b |

All nine are BYTE mode, as the plan states. Mode segmentation is not a
variable: seven payloads contain no digits at all.

### The matrices are NOT reproducible, and the cause is below the mask

Automatic encoding, `qrcodegen` against segno: **1 of 9 matrices match**.
Masks differ on 7 of 9.

Forcing segno's version, error level AND mask, so only the data layer can
differ: still **1 of 9 match**, 8 differing by 64 to 144 modules. So the
divergence is in the encoded bitstream, not in mask selection.

### Mechanism, tested per rule 11 rather than asserted

Controlled experiment at forced v4-M, same mask, varying only whether the
data stream needs pad codewords:

| case | pad bytes needed | modules differing |
|---|---|---|
| payload `"a" x 62` | none (terminator exactly fills capacity) | **0** |
| payload `"a" x 50` | 12 pad codewords | 158 |

Removing the supposed cause removes the effect. The mechanism is then visible
in `segno/encoder.py:330` `write_padding_bits`:

    buff.extend([0] * (8 - (length % 8)))

When the stream is ALREADY at a codeword boundary this appends **8 spurious
zero bits**, where ISO/IEC 18004 §7.4.10 adds none ("if the bit stream length
is such that it does not end at a codeword boundary"). segno's own docstring
quotes that clause directly above the line that violates it.

In byte mode the stream after a 4-bit terminator is `16 + n*8` bits, which is
always ≡ 0 mod 8, so segno ALWAYS injects one extra zero byte unless remaining
capacity forces the terminator to truncate. That extra byte displaces one pad
codeword and changes every ECC codeword, which is why the differences are
large and why the only natural match (`government-rails`, 508 data bits
against a 512-bit capacity) is the one case with no room for it.

Prediction tested on three FRESH cases not used to form the hypothesis, at
v4-M:

| payload | predicted | modules differing |
|---|---|---|
| `"a" x 62` (terminator truncated, no room) | MATCH | **0** |
| `"a" x 61` (room for the spurious byte) | DIFF | 68 |
| `"a" x 60` (room for the spurious byte) | DIFF | 82 |

Predicted correctly in all three.

### What this means for the oracle

Byte-identical QR SVGs are not reachable with an ISO-correct Rust encoder,
and neither is the plan's PRIMARY structural oracle, module-matrix equality,
because the matrices themselves differ. Both oracles fail for the same
reason.

Three dispositions, none of which a WP may choose alone:

1. Reproduce segno's spurious pad byte deliberately in a Rust encoder. This
   is the "reproduce a hack to stay equal to a tool we are deleting" category
   the plan has now rejected four times (WP-5.7's pypdf text layer, the
   `_check_unique_art` crash, the critic's text source, reportlab's
   subsetting). It is also narrower than those: one documented deviation from
   a published spec, in an encoder that is otherwise standard, and it would be
   asserted by a test rather than inferred. That makes it the cheapest option
   and the one most in tension with the plan's stated principle.
2. Restate the oracle as the plan's own fallback already anticipates:
   "byte-identical except the nine QR SVGs, which are structurally equal",
   where structurally equal means SAME PAYLOAD, VERSION AND EFFECTIVE ERROR
   LEVEL — but explicitly NOT the same module matrix, since mask and data
   layer both differ. Note this is weaker than the fallback the plan wrote,
   which assumed matrix equality would hold.
3. Keep calling segno. This defeats WP-6.1's target of no Python anywhere and
   the plan rejects it for `pdf2md.py` already.

Option 2 needs one decision the plan has not yet faced: the QR codes are
SCANNED BY READERS, so "decodes to the same URL at a legitimate error level"
may be the property that actually matters, and matrix equality may be the
wrong bar rather than an unreachable one. That is a product judgment about
what the web edition guarantees, not a verification judgment.

## Commands

All Python via `uv run python` (this machine has a second Python 3.9.6 on
Unicode 13.0.0; a bare `python3` gives different answers).

Dump segno's matrices for 010's nine opener sources:

    cd <worktree> && uv run python -c '
    import sys, yaml, json
    sys.path.insert(0, "src")
    import segno
    from magazine.manifest import source_code_payload
    ed = yaml.safe_load(open("editions/010/edition.yaml"))
    rows=[]
    for a in ed["articles"]:
        if a.get("opener_art") is None: continue
        sid = (a.get("source_ids") or [a["id"]])[0]
        rec = yaml.safe_load(open(f"library/sources/{sid}/record.yaml"))
        if not rec.get("url"): continue
        if any(r[0]==sid for r in rows): continue
        rows.append((sid, rec["url"]))
    out=[]
    for sid, url in rows:
        p = source_code_payload(url)
        q = segno.make(p, error="L", micro=False)
        m = ["".join("1" if c else "0" for c in row) for row in q.matrix]
        out.append({"sid": sid, "payload": p, "error": str(q.error),
                    "version": q.version, "mask": q.mask, "size": len(m), "matrix": m})
    json.dump(out, open("/tmp/segno_matrices.json","w"))
    print("dumped", len(out))'

The Rust probe is a throwaway cargo project depending on `qrcodegen = "1.8"`
and `serde_json = "1"`, reading that JSON and calling
`QrCode::encode_segments_advanced(&segs, ecc, v, v, mask, boost)` with
`boost=true` for the automatic comparison and `boost=false` plus segno's
version and mask for the forced-parameter comparison. Full source is in
`## Residuals`; it adds nothing to `mag/` and was not committed.

Controlled padding experiment: same probe against `segno.make("a"*62,
error="M")` and `segno.make("a"*50, error="M")`, forcing each one's own
version and mask.

## Tool versions

- segno 1.6.6
- Python 3.12.11 (`uv run python`)
- qrcodegen 1.8.0
- rustc 1.96.0

## Verdicts

No parity verdicts produced; this WP wrote no Rust and ran no render.

## Residuals

- **The non-QR half of the port is untouched and unblocked.** `web_edition.py`
  is 755 lines and `html_edition.py`'s web path is part of 875; none of it
  depends on HOW the QR SVGs are produced, only on their filenames. Whoever
  resumes this can build it against any of the three dispositions. I did not
  build it because the WP's oracle is the byte-identical tree and that oracle
  is what is undecided; building 700 lines against an undecided bar risks
  shaping the module around a decision that then changes.
- **Four brittle matchers inherited from WP-0.0c are NOT yet ported**:
  `_PRINT_ONLY_LINE`, `_SOURCE_LINK_LINE`, `_PIECE_OPENING` and
  `_ILLUSTRATED_OPENER_HEADER` (which still requires the class to be exactly
  `article-opener`). All four recognise markup by exact spelling. They remain
  this WP's obligation, to be ported as structural tests with fixtures
  carrying an extra unrelated attribute.
- **segno's pad-bit deviation is worth reporting upstream** and is not
  specific to this project: any encoder comparing against segno will hit it.
  It is reproducible in three lines.
- **The probe source** (throwaway, not committed):
  `Cargo.toml` with `qrcodegen = "1.8"`, `serde_json = "1"`; `src/main.rs`
  reads the dumped JSON, rebuilds each code with
  `QrSegment::make_segments(payload)` and
  `QrCode::encode_segments_advanced`, renders the matrix with
  `qr.get_module(x, y)`, and counts differing modules.
- **Cargo.lock only-gained check: not applicable.** No crates were added to
  `mag/`; the probe lived outside the repository.
- No f32 exposure: this WP did no arithmetic on lopdf-parsed numbers.
