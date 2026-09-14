# WP-1.5 apply the hyphenation decision

## Base

7d79b9d (plan revision 9: 4b887f6 + 5f16548).

Decision applied, not revisited: revision 9 records option (b), hyphenation
off in both engines for parity, scoped to `:lang(en)`, with WP-4.3 mandatory.

## Commands

Everything below ran in a throwaway worktree so no tracked file outside Owns
moved and no other agent's work was disturbed:

```sh
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp15 HEAD
cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp15
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 editions/010/
cd mag && cargo build && cd ..
```

Edition 010 ships no Spanish translation and `stage_translation`
(mag/src/render.rs:737) only emits an es leg when
`editions/<id>/translations/es/edition.yaml` exists, so the scoping proof
needs one. It is built from the run's own finals, because the translated
prose is irrelevant here: what is under test is whether the selector fires on
a document whose `html lang` is not `en`.

```sh
python3 - <<'PY'
import pathlib, shutil, yaml
root = pathlib.Path(".")
run = root/"editions/010/run-2026-09-13T01-34-51/articles"
ed = yaml.safe_load((root/"editions/010/edition.yaml").read_text())
tdir = root/"editions/010/translations/es"
(tdir/"articles").mkdir(parents=True, exist_ok=True)
arts = []
for a in ed["articles"]:
    name = pathlib.Path(a["manuscript"]).stem
    shutil.copyfile(run/name/"final.md", tdir/"articles"/f"{name}.md")
    entry = {"id": a["id"], "title": a["title"],
             "short_title": a.get("short_title", a["title"]),
             "author_note": a.get("author_note", ""),
             "manuscript": f"articles/{name}.md"}
    figs = a.get("figures")
    if figs:
        entry["figures"] = [{k: f[k] for k in
                             ("id","caption","credit","alt_text","anchor") if k in f}
                            for f in figs]
    arts.append(entry)
cov = ed["cover"]
t = {"schema_version": 1, "language": "es", "source_language": "en",
     "locale": "es-AR", "fallback_locale": "es-ES",
     "title": ed["title"], "subtitle": ed.get("subtitle", ""),
     "cover": {"headline": cov["headline"], "deck": cov["deck"],
               "back_text": cov["back_text"]},
     "closing_plate_titles": [p["title"] for p in ed["closing_plates"]],
     "sections": [],
     "articles": arts}
(tdir/"edition.yaml").write_text(yaml.safe_dump(t, allow_unicode=True, sort_keys=False))
PY
```

Baseline both legs, then the CSS switch, then both legs again:

```sh
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51 --langs en,es
# copy the edited weasyprint-a5.css into the worktree, then:
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51 --langs en,es
```

With the baseline out dir as `B` and the post-switch out dir as `A`:

```sh
for L in en es; do
  pdfinfo $B/$L/reader.pdf | awk '/^Pages/{print $2}'
  pdftotext -raw $B/$L/reader.pdf /tmp/base-$L.txt
  pdftotext -raw $A/$L/reader.pdf /tmp/after-$L.txt
  grep -c -- '-$' /tmp/base-$L.txt; grep -c -- '-$' /tmp/after-$L.txt
done
cmp /tmp/base-es.txt /tmp/after-es.txt      # must be identical
python3 -c "
import json
b=json.load(open('$B/en/edition-manifest.json'))['layout']['article_pages']
a=json.load(open('$A/en/edition-manifest.json'))['layout']['article_pages']
print('identical' if b==a else [(k,b[k],a[k]) for k in b if b[k]!=a[k]])"
python3 -c "
run=mx=0
for l in open('/tmp/after-en.txt'):
    run = run+1 if l.rstrip(chr(10)).endswith('-') else 0
    mx=max(mx,run)
print(mx)"
```

Determinism, WP-0.1's check re-run verbatim on the post-switch state (its
`## Commands` script, unchanged, over two fresh en renders sharing one run
dir):

```sh
./mag/target/debug/mag render 010 --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag render 010 --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
# then WP-0.1's pdftotext / pdfinfo / JSON leaf comparison, verbatim
```

## Tool versions

Unchanged from WP-0.1's record (python 3.12.11, uv 0.8.17, weasyprint 69.0,
poppler 25.08.0, rustc 1.96.0); this WP adds no tool.

## Metrics

The switch, edition 010 English:

| quantity | before | after |
|---|---|---|
| reader pages | 56 | 56 |
| `layout.article_pages` | identical before and after | |
| cap violations introduced | 0 | |
| hyphen-ended lines | 142 | 16 |
| max consecutive hyphen-ended lines | 3 (WP-1.3's ladders) | 2 |

The 142 to 16 delta is exactly 126, matching WP-1.3's independently measured
126 soft-hyphen breaks. The 16 that remain are real compound hyphens, present
either way. WP-1.3 counted 141 and 15 for the same two states: a consistent
offset of one, from counting the reader dump rather than the prose blocks, and
the delta agrees exactly.

One pre-existing cap violation survives untouched: `dario-amodei-we-must-pace
-the-frontier` sets 13 pages against a cap of 10, before and after, recorded
by WP-1.3 and by edition 010's own intake. This switch neither causes nor
cures it.

The scoping, proved rather than assumed:

| quantity | es before | es after |
|---|---|---|
| reader pages | 56 | 56 |
| `pdftotext -raw` dump | byte-identical to after | |
| hyphen-ended lines | 162 | 162 |
| max consecutive hyphen-ended lines | 4 | 4 |

Spanish is untouched at the byte level, still hyphenates, and still ladders.
The ladder the render reports on reader page 49 is the es leg: English's
longest run after the switch is 2, inside the adapter's allowance.

Determinism, WP-0.1's check on the post-switch state: `pdftotext` and
`pdfinfo -box` identical for reader, booklet-a4, booklet-a4-interior and
booklet-a4-cover; `request.json` and `en/edition-manifest.json` byte-equal;
exactly the six whitelisted leaves differ and nothing else, the four
`preflight.json` scratch-stage paths and the two `render-critic.json`
PDF-byte hashes.

## Verdicts

No `mag parity` verdict belongs to this WP: it changes the oracle, and the
comparator's own verdicts are bound to staged-input digests that this change
moves. The next parity run rebases its baseline per the staleness guard.

## Residuals

- Every render of 010 en after this commit differs from every render before
  it. The two deterministic trees WP-0.2a through WP-0.2d used as fixtures
  (`editions/010/render-2026-09-14T01-47-59` and `...T01-49-02`) are now
  stale as oracle references: they carry hyphenated English. Any WP replaying
  a stored verdict digest against a fresh render must re-render both legs
  first. The comparator is unaffected, since `mag parity` renders both legs
  itself.
- WP-0.0c had NOT landed when this committed (`git log` at commit time tops
  out at 7d79b9d). Its before/after `edition-manifest.json` comparison must
  therefore be run entirely after this commit, never straddling it, or the
  opener-fit diff will carry this switch's line rebreaks as noise.
- The es leg was proved with a scratch translation built from English finals,
  not real Spanish prose. That is sufficient for the selector question, which
  is about `html lang`, and it is not evidence about Spanish typography. The
  cap risk the stylesheet comment records for real Spanish editions is
  untested here and stays as revision 9 describes it.
- `mag render` emits the es leg whenever a translation exists and `--langs`
  does not exclude it, so this scratch translation must never be committed:
  it would silently add a Spanish leg to every 010 render. It lives only in
  the throwaway worktree, which is removed.

## Status

done
