# WP-1.8 reconcile the third cross-spike line count

## Base

`74c8aae` (art_directed; plan revision 41).

Phase 1 spike: all instrumentation is uncommitted and lives in a throwaway
worktree, removed at WP end. This WP owns only this evidence file. No tracked
file changed. The one source change made to measure at all (WP-1.2's
`_dump_prose_lines` re-applied to `src/magazine/weasyprint_adapter.py`) is
reproduced by the command block below from WP-1.2's own evidence and is
reverted before landing.

## Summary

**The hypothesis did not survive, and the cause is named.** The standing
hypothesis was that WP-1.7's harness lacks the styled-run preservation that
took WP-1.2 from 147/149 to 148/149. Measured: the two harnesses are the same
program, they read a byte-identical input, and they produce the same number,
**147/149 paragraphs and 962/968 lines**. Neither reports 148/149.

The single cause of the disagreement is the comparison's **whitespace
normalization**, one line in a harness both spikes share:

```
def norm(seq):
    return [" ".join(s.replace("\xa0", " ").split()) for s in seq]
```

That collapses *runs* of whitespace but cannot remove an *inserted* space.
Replacing it with `return ["".join(s.split()) for s in seq]` and changing
nothing else moves **both** harnesses from 147/149, 962/968 to **148/149,
963/968**, reproducing WP-1.2's headline exactly. Removing the supposed cause
(styled-run preservation) instead leaves the paragraph count at 147/149.

The extra divergent block and extra differing line are therefore named:
**block 4, reader page 6, line index 5, at the 325.0000 pt measure**. It is not
an engine divergence. It is the `pdftotext -bbox-layout` word-segmentation
artifact at a font change that both spikes already recorded in prose: the
inline-code run `verification)` (Magazine Mono, 8.2 pt, weight 500) is followed
by a Magazine Serif 10 pt run, and poppler emits a word boundary there, so the
extracted line reads `verification) , which named the CVE ...` against
WeasyPrint's `verification), which named the CVE ...`. The first differing
character is index 13, exactly the run boundary, and the two lines are equal
once whitespace is removed.

So each spike's number is right about a different thing, and neither said
which: **WP-1.2 reports the artifact-corrected count, WP-1.7 reports the raw
harness count**, and WP-1.7's own delta table mixes the two (below).

## Commands

Replays from a fresh worktree at `## Base`. Every path is derived from the
checkout or from an environment variable; nothing absolute is written down.
Both helper scripts read only the checkout they are pointed at, and both
harnesses under test are EXTRACTED from the committed evidence files rather
than transcribed, so what runs is what WP-1.2 and WP-1.7 recorded.

Environment, announced rather than silent (rule 2b): the edition 010 run
directory is untracked and lives outside the repository, so `MAG_RUN_DIR` must
name it. The block prints which mode it took and exits non-zero if the corpus
is absent, because without the corpus there is no measurement here at all.

```sh
set -eu
CHECKOUT="$PWD"
WORK="${WP18_WORK:-${TMPDIR:-/tmp}/wp18-work}"
TYPST_INSTALL="${WP18_TYPST_INSTALL:-$WORK/typst-install}"
TYPST="$TYPST_INSTALL/bin/typst"
unset TYPST_ROOT
mkdir -p "$WORK"

if [ -z "${MAG_RUN_DIR:-}" ] || [ ! -d "${MAG_RUN_DIR:-}" ]; then
  echo "SKIPPED: MAG_RUN_DIR is not set to the edition 010 run directory"
  exit 1
fi
echo "MODE: measuring the live edition 010 corpus at $MAG_RUN_DIR"

if [ ! -x "$TYPST" ]; then
  cargo install typst-cli --locked --version 0.15.1 --root "$TYPST_INSTALL"
fi
"$TYPST" --version

RUN_NAME="$(basename "$MAG_RUN_DIR")"
[ -d "$CHECKOUT/editions/010/$RUN_NAME" ] || cp -R "$MAG_RUN_DIR" "$CHECKOUT/editions/010/"
(cd "$CHECKOUT/mag" && cargo build)
```

