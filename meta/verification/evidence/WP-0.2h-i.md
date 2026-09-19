# WP-0.2h-i the shared tracer seam, made reachable and proved by a test that can fail

## Base

`d23a75b` (`verify(typeset): WP-2.2a rejected, the folio is wrong past page
9`), branch `art_directed`. Worked in `git worktree add --detach
<scratch>/wp02hi art_directed`; the branch is checked out in the main tree, so
a named-branch worktree is refused and the detached form is the only one
available. Rebased for landing onto `2a57ebf` (`feat(critic): WP-5.3b-iii
void geometry, tail bands, openers and the 31 checks`), after two earlier
compare-and-swaps were refused by a moving tip. Of the eleven commits between
the two, only WP-5.3b-iii touches this WP's concern set: it adds `pub mod
rules;` to `mag/src/critic.rs`, which rebased without conflict above the
test module, and it adds `mag/tests/critic_rules.rs`, whose `#[path]`
includes name `critic/metrics.rs`, `critic/text.rs`, `critic/inspect.rs` and
`critic/rules.rs` but not `critic.rs`, so block 1's sibling counts rise and
its first grep stays empty. None touches `mag/src/parity.rs`. The Commands
blocks were replayed at the rebased commit, not the original.

## Files touched

Named explicitly rather than by glob, per the brief:

- `mag/src/parity.rs` (visibility only, one line)
- `mag/src/critic.rs` (the `#[cfg(test)]` consumer module)
- `meta/verification/evidence/WP-0.2h-i.md` (this file)

Nothing under `mag/src/typeset/`, `mag/src/critic/rules.rs`, `mag/src/web/`,
`mag/src/model/` or `mag/tests/cover_*` was read for edit or written. The
staleness, ratchet, cardinality and verdict paths of `parity.rs` are
untouched; the diff against `d23a75b` for that file is exactly one line.

## What the blocker actually was, re-derived

The brief states `mag/src/parity.rs` declares `mod display;` and `mod streams;`
privately **with no `pub use`**. That is no longer accurate, and rule 9 binds
at the point of citation, so it is corrected here rather than inherited.

At `d23a75b`, `mag/src/parity.rs:17-20` reads:

```rust
pub(crate) use display::trace_elements;
#[allow(unused_imports)]
pub(crate) use streams::Color;
pub(crate) use streams::{Element, Face as TextFace, GLYPH_QUANTUM};
```

Those item re-exports accumulated in three separate commits, each adding only
what its own author needed at that moment:

- `e5e741a` (WP-2.0b) added `trace_elements` and `{Color, Element, Face as
  TextFace}`.
- `26391ab` (WP-5.3b-i) split the `Color` line out under
  `#[allow(unused_imports)]`.
- `80b7b62` (WP-5.3b-i rework) added `GLYPH_QUANTUM`.

So blocker 1 had already been **partially** closed by accretion, and two
real consumers already compile against the seam today:
`mag/src/critic/text.rs:7` and `mag/src/main.rs:377`. What remained blocked
was narrower than the brief describes, and is stated in the next section.

Two things about that accretion are worth recording, because they are why the
blocker stayed open while looking closed. First, nothing in the crate stated
what the seam was *for*, so each WP widened it by the single item in front of
it. Second, `mag/src/main.rs:377` already carries a `#[cfg(test)] mod
parity_text_seam_is_reachable`, added by `e5e741a`. It is in-crate and it does
resolve `crate::parity::` against the real tree, so it is not a `#[path]`
demonstration. But it imports only `{trace_elements, Element, TextFace}` and
asserts only that a missing PDF errors; it pins the three items that already
worked and could never have detected that `qc` and `qo` did not. A reachability
test that only names the reachable items is not a reachability test. That is
the residue of WP-0.2h's mistake surviving in a different form from the one
the brief names.

## The narrowest visibility change

The obligation was to find the narrowest form that lets a real consumer import
what it needs. Measured against the parity items that `mag/src/critic/`'s
existing tests actually touch, namely `streams::{qc, qo, Color, Element, Face}`,
`streams::GLYPH_QUANTUM` and `display::trace_elements`, read out of
`mag/tests/critic_text.rs` and `mag/tests/critic_inspect.rs`, exactly two are
unreachable from `crate::parity::`: the quantizers `qc` and `qo`. A consumer
that must build `Element::Text` fixtures cannot build them without the same
quantizers the tracer used, and `Element`'s fields are raw quantized integers,
so this is a genuine need and not a contrivance.

