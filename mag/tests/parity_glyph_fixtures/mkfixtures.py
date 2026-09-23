"""Build the WP-0.2i glyph-parity fixture corpus from a rendered edition tree.

Usage:
    uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py [NAME ...]

With no NAME every fixture is built. Both input and output are resolved
against the checkout that contains this file and announced at startup:

    render tree   $MAG_PARITY_RENDER_A, else editions/010/render-2026-09-14T01-47-59
    output root   $MAG_PARITY_FIXTURES, else .magazine/parity-fixtures

The render tree is untracked build output. Stage it into the checkout (copy
it, or re-render the edition) before running; the script fails loud naming
the path it wanted if it is absent.
"""

import io
import os
import re
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
)

ROOT = Path(__file__).resolve().parents[3]
TICK = 0.000732421875
QUANTUM = TICK / 8.0
RATE = 0.000173
INTERIOR = range(1, 55)
FAULT_PAGE = 3

TJ = re.compile(rb"\[(.*?)\]\s*TJ", re.S)
TF = re.compile(rb"/(\w+)\s+([0-9.]+)\s+Tf")
TOK = re.compile(rb"<([0-9A-Fa-f]*)>|(-?[0-9.]+)")

SRC = None
OUT = None


def size_before(data, pos):
    m = None
    for x in TF.finditer(data, 0, pos):
        m = x
    return float(m.group(2)) if m else 10.0


def count_glyphs(body):
    return sum(len(m.group(1)) // 4 for m in TOK.finditer(body) if m.group(1) is not None)


def rebuild(body, sz, kern_at):
    total = count_glyphs(body)
    parts, k = bytearray(), 0
    for m in TOK.finditer(body):
        if m.group(1) is None:
            parts += b" " + m.group(2) + b" "
            continue
        hexs = m.group(1)
        for i in range(0, len(hexs), 4):
            parts += b"<" + hexs[i : i + 4] + b">"
            k += 1
            shift = kern_at(k, total)
            if shift:
                parts += b"%.9f" % (-shift * 1000.0 / sz)
    return bytes(parts), total


def edit_page(data, kern_at, only_first=False, min_glyphs=0):
    out, last, done = bytearray(), 0, 0
    for m in TJ.finditer(data):
        if only_first and done:
            break
        sz = size_before(data, m.start())
        body, total = rebuild(m.group(1), sz, kern_at)
        if total < min_glyphs:
            continue
        out += data[last : m.start()] + b"[" + body + b"] TJ"
        last = m.end()
        done += 1
    out += data[last:]
    return bytes(out), done


def write_variant(name, page_fn, doc_fn=None):
    reader = PdfReader(SRC)
    writer = PdfWriter()
    writer.append(reader)
    edits = 0
    for i, page in enumerate(writer.pages):
        new, n = page_fn(i, page.get_contents().get_data(), page, writer)
        if n:
            stream = DecodedStreamObject()
            stream.set_data(new)
            page[NameObject("/Contents")] = writer._add_object(stream)
            edits += n
    if doc_fn:
        edits += doc_fn(writer)
    out = OUT / name / "en"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "reader.pdf", "wb") as f:
        writer.write(f)
    print(f"{name}: {edits} edits")


def unchanged(name):
    write_variant(name, lambda i, d, p, w: (d, 0))


def interior_drift(name, dfun):
    step = lambda k, total: dfun(k) - dfun(k - 1)
    write_variant(
        name,
        lambda i, d, p, w: edit_page(d, step) if i in INTERIOR else (d, 0),
    )


def compensating_kern(name, amount):
    at = {2: amount, 6: -amount}
    write_variant(
        name,
        lambda i, d, p, w: edit_page(d, lambda k, total: at.get(k, 0.0), only_first=True)
        if i == FAULT_PAGE
        else (d, 0),
    )