`unset TYPST_ROOT` is load bearing and is here because the replay found it:
the typst CLI reads `TYPST_ROOT` as its **project root**, so an exported
variable of that name, however innocently introduced to hold an install prefix,
makes every compile fail with `source file must be contained in project root`.
The install prefix is `WP18_TYPST_INSTALL`.

Re-apply WP-1.2's oracle instrumentation, taken from WP-1.2's evidence rather
than retyped:

```sh
cat > "$WORK/wp18_instrument.py" <<'PY'
import os
import pathlib
import re

CHECKOUT = pathlib.Path(os.environ["CHECKOUT"]).resolve()
FENCE = chr(96) * 3
PYBLOCK = re.compile("^" + FENCE + r"python\n(.*?)^" + FENCE + "$", re.S | re.M)
source = (CHECKOUT / "meta/verification/evidence/WP-1.2.md").read_text(encoding="utf-8")
call, func = PYBLOCK.findall(source)[0], PYBLOCK.findall(source)[1]
target = CHECKOUT / "src/magazine/weasyprint_adapter.py"
text = target.read_text(encoding="utf-8")
anchor = "    _report_hyphen_ladders(document, edition)\n"
marker = "def _walk_boxes(box: Any) -> Iterable[Any]:\n"
assert text.count(anchor) == 1 and text.count(marker) == 1
text = text.replace(anchor, call).replace(marker, func + "\n\n" + marker)
target.write_text(text, encoding="utf-8")
print("instrumented", target.relative_to(CHECKOUT))
PY

CHECKOUT="$CHECKOUT" uv run python "$WORK/wp18_instrument.py"
```

Produce the oracle dump and prove it is the same input both spikes measured:

```sh
(cd "$CHECKOUT" && MAG_LINE_DUMP="$WORK/wp18-weasy-runs.json" \
  ./mag/target/debug/mag render 010 --no-model --run "editions/010/$RUN_NAME" >"$WORK/wp18-render.log" 2>&1)
shasum -a 256 "$WORK/wp18-weasy-runs.json"
```

The digest must be
`e4ab672cefe221d06d2df1237e7663761a1e7c2f4311cb6d0d6a4f8581a7ac41`, which is
the digest WP-1.7 records for WP-1.2's dump. Same bytes, so the two spikes and
this one measured one population, not three.

The runner. It extracts the two harnesses from the evidence files, rewrites
only their three path constants (to the checkout's fonts, the work directory
and the typst binary) and their output-file tag, asserts no absolute path
survived, and then applies one named treatment at a time:

```sh
cat > "$WORK/wp18_run.py" <<'PY'
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

CHECKOUT = pathlib.Path(os.environ["CHECKOUT"]).resolve()
WORK = pathlib.Path(os.environ["WORK"]).resolve()
EVIDENCE = CHECKOUT / "meta/verification/evidence"
FENCE = chr(96) * 3
PYBLOCK = re.compile("^" + FENCE + r"python\n(.*?)^" + FENCE + "$", re.S | re.M)
NORM = re.compile(r'return \[" "\.join\(s\.replace\(.*?\)\.split\(\)\) for s in seq\]')
HOME = "/Users/"


def block(name, index):
    return PYBLOCK.findall((EVIDENCE / name).read_text(encoding="utf-8"))[index]


def retarget(src, tag):
    src = src.replace(
        'TMP = Path("/Users/franguijarro/.claude/jobs/7d99e27f/tmp")',
        'TMP = Path(os.environ["WORK"])',
    )
    src = src.replace('TYPST = TMP / "typst-install/bin/typst"', 'TYPST = Path(os.environ["TYPST"])')
    src = src.replace(
        'FONTS = TMP / "spike-wp12/src/magazine/assets/fonts"',
        'FONTS = Path(os.environ["CHECKOUT"]) / "src/magazine/assets/fonts"',
    )
    src = src.replace(
        'FONTS = Path("/Users/franguijarro/code/magazine/src/magazine/assets/fonts")',
        'FONTS = Path(os.environ["CHECKOUT"]) / "src/magazine/assets/fonts"',
    )
    src = src.replace('(TMP / "wp12-weasy-runs.json")', '(TMP / "wp18-weasy-runs.json")')
    src = src.replace("wp12d-", tag + "-").replace("wp17v-", tag + "-")
    assert HOME not in src, "absolute path survived retargeting"
    return "import os\n" + src


VARIANTS = {
    "flat": [
        (
            '                    "weight": int(r["weight"]), "font": FAMILY[r["family"]],'
            ' "size": round(r["size"] * PX_TO_PT, 4),\n'
            '                    "style": r["style"],\n',
            '                    "weight": 400, "font": FAMILY["Magazine Serif"],'
            ' "size": round(b["font_size"] * PX_TO_PT, 4),\n'
            '                    "style": "normal",\n',
        )
    ],
    "nosize": [
        (
            "    if False:\n        continue\n",
            '    if any(r["size"] != b["font_size"] for r in flat):\n        continue\n',
        ),
        (
            '                    "weight": int(r["weight"]), "font": FAMILY[r["family"]],'
            ' "size": round(r["size"] * PX_TO_PT, 4),\n',
            '                    "weight": int(r["weight"]), "font": FAMILY[r["family"]],'
            ' "size": round(b["font_size"] * PX_TO_PT, 4),\n',
        ),
        (
            "      text(font: r.font, size: r.size * 1pt, weight: r.weight, style: r.style, r.text)",
            "      text(font: r.font, weight: r.weight, style: r.style, r.text)",
        ),
    ],
}


def nospace(src):
    src, n = NORM.subn('return ["".join(s.split()) for s in seq]', src)
    assert n == 1
    return src


def patch(src, variant):
    for old, new in VARIANTS[variant]:
        assert src.count(old) == 1, (variant, old[:60])
        src = src.replace(old, new)
    return src


def run(label, source, args):
    source = retarget(source, label)
    path = WORK / (label + ".py")
    path.write_text(source, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(path), *args], cwd=WORK, capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr)
        raise SystemExit("harness %s failed" % label)
    misses = json.loads((WORK / (label + "-misses.json")).read_text())
    head = [ln for ln in proc.stdout.splitlines() if ln.startswith(("PARAGRAPHS", "LINES", "MISSES"))]
    print(
        "### %s  sha256=%s  argv=%s"
        % (label, hashlib.sha256(source.encode()).hexdigest()[:16], args)
    )
    for ln in head:
        print("   " + ln)
    for m in misses:
        bad = [i for i, (a, c) in enumerate(zip(m["weasy"], m["typst"])) if a != c]
        print(
            "   miss block %s w=%s styled=%s lines %d/%d differing=%s"
            % (m["key"], m["width"], m["styled"], len(m["weasy"]), len(m["typst"]), bad)
        )
    return misses


wp12 = block("WP-1.2.md", 2)
wp17 = block("WP-1.7.md", 1)
print("wp12 appendix sha256", hashlib.sha256(wp12.encode()).hexdigest())
print("wp17 verify   sha256", hashlib.sha256(wp17.encode()).hexdigest())

which = sys.argv[1] if len(sys.argv) > 1 else "all"
if which in ("all", "recorded"):
    run("wp18a-wp12-appendix", wp12, [])
    run("wp18b-wp17-verify-d0", wp17, ["0"])
if which in ("all", "hypothesis"):
    run("wp18c-wp17-flat", patch(wp17, "flat"), ["0"])
    run("wp18d-wp17-nosize", patch(wp17, "nosize"), ["0"])
if which in ("all", "nospace"):
    run("wp18f-wp12-appendix-nospace", nospace(wp12), [])
    run("wp18g-wp17-nospace-d0", nospace(wp17), ["0"])
if which in ("all", "deltas"):
    for d in ("0.000", "0.005", "0.010", "0.025", "0.039", "0.045"):
        tag = d.replace(".", "_")
        run("wp18h-strict-d" + tag, wp17, [d])
        run("wp18i-nospace-d" + tag, nospace(wp17), [d])
PY

export CHECKOUT WORK TYPST
(cd "$WORK" && uv run python wp18_run.py recorded)
(cd "$WORK" && uv run python wp18_run.py hypothesis)
(cd "$WORK" && uv run python wp18_run.py nospace)
(cd "$WORK" && uv run python wp18_run.py deltas)
```