The change is therefore one line:

```
-pub(crate) use streams::Color;
+pub(crate) use streams::{qc, qo, Color};
```

`mod display;` and `mod streams;` remain **private**. No module is re-exported
wholesale, no item gains `pub`, and the crate's external surface (there is no
`[lib]` target; `mag/Cargo.toml` declares one `[[bin]]`) is unchanged. It rides
on the existing `#[allow(unused_imports)]` because `qc` and `qo` are consumed
only from `#[cfg(test)]` code, exactly as `Color` already was.

This is narrower than I expected to be able to get away with, so per the brief
I record the alternative I did **not** take: `pub(crate) mod streams;` would
have been one line too and would have made every one of the 30-plus items in
that 1298-line module crate-visible. It is rejected. The seam should name what
it exports.

## Where the consumer test could live, and why

The coordinator's mid-flight constraint applies directly: a `#[cfg(test)]`
module inside a `#[path]`-included file compiles into the *including* binary,
where `crate::` names that binary's root, so it would prove nothing about
`mag`'s module graph. Measured at `d23a75b`, every file in `mag/src/critic/`
is included by at least one integration test:

| file | `#[path]` includes of it in `mag/tests` |
| --- | --- |
| `mag/src/critic.rs` | 0 |
| `mag/src/critic/text.rs` | 2 |
| `mag/src/critic/inspect.rs` | 1 |
| `mag/src/critic/metrics.rs` | 6 |

`mag/src/critic.rs`, the critic module root, is the only file in critic
territory that no `#[path]` includes, so it is where the test goes. It is a
real consumer home rather than an artificial one: it is the node the critic's
own `use crate::parity::...` lines hang off. Block 1 of the Commands section is the
grep that makes this checkable by a later reader, who otherwise cannot tell
the difference between this file and any other.

The rule's other half holds too: the new module uses `crate::` and lives in a
file included by nobody, so it does not become the first `use crate::` inside
an included file's test module.

## Both directions

**Red.** With the consumer test written and `parity.rs` untouched,
`cargo test --bin mag` does not compile:

```
error[E0603]: module `display` is private
 --> src/critic.rs:8:24
  |                        ^^^^^^^ private module
 --> src/parity.rs:1:1
error[E0603]: module `streams` is private
 --> src/critic.rs:9:24
  |                        ^^^^^^^ private module
 --> src/parity.rs:5:1
error[E0603]: module `streams` is private
 --> src/critic.rs:9:24
  |                        ^^^^^^^ private module
 --> src/critic.rs:9:49
 --> src/parity.rs:5:1
error: could not compile `mag` (bin "mag" test) due to 3 previous errors
```

That is blocker 1's own error text, produced by an in-crate consumer, which is
the thing WP-0.2h's `#[path]` include could not produce. Block 3b of the
Commands section reproduces that exact text from the landed tree by rewriting
the import back to the module-path spelling; block 3a shows the other spelling
of the same failure, `E0432`, by reverting the one-line seam change instead.

**Green.** With the seam change applied and the import rewritten to the flat
`use crate::parity::{qc, qo, trace_elements, Color, Element, TextFace,
GLYPH_QUANTUM};`, all three tests pass (block 2).

An intermediate failure is worth recording because it shows the test is not
compile-only theatre: the first green build failed at runtime on
`critic_joins_elements_built_with_the_seams_quantizers`, `left: "ab cd"`,
`right: "abcd"`, because the fixture builder divided the advance by the font
size rather than by `glyphs - 1`. The seam compiled; the assertion still
caught a wrong fixture.

## What would make the guard fail

- Removing `qc` or `qo` from the `parity.rs` re-export, or making the seam's
  exports reachable only through a wholesale `pub(crate) mod`, fails
  compilation with `E0603` or `E0432`, the red direction above, which is the
  committed case.
- `the_quantizers_reached_through_the_seam_are_the_tracers_own` fails at
  runtime if the `qc`/`qo` reached through `crate::parity::` are not the ones
  `streams` quantizes with: it pins `qc(1.0) == 100` and
  `qo(GLYPH_QUANTUM * 8.0) == 8`, so a re-export aliased to a differently
  scaled quantizer flips it without touching compilation.
- `critic_joins_elements_built_with_the_seams_quantizers` fails at runtime if
  the element model or the quantizer scale changes under the critic's join
  rule: it commits one pair 8.0 pt apart (a space) and one pair 1.0 pt apart
  (no space) against a 2.5 pt threshold, so a scale error in either direction
  flips one of the two.