def suffix_kern(name, start_at, amount, compensate_at, min_glyphs):
    def at(k, total):
        stop = total if compensate_at == "tail" else compensate_at
        if k == start_at:
            return amount
        return -amount if stop and k == stop else 0.0

    write_variant(
        name,
        lambda i, d, p, w: edit_page(d, at, only_first=True, min_glyphs=min_glyphs)
        if i == FAULT_PAGE
        else (d, 0),
    )


def mid_bump(name, amount):
    def at(k, total):
        return amount if k == 10 else (-amount if k == 20 else 0.0)

    write_variant(
        name,
        lambda i, d, p, w: edit_page(d, at, min_glyphs=25) if i in INTERIOR else (d, 0),
    )


def linmatrix(name):
    def patch(i, d, p, w):
        if i != FAULT_PAGE:
            return d, 0
        m = re.search(rb"([0-9.]+) (0|0\.0+) (0|-?0\.0+) (-?[0-9.]+) ([0-9.]+) ([0-9.]+) Tm", d)
        if not m:
            return d, 0
        a = float(m.group(1))
        na = a * (1.0 + 0.0004 / max(a, 1e-9))
        rep = b"%.9f %s %s %s %s %s Tm" % (
            na,
            m.group(2),
            m.group(3),
            m.group(4),
            m.group(5),
            m.group(6),
        )
        return d[: m.start()] + rep + d[m.end() :], 1

    write_variant(name, patch)


def ocmember(name):
    def wrap(i, d, p, w):
        if i != FAULT_PAGE:
            return d, 0
        ocg = DictionaryObject()
        ocg[NameObject("/Type")] = NameObject("/OCG")
        ocg[NameObject("/Name")] = NameObject("/Hidden")
        props = DictionaryObject()
        props[NameObject("/MC0")] = w._add_object(ocg)
        p["/Resources"][NameObject("/Properties")] = w._add_object(props)
        return b"/OC /MC0 BDC\n" + d + b"\nEMC\n", 1

    write_variant(name, wrap)


def annotap(name):
    def attach(w):
        for page in w.pages:
            if "/Annots" not in page:
                continue
            for a in page["/Annots"]:
                obj = a.get_object()
                ap = DecodedStreamObject()
                ap.set_data(b"")
                ap[NameObject("/Type")] = NameObject("/XObject")
                ap[NameObject("/Subtype")] = NameObject("/Form")
                ap[NameObject("/BBox")] = ArrayObject([FloatObject(0)] * 4)
                slot = DictionaryObject()
                slot[NameObject("/N")] = w._add_object(ap)
                obj[NameObject("/AP")] = slot
                return 1
        return 0

    write_variant(name, lambda i, d, p, w: (d, 0), attach)


def glyphsub(name):
    reader = PdfReader(SRC)
    writer = PdfWriter()
    writer.append(reader)
    page = writer.pages[FAULT_PAGE]
    data = page.get_contents().get_data()
    m = re.search(rb"/(\w+)\s+[0-9.]+\s+Tf\n\[<([0-9A-Fa-f]{4})", data)
    res_name, a_cid = m.group(1).decode(), int(m.group(2), 16)
    font = page["/Resources"]["/Font"][NameObject("/" + res_name)].get_object()
    desc = font["/DescendantFonts"].get_object()[0].get_object()
    fd = desc["/FontDescriptor"].get_object()
    face = TTFont(io.BytesIO(fd["/FontFile2"].get_object().get_data()), recalcTimestamp=False)
    order = face.getGlyphOrder()
    donor = next(
        n
        for i, n in enumerate(order)
        if i not in (0, a_cid) and face["glyf"][n].numberOfContours not in (0, None)
    )
    face["glyf"][order[a_cid]] = face["glyf"][donor]
    buf = io.BytesIO()
    face.save(buf)
    stream = DecodedStreamObject()
    stream.set_data(buf.getvalue())
    stream[NameObject("/Length1")] = NumberObject(len(buf.getvalue()))
    fd[NameObject("/FontFile2")] = writer._add_object(stream)
    out = OUT / name / "en"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "reader.pdf", "wb") as f:
        writer.write(f)
    print(f"{name}: CID {a_cid:04X} ({order[a_cid]}) now draws {donor}; widths and ToUnicode intact")