Characterise block 4 and locate every named block by reader page:

```sh
pdftotext -layout "$(ls -d "$CHECKOUT"/editions/010/render-*/en/reader.pdf | tail -1)" "$WORK/wp18-reader.txt"

cat > "$WORK/wp18_block4.py" <<'PY'
import json
import os
import pathlib

WORK = pathlib.Path(os.environ["WORK"]).resolve()
dump = json.loads((WORK / "wp18-weasy-runs.json").read_text(encoding="utf-8"))
for key in ("4", "135", "137"):
    b = dump[key]
    print(
        "block %s tag=%s measure=%.4fpt families=%s"
        % (key, b["tag"], round(b["width"] * 0.75, 4), sorted({r["family"] for ln in b["runs"] for r in ln}))
    )
print("block 4 line 5 runs:")
for r in dump["4"]["runs"][5]:
    print("   %-16s weight=%-4s size=%.4fpx %r" % (r["family"], r["weight"], r["size"], r["text"]))
miss = [m for m in json.loads((WORK / "wp18b-wp17-verify-d0-misses.json").read_text()) if m["key"] == "4"][0]
w, t = miss["weasy"][5], miss["typst"][5]
print("weasy L5:", repr(w))
print("typst L5:", repr(t))
print("first differing index:", next(i for i, (a, c) in enumerate(zip(w, t)) if a != c))
print("equal with all whitespace removed:", "".join(w.split()) == "".join(t.split()))
pages = (WORK / "wp18-reader.txt").read_text(encoding="utf-8").split("\f")
for label, needle in (
    ("block 4 line 5", "named the CVE it was probing for"),
    ("block 135 line 0", "The Causal Encoder-Decoder handles the other half"),
    ("block 137 line 1", "reconstruction demands replaying"),
):
    print(label, "-> reader page", [i + 1 for i, p in enumerate(pages) if needle in p])
PY

WORK="$WORK" uv run python "$WORK/wp18_block4.py"
```

Revert the instrumentation (no `rm`, no path checkout):

```sh
(cd "$CHECKOUT" && git show HEAD:src/magazine/weasyprint_adapter.py > src/magazine/weasyprint_adapter.py && git status --porcelain src/magazine/weasyprint_adapter.py)
```

## Tool versions

