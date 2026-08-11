#!/usr/bin/env python3
"""Render the same edition cover with different candidate art, side by side.

    python3 tools/coverproof.py 006 art1.png art2.png [...]

For each candidate the edition's cover.art_path is swapped in place, the
edition is rendered through the normal `mag render` path, and the rendered
cover page (page-001) is harvested. The original edition.yaml is restored
afterward even on failure. Output: editions/<ed>/art/cover-proofs/<stamp>/
with one PNG per candidate and a proof.html opening them side by side.

Each candidate costs one full edition render (roughly half a minute); the
point is zero hand-editing between trials, not a faster renderer. Render
scratch dirs created along the way are ordinary untracked render-* output.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def newest_render_dir(edition_dir: Path) -> Path:
    dirs = sorted(d for d in edition_dir.glob("render-*") if d.is_dir())
    if not dirs:
        raise SystemExit("no render-* directory produced")
    return dirs[-1]


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    edition = sys.argv[1]
    candidates = [Path(p) for p in sys.argv[2:]]
    for c in candidates:
        if not (ROOT / c).is_file():
            raise SystemExit(f"candidate not found: {c}")

    edition_dir = next(
        (d for d in (ROOT / "editions").iterdir() if d.name == edition or d.name.startswith(edition)),
        None,
    )
    if edition_dir is None:
        raise SystemExit(f"no editions/ directory for {edition!r}")
    manifest = edition_dir / "edition.yaml"
    original = manifest.read_text(encoding="utf-8")
    if not re.search(r"(?m)^  art_path: ", original):
        raise SystemExit("edition.yaml has no cover art_path to swap")

    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    out_dir = edition_dir / "art" / "cover-proofs" / stamp
    out_dir.mkdir(parents=True)

    rows = []
    try:
        for cand in candidates:
            swapped = re.sub(
                r"(?m)^  art_path: .*$", f"  art_path: {cand.as_posix()}", original, count=1
            )
            manifest.write_text(swapped, encoding="utf-8")
            print(f"rendering with {cand.name} ...", flush=True)
            subprocess.run(
                [str(ROOT / "mag" / "target" / "debug" / "mag"), "render", edition],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            page = newest_render_dir(edition_dir) / "out" / "en" / "render-review" / "reader-pages" / "page-001.png"
            dest = out_dir / f"{cand.stem}.png"
            dest.write_bytes(page.read_bytes())
            rows.append((cand, dest.name))
    finally:
        manifest.write_text(original, encoding="utf-8")

    cells = "\n".join(
        f'<figure><img src="{name}"><figcaption>{cand.as_posix()}</figcaption></figure>'
        for cand, name in rows
    )
    (out_dir / "proof.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Cover proofs</title>"
        "<style>body{margin:2rem;font:14px/1.4 -apple-system,sans-serif;background:#222;color:#eee}"
        "main{display:flex;gap:2rem;flex-wrap:wrap}figure{margin:0}"
        "img{width:420px;box-shadow:0 4px 24px #000}figcaption{margin-top:.5rem;max-width:420px;word-break:break-all}</style>"
        f"<main>{cells}</main>",
        encoding="utf-8",
    )
    print(f"proof sheet: {out_dir / 'proof.html'}")


if __name__ == "__main__":
    main()