BUILDERS = {
    "control": lambda: unchanged("control"),
    "drift": lambda: interior_drift("drift", lambda k: k * RATE),
    "stairdrift": lambda: interior_drift("stairdrift", lambda k: TICK * round(k * RATE / TICK)),
    "smoothdrift": lambda: interior_drift("smoothdrift", lambda k: k * 0.0005),
    "kern02": lambda: compensating_kern("kern02", 0.02),
    "kern005": lambda: compensating_kern("kern005", 0.005),
    "kern001": lambda: compensating_kern("kern001", 0.001),
    "kern00001": lambda: compensating_kern("kern00001", 0.0001),
    "linmatrix": lambda: linmatrix("linmatrix"),
    "ocmember": lambda: ocmember("ocmember"),
    "annotap": lambda: annotap("annotap"),
    "glyphsub": lambda: glyphsub("glyphsub"),
    "advtail02": lambda: suffix_kern("advtail02", 2, 0.02, "tail", 10),
    "advtail_small": lambda: suffix_kern("advtail_small", 2, 0.001, "tail", 10),
    "advtail_late": lambda: suffix_kern("advtail_late", 40, 0.025, "tail", 60),
    "advstep": lambda: suffix_kern("advstep", 40, 0.025, None, 60),
    "advmid": lambda: suffix_kern("advmid", 40, 0.025, 60, 60),
    "vq_2q": lambda: mid_bump("vq_2q", 2 * QUANTUM),
    "vq_1q": lambda: mid_bump("vq_1q", QUANTUM),
    "vq_half": lambda: mid_bump("vq_half", QUANTUM / 2),
    "vq_quarter": lambda: mid_bump("vq_quarter", QUANTUM / 4),
    "vq_e2": lambda: mid_bump("vq_e2", QUANTUM / 100),
    "vq_e3": lambda: mid_bump("vq_e3", QUANTUM / 1000),
    "vq_e4": lambda: mid_bump("vq_e4", QUANTUM / 10000),
}


def flat_fraction(n):
    d = lambda k: TICK * round(k * RATE / TICK)
    flats = sum(1 for k in range(n) if d(k + 1) == d(k))
    return flats, n, flats / n


def main():
    global SRC, OUT
    env_src = os.environ.get("MAG_PARITY_RENDER_A")
    env_out = os.environ.get("MAG_PARITY_FIXTURES")
    tree = Path(env_src) if env_src else ROOT / "editions/010/render-2026-09-14T01-47-59"
    OUT = Path(env_out) if env_out else ROOT / ".magazine/parity-fixtures"
    SRC = tree / "en" / "reader.pdf"
    print(__doc__.splitlines()[0])
    print(f"checkout    {ROOT}")
    print(f"render tree {tree} ({'env' if env_src else 'checkout default'})")
    print(f"output root {OUT} ({'env' if env_out else 'checkout default'})")
    print(f"quantum     {QUANTUM!r} pt = tick/{TICK / QUANTUM:.1f}")
    if not SRC.is_file():
        sys.exit(f"missing render tree: {SRC}\nstage it into the checkout, then re-run")
    names = sys.argv[1:] or list(BUILDERS)
    unknown = [n for n in names if n not in BUILDERS]
    if unknown:
        sys.exit(f"unknown fixture(s): {', '.join(unknown)}\nknown: {', '.join(BUILDERS)}")
    for name in names:
        BUILDERS[name]()
    flats, n, frac = flat_fraction(68800)
    print(f"stairdrift flat steps {flats}/{n} = {frac:.4%}")


if __name__ == "__main__":
    main()