- `the_trace_entry_point_is_callable_from_critic` fails if `trace_elements`
  stops being callable from outside `parity`, or stops naming the offending
  path in its error.

## What this evidence cannot discriminate

- It cannot show that the seam exports *enough* for consumers that do not yet
  exist. It shows the seam covers every parity item `mag/src/critic/`'s
  current tests touch; the next consumer may still need a thirty-first item,
  and the accretion pattern recorded above is the
  reason to expect that.
- It cannot distinguish "the module tree is right" from "the module tree is
  right *for the `mag` binary target*". There is no `[lib]` target, so there is
  no second compilation of this tree to disagree with.
- It cannot tell whether `mag/src/critic.rs` will still be `#[path]`-free
  later. Block 1's grep is a measurement taken now, not an enforced invariant;
  nothing in the repository fails if a future test includes `critic.rs` and
  silently moves this test into a foreign crate root. Making that an enforced
  check is named under Residuals below.
- One replay of block 4 at an earlier rebase (`f9de740` on `3449552`)
  reported `test failed, to rerun pass --test cover_modes` under the full
  concurrent suite; `cargo test --test cover_modes` then passed 14/14 in
  isolation both at that commit and at `3449552` without this WP's commit,
  and the full suite passed at `d23a75b` plus this change. `cover_modes`
  includes only `critic/metrics.rs`, which this WP does not touch. The
  evidence cannot tell a one-off flake from load sensitivity in that
  suite; it can say the failure is not reachable from this diff.
- The three tests are reachability and composition guards, not algorithm
  tests. They do not re-verify the join rule, the tracer, or the quantizers'
  correctness against the Python oracle; `mag/tests/critic_text.rs` still owns
  that.

## Retirement of the `#[path]` workarounds: reported, not done

The brief asks whether WP-5.3b-i's and -ii's `#[path]` includes can now be
retired. **They cannot be retired in place, and the reason is structural
rather than a matter of the seam.**

`mag/tests/critic_text.rs` and `mag/tests/critic_inspect.rs` are integration
tests. Each compiles as its **own crate**, and an integration-test crate can
only reach the tested code through a `[lib]` target's `pub` surface. There is
no `[lib]` target. Revision 62 decided against one, and correctly, since every
item at issue is `pub(crate)` or narrower and a library exposes only `pub`. So
for those two files `#[path]` is not a workaround for the seam at all; it is
the only mechanism by which an integration test can see the code. Making the
seam reachable does not change that, and no amount of widening it would.

What *is* now possible is a different move: those tests could be **relocated**
in-crate as `#[cfg(test)]` modules, at which point they would use the seam and
the `#[path]` preamble would disappear. That is a migration, and revision 62
explicitly rules it out: the 51 includes stay, they are genuine algorithm
tests, and rewriting them buys churn rather than verification. I agree, with
one qualification worth putting in front of the planner: those two files' mode
of use is not the same as the other 49. Their preambles rebuild a **fake
module tree**, `mod parity { pub use super::display::trace_elements; ... }`,
`mod critic { pub use super::{metrics, text}; }`, and WP-5.3b-iii's
`mag/tests/critic_rules.rs` repeats the same shim a third time, precisely so that
`critic/text.rs`'s and `critic/inspect.rs`'s real `use crate::...` lines
resolve. That shim is a hand-maintained replica of the module graph, and
nothing checks it against the real one. If `parity.rs`'s re-exports and the
shim ever disagree, the tests keep passing while testing a different tree.
This WP's test is the thing that would now catch that class of drift for the
parity seam specifically, and it is the argument for eventually relocating
those two files even though today's answer is to leave them alone.

No file under `mag/tests/` was modified.

## Commands

Every block below was extracted programmatically from this file and executed
in a clean shell from a directory that is not the one the work was developed
in. `$PWD` is the repository checkout root.

The extractor must anchor the section headers to the start of a line, `^##
Commands$` through `^## Residuals$` under `re.MULTILINE`, and take the
` ```sh ` fences inside. A first attempt that split on the bare strings
silently produced zero blocks, because the phrase `## Residuals` also occurred
inside backticks in the prose above and truncated the section before it began.
Those in-prose occurrences have been removed, so `grep -n '^## '` now lists
every header exactly once, but the anchored form is the one to use.