| tool | version |
|---|---|
| typst (CLI, spike only) | 0.15.1 |
| weasyprint | 69.0 (via the repo's `uv` environment) |
| poppler (`pdftotext`) | 25.08.0 |
| python | 3.12.11 (`uv run python`) |
| uv | 0.8.17 |
| rustc / cargo | 1.96.0 |

## Metrics

**Configuration carried by every number below (rule 9).** Corpus: edition 010
English, run directory `run-2026-09-13T01-34-51`, staged by
`mag render 010 --no-model`. Oracle leg: WeasyPrint 69.0 under the tracked CSS
at `74c8aae`, i.e. English prose **hyphenation OFF** through WP-1.5's
`html:lang(en)` block; instrumented with WP-1.2's `_dump_prose_lines`.
Population: the 155 keyed blocks of the dump, of which the **149 `p` blocks
(968 lines)** are compared and the 6 `span` blocks (6.8 pt) are excluded, as in
both spikes. Input digest
`e4ab672cefe221d06d2df1237e7663761a1e7c2f4311cb6d0d6a4f8581a7ac41`, identical
to the dump WP-1.2 produced and WP-1.7 reused. Typst leg: typst CLI 0.15.1,
`linebreaks: "simple"`, `justify: false`, `hyphenate: false`, `leading: 3.5pt`,
three measure groups at 325.0000 / 311.0000 / 312.1614 pt plus the delta named
in the row. Break sets extracted with `pdftotext -bbox-layout`. Units: whole
paragraphs (blocks) and lines.

### 1. The two recorded harnesses, run on that one population

| harness | extracted from | sha256 of the extracted block | delta | paragraphs | lines | misses |
|---|---|---|---|---|---|---|
| WP-1.2 appendix (`wp12_compare4.py`) | `WP-1.2.md` python block 2 | `ee02136dd6b7ca780f7b751004917f5ed75b9de60c1b22d78d7e02c1e6fa00ca` | +0.000 | **147/149** | **962/968** | 4, 135 |
| WP-1.7 section 3 (`wp17_verify.py`) | `WP-1.7.md` python block 1 | `1900b2be7941e0a4485d085ad2117a80b9bba9520a912e8e6aa9b6cc7011595d` | +0.000 | **147/149** | **962/968** | 4, 135 |

The two harnesses agree exactly, miss for miss. **The disagreement is not
between the spikes' harnesses.** It is between WP-1.2's recorded harness and
WP-1.2's own headline table, which reports 148/149 and 963/968.

### 2. The hypothesis, tested by removing the supposed cause (rule 11)

Each row is the WP-1.7 harness with exactly one named treatment changed and
everything else held fixed, at delta +0.000.

| treatment | paragraphs | lines | miss set |
|---|---|---|---|
| as recorded (styled runs preserved) | 147/149 | 962/968 | 4, 135 |
| **styled-run preservation REMOVED** (every run forced to Magazine Serif 400 normal at the block's own size) | **147/149** | 960/968 | 39, 135 |
| WP-1.2's earlier size-exclusion treatment (blocks carrying a run at a size other than the block's are dropped; per-run size not emitted) | 146/**147** | 937/**942** | 135 |

**The hypothesis is falsified.** Removing styled-run preservation does not move
the paragraph count at all: 147/149 with it, 147/149 without it. It cannot
explain a 147-versus-148 difference in either direction, and WP-1.7's harness
does not lack it in the first place, being the same program as WP-1.2's.

Two things worth having in the record. First, the two extremes give the same
count while the miss *set* changes completely, 4 and 135 against 39 and 135:
the count alone cannot discriminate here, only the enumeration can, which is
rule 9's point about deriving a count from its list. Second, this is very
likely where the hypothesis came from. WP-1.2 records the styled-run fix as
"improved from 147/149 to 148/149"; measured, the fix repairs block 39 and
simultaneously introduces block 4, so the 147 before and the 147 after are two
different 147s, and the 148 came from somewhere else entirely.

The size-exclusion row rules out the other candidate for free: it changes the
POPULATION, to 147 blocks and 942 lines, so its numbers are not comparable to
either spike's and cannot be the source of a 149-block, 968-line 148/149.

### 3. The cause, established by adding it and measuring the move

One line changed, the comparison's whitespace normalization, everything else
held fixed, delta +0.000:

| harness | `norm` treatment | paragraphs | lines | miss set |
|---|---|---|---|---|
| WP-1.2 appendix | collapse whitespace runs (as recorded) | 147/149 | 962/968 | 4, 135 |
| WP-1.2 appendix | remove whitespace entirely | **148/149** | **963/968** | 135 |
| WP-1.7 section 3 | collapse whitespace runs (as recorded) | 147/149 | 962/968 | 4, 135 |
| WP-1.7 section 3 | remove whitespace entirely | **148/149** | **963/968** | 135 |

Both spikes' headline numbers are produced by one harness under two
normalizations. The effect moves when the treatment is added and returns when
it is removed, on both harnesses, which is the test rule 11 asks for.

### 4. The named block and the named line

| what | where |
|---|---|
| the extra divergent block | block **4**, reader page **6**, measure **325.0000 pt**, 12 lines |
| the extra differing line | line index **5** of that block |
| WeasyPrint | `verification), which named the CVE it was probing for rather than` |
| Typst via `pdftotext -bbox-layout` | `verification) , which named the CVE it was probing for rather than` |
| first differing character | index **13**, exactly the run boundary |
| equal with all whitespace removed | **yes** |
| the run boundary | `verification)` in Magazine Mono (Geist Mono) at 10.9333 px = 8.2 pt, weight 500, followed by Magazine Serif (Source Serif 4 SmText) at 13.3333 px = 10 pt, weight 400 |

The block is one of the two inline-code paragraphs WP-1.2's residual 4 names.
No word crosses a line boundary: the difference is a space poppler emits at the
font change, so no break point differs and the count of lines is the same on
both sides. This is the artifact both spikes describe in prose; what neither
did was say which of its numbers had been corrected for it.

The residual genuine divergence at delta +0.000 is unchanged and is WP-1.2's
known one: **block 135, reader page 47, measure 325.0000 pt, all 5 lines
displaced**, whose 325.01 pt measured width against a 325 pt column WP-1.2 and
WP-1.6 both characterise. Block 137, reader page 48, is WP-1.7's upper-bound
witness and appears as a miss only at +0.045 among the six deltas measured
here.

### 5. WP-1.7's delta table, re-measured under both normalizations

| delta | WP-1.7 records | as recorded (collapse) | whitespace removed | miss set, collapse | miss set, removed |
|---|---|---|---|---|---|
| +0.000 | 147/149, 962/968 | **147/149, 962/968** | 148/149, 963/968 | 4, 135 | 135 |
| +0.005 | 147/149, 962/968 | **147/149, 962/968** | 148/149, 963/968 | 4, 135 | 135 |
| +0.010 | 149/149, 968/968 | 148/149, 967/968 | **149/149, 968/968** | 4 | none |
| +0.025 | 149/149, 968/968 | 148/149, 967/968 | **149/149, 968/968** | 4 | none |
| +0.039 | 149/149, 968/968 | 148/149, 967/968 | **149/149, 968/968** | 4 | none |
| +0.045 | 147/149, 963/968 | **147/149, 963/968** | 148/149, 964/968 | 4, 137 | 137 |

Bold marks which column WP-1.7's recorded row matches. **Its table mixes the
two normalizations**: the three rows inside the interval are the
whitespace-removed numbers, the three outside it are the collapse numbers. That
is the same slip as WP-1.2's, one row at a time instead of once, and it is why
WP-1.7's prose ("comparison is space-insensitive ... block 4 only; all 12 of
its lines are space-insensitively identical at every delta") reads as true
while its delta-0 number is the space-sensitive one.

Block 4 is a miss under the collapse treatment at **every** delta measured,
including the three inside the interval. The artifact is constant in the
column width, as a font-change segmentation artifact should be, which is the
independent check that it is not a width-dependent break effect.

**WP-1.7's conclusion is unaffected.** The interval is set by block 135 below
and block 137 above; block 4 contributes a constant single-line offset at every
delta and can move neither bound. At the six deltas WP-1.7 tested, whitespace
removal reproduces its table row for row, 149/149 inside the window and a real
block outside it on both sides; under the collapse treatment the same two
blocks bound the same window, one paragraph lower throughout. The exclusive
upper endpoint +0.040000 itself was not re-measured here, only the +0.039 and
+0.045 witnesses either side of it. Nothing about the recommended +0.025000 pt
changes.

## Verdicts

No `verdict.json`: this is a Phase 1 spike and runs no comparator. The binding
artifacts are the input digest
`e4ab672cefe221d06d2df1237e7663761a1e7c2f4311cb6d0d6a4f8581a7ac41`, the two
extracted-harness digests in the table above, and the miss enumerations, each
of which the command block regenerates.

## What is and is not proven

**PROVEN**

- **The two spikes' harnesses produce the same number on the same input.**
  Proved by extracting both programs from the committed evidence files and
  running them on one dump whose sha256 matches the digest both spikes record.
  Discrimination: the runner asserts that no absolute path survives
  retargeting, so a harness silently reading the other spike's scratch files
  would fail rather than pass; and the same runner, given one changed line,
  produces a different number from the same programs, so it is not reporting a
  constant.
- **The whitespace normalization is the cause.** Proved by changing that one
  line, on both harnesses, and measuring the count move 147/149 to 148/149 and
  962/968 to 963/968, then back. Discrimination: whitespace removal is not a
  blanket pass. It still reports block 135 as a miss at delta +0.000 and block
  137 at +0.045, so it fails on real break divergences and only absorbs the
  segmentation artifact.
- **The styled-run hypothesis is false.** Proved by removing styled-run
  preservation from WP-1.7's harness and measuring 147/149, unmoved.
  Discrimination: the removal is not inert, it changes the line count
  (962 to 960) and the entire miss set (4, 135 to 39, 135); it simply does not
  move the paragraph count. Per rule 10, both extremes were run, and both
  giving 147 is reported as the result rather than read as agreement.
- **The extra divergent block and line are named and characterised**: block 4,
  reader page 6, line index 5, 325.0000 pt measure, differing from character 13
  at the Geist Mono to Source Serif run boundary, equal once whitespace is
  removed.
- **WP-1.7's interval and recommendation stand.** Proved by re-measuring all
  six deltas under both treatments: the bounds are set by blocks 135 and 137
  under either, and block 4 offsets every row equally.

**NOT PROVEN**

- **That the segmentation artifact is poppler's rather than typst's output.**
  The measurement shows the extracted text carries a space the source runs do
  not and that no break point moves; it does not open the PDF content stream to
  show where the word boundary is decided. It does not matter for any count
  here, and WP-2.3 will measure Typst line breaks through the engine's own
  layout result rather than through `pdftotext`, which retires the question
  instead of answering it. Owner: WP-2.3.
- **That no other recorded number in Phase 1 mixes normalizations.** Only
  WP-1.2's and WP-1.7's break-set counts were re-measured. WP-1.1, WP-1.3 and
  WP-1.6 report different quantities through different instruments and were not
  touched. Nobody currently owns auditing them; recorded here as the finding
  rather than assumed clean.
- **That WP-1.2's intermediate scripts are exactly what I reconstructed.** The
  "styled-run preservation removed" row is a minimal single-treatment removal
  from the recorded harness with the population held fixed, not a replay of
  WP-1.2's earlier `wp12_compare.py`, which also narrowed the population. The
  claim proved is about the treatment, not about that script.
- **Anything about hyphenation on.** Every number here is hyphenation off for
  English, per the tracked CSS at `74c8aae`. WP-1.2's residual 3 stands.

## Residuals

1. **The reconciled delta-0 figures, for anyone citing them.** The 149-block,
   968-line population at the unwidened measure gives **147/149 and 962/968**
   as the harness reports it, and **148/149 and 963/968** once the
   `pdftotext` font-change artifact on block 4 is removed. Both are correct;
   neither is quotable without saying which. The engine-level fact both
   express is one divergent block, block 135, five displaced lines.
2. **A `pdftotext`-based break comparison needs whitespace-removing
   normalization, and both spikes' harnesses do not have it.** Collapsing
   whitespace runs cannot remove an inserted space. Any later WP reaching for
   these harnesses should change `norm` to `["".join(s.split()) for s in seq]`
   and say so, or use an instrument that does not re-segment words.
3. **The count-beside-an-enumeration slip has now produced all three
   cross-spike disagreements.** In each, a table carried a number that its own
   recorded enumeration did not produce. Rule 9's second paragraph covers it
   for prose enumerations; these were metric tables, where the enumeration
   lives in a miss file rather than in the text. A cheap habit that would have
   caught all three: print the miss enumeration next to the count in the
   evidence, as section 1 above does.
4. **WP-1.7's Verify-clause sentence should be read as
   whitespace-insensitive.** "968/968 lines" at the recommended midpoint is
   true under whitespace removal and reads 967/968 under the treatment its
   recorded harness carries. The recommendation and the interval are
   unaffected; only the sentence's configuration was missing.
5. **`TYPST_ROOT` is the typst CLI's project root, not a spare name.** Phase 1
   drives typst through the standalone CLI, and any harness run with that
   variable exported fails every compile with `source file must be contained in
   project root`, which reads like a path bug in the harness. The command block
   above unsets it. Found by the rule-12 replay, not by the authoring run,
   which had no such variable in its environment.
6. **No source change is proposed by this WP.** The harness edits exist only
   to measure and are not committed. If a later WP wants the corrected
   normalization permanently, it owns that change.

## Status

`done`. The two counts reconcile with a stated cause, established by removing
and re-adding it and measuring the move; the standing hypothesis was tested and
falsified; and the extra divergent block and line are named with their page,
measure and character offset.