Block 1, the placement check. `mag/src/critic.rs` must appear in **no**
`#[path]` include. Empty output from the first grep is the passing result, and
because an empty grep and a grep that failed to run look alike, the loop that
follows is the positive control: the same pipeline over the three sibling
files must report non-zero counts (2, 1 and 6 at the base; re-measured on
every replay), or the first line's silence proves nothing:

```sh
grep -rn '#\[path' mag/tests --include='*.rs' | grep 'src/critic\.rs"' || true
for f in critic.rs critic/text.rs critic/inspect.rs critic/metrics.rs; do
  n=$(grep -rn '#\[path' mag/tests --include='*.rs' | grep -c "src/$f\"" || true)
  echo "$f included_by=$n"
done
```

Block 2, the green direction. The three consumer tests must run and pass:

```sh
cd mag && cargo test --bin mag parity_seam_is_reachable_from_critic 2>&1 | tail -8
```

Block 3, the red direction in two forms, both reproduced from the landed tree.
The first replay of this block caught a caption error: with the one-line seam
change reverted, the landed test fails with `E0432: unresolved imports
crate::parity::qc, crate::parity::qo`, **not** `E0603`, because the landed
import is the flat `crate::parity::{qc, qo, ...}` and a missing re-export is an
unresolved name rather than a private module. `E0603` is what the consumer
hits when it writes the import the way the source suggests,
`crate::parity::streams::...`, which is the form the test was first written
in. Both forms are the seam being unreachable; they are just two spellings of
the same consumer. So the block runs both: 3a reverts the seam and expects
`E0432`; 3b keeps the seam and rewrites the test's import to the module path,
expecting `E0603` for both `display` and `streams`. Each restores its file
from HEAD afterwards. `rm` and `git checkout --` are unavailable, so the
restore goes through `git show`:

```sh
cd mag
uv run python - <<'PY'
from pathlib import Path
p = Path("src/parity.rs")
s = p.read_text()
assert "pub(crate) use streams::{qc, qo, Color};" in s, "seam line not found"
p.write_text(s.replace("pub(crate) use streams::{qc, qo, Color};",
                       "pub(crate) use streams::Color;"))
PY
echo "3a, seam reverted:"
cargo test --bin mag 2>&1 | grep -E '^error' || true
git show HEAD:mag/src/parity.rs > src/parity.rs
git diff --quiet src/parity.rs && echo "parity.rs restored"
uv run python - <<'PY'
from pathlib import Path
p = Path("src/critic.rs")
s = p.read_text()
flat = "use crate::parity::{qc, qo, trace_elements, Color, Element, TextFace, GLYPH_QUANTUM};"
assert flat in s, "flat import not found"
p.write_text(s.replace(flat,
    "use crate::parity::display::trace_elements;\n"
    "    use crate::parity::streams::{qc, qo, Color, Element, Face as TextFace, GLYPH_QUANTUM};"))
PY
echo "3b, import spelled through the private modules:"
cargo test --bin mag 2>&1 | grep -E '^error' || true
git show HEAD:mag/src/critic.rs > src/critic.rs
git diff --quiet src/critic.rs && echo "critic.rs restored"
```

Block 4, the full gate, unchanged from the repository's standing state:

```sh
cd mag
cargo fmt --check && echo "fmt ok"
cargo clippy --all-targets -- -D warnings 2>&1 | tail -2
cargo test 2>&1 | grep -E 'test result: FAILED|^error' || echo "all suites ok"
```

## Residuals

- `mag/src/main.rs:377`'s `parity_text_seam_is_reachable` is now redundant with
  the stronger test in `mag/src/critic.rs` and names only items that were never
  blocked. It is in `main.rs`, which is not in this WP's Owns, so it stands.
  Folding it into the critic-side module, or deleting it, is a one-line change
  for whoever owns `main.rs` next.
- Nothing enforces that `mag/src/critic.rs` stays `#[path]`-free. The check in
  block 1 is a measurement. `mag/tests/` already carries `tools/nocomments.py`
  as precedent for a repository-shaped rule enforced by a test; the same shape
  would work here: assert that no `#[path]` in `mag/tests` names a file whose
  `#[cfg(test)]` modules use `crate::`. Not built, because it is a new test
  under `mag/tests/` and outside this WP's Owns.
- The two integration tests that rebuild a fake `mod parity { ... }` shim have
  no check binding that shim to `mag/src/parity.rs`'s real re-exports. See
  the retirement section above.
