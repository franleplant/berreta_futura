#let PAGE-WIDTH = 148mm
#let PAGE-HEIGHT = 210mm
#let MARGIN-TOP = 42.0004pt
#let MARGIN-OUTER = 42.5197pt
#let MARGIN-BOTTOM = 54.9996pt
#let MARGIN-INNER = 44pt
#let LIVE-WIDTH = PAGE-WIDTH - MARGIN-INNER - MARGIN-OUTER
#let MEASURE = 325pt
#let MEASURE-DELTA = 0.025pt
#let RAIL = (LIVE-WIDTH - MEASURE) / 2

#let INK = rgb(27, 24, 22)
#let RUBRIC = rgb(186, 52, 31)
#let STONE = rgb(112, 104, 95)
#let CAPTION-INK = rgb(72, 66, 60)
#let VIOLET = RUBRIC
#let SLATE = STONE
#let COOL-GRAY = rgb(214, 207, 196)
#let PALE-VIOLET = rgb(246, 243, 237)
#let SIGNAL-ORANGE = rgb(240, 87, 56)

#let SYMBOLS = "Noto Sans Math"
#let EMOJI = ("Twemoji Mozilla", "Noto Emoji")
#let SERIF = ("EB Garamond", SYMBOLS, ..EMOJI)
#let DISPLAY = ("EB Garamond", SYMBOLS, ..EMOJI)
#let SANS = ("Inter", SYMBOLS, ..EMOJI)
#let MONO = ("Geist Mono", SYMBOLS, ..EMOJI)
#let CODE-VIOLET = rgb(25%, 10%, 43%)
#let CODE-PALE = rgb(95.5%, 94.5%, 97.5%)
#let CODE-INK = rgb(5.5%, 7.5%, 8.5%)
#let OLDSTYLE = ("onum", "pnum")
#let PROSE-FIGURES = ("lnum", "pnum")
#let LINING = ("lnum", "tnum")
#let SMALL-CAPS = ("smcp", "onum")
#let ALL-SMALL-CAPS = ("c2sc", "smcp", "onum")

#let HALF-SERIF = 0.3545
#let HALF-DISPLAY = 0.3545
#let HALF-SANS = 0.36377
#let HALF-MONO = 0.355
#let MONO-ADVANCE = 0.6
#let CODE-SIZE = 0.82
#let CODE-PAD-X = 3pt
#let CODE-PAD-Y = 1.2pt
#let CODE-RADIUS = 2pt
#let CODE-BLOCK-SIZE = 7.5pt
#let CODE-BLOCK-LEADING = 1.3
#let CODE-BLOCK-PAD = 3mm
#let TABLE-SIZE = 8.6pt
#let TABLE-LEADING = 10.8pt
#let TABLE-PAD = 4pt
#let TABLE-GAP = 14pt
#let TABLE-RULE = 0.35pt
#let DISC = 5pt
#let DISC-KAPPA = 0.55

#let DATUM = 10.810791015625pt
#let BODY-SIZE = 10.75pt
#let BODY-LEADING = 14pt
#let PARAGRAPH-AFTER = 7pt
#let PARAGRAPH-INDENT = 1.1em
#let EDITORIAL-AFTER = 7pt
#let PLATE-LEADING = 13.2pt
#let PLATE-AFTER = 6.6pt
#let CAPTION-SIZE = 8.6pt
#let CAPTION-LEADING = 10.8pt
#let LABEL-SIZE = 8.4pt
#let FOLIO-SIZE = 10pt
#let FOLIO-BASELINE = 24pt
#let LIST-INDENT = 16pt
#let ITEM-AFTER = 3.5pt
#let REFERENCE-AFTER = 3pt
#let REFERENCE-SIZE = 8.8pt
#let REFERENCE-LEADING = 11pt
#let REFERENCE-HANG = 14pt
#let QUOTE-RULE = 1.5pt
#let QUOTE-PAD = 14pt
#let QUOTE-SIZE = 10.2pt
#let QUOTE-LEADING = 13.4pt
#let HEADING-CLEARANCE = 25pt
#let ZERO-LEADING-SANS = 2.47375pt
#let RUNNING-BASELINE = 25pt
#let RUNNING-TRACKING = 0.14em
#let ARTICLE-PAGE-CAP = 7
#let VERBATIM-PAGE-CAP = 10

#let FIGURE-CAPTION-ABOVE = 6.3pt
#let FIGURE-GAP = 21pt
#let COMPACT-FIGURE-GAP = 18pt
#let FIGURE-MAX-HEIGHT = 205pt
#let COMPACT-FIGURE-MAX-HEIGHT = 170pt
#let OPENER-FIGURE-MAX-HEIGHT = 270pt
#let FULL-FIGURE-MAX-HEIGHT = 400pt
#let ROTATED-PLATE-LENGTH = 523pt
#let ROTATED-PLATE-DEPTH = 295pt
#let COMPACT-BAND-INSET = 32.5pt
#let FIGURE-RULE = 0.55pt
#let CAPTION-NUDGE = 0.1166pt
#let CREDIT-NUDGE = -0.09023pt
#let TAIL-MAX-HEIGHT = 214pt
#let TAIL-FRAME-BOTTOM = 45pt
#let TAIL-CLEARANCE = 12pt
#let BAND-CLEARANCE-LINES = 4
#let TAIL-FOOT-F32-LIFT = 0.0001pt
#let PAGE-TOP-EPSILON = 0.01pt
#let BAND-LAYOUTS = ("evidence_band", "evidence_band_prose", "adaptive_band", "full_band")
#let ROTATED-PLATE = "rotated_plate"
#let COMPACT-BAND = "compact_band"
#let OPENER-ANCHOR = "__opener__"
#let EXTRACT-GAP = 5mm
#let EXTRACT-LABEL-AFTER = 2pt
#let EXTRACT-CAPTION-ABOVE = 2pt
#let EXTRACT-LABEL-TRACKING = 0.45pt

#let CONTENTS-KICKER-TOP = -13.46915pt
#let CONTENTS-TOP = 8pt
#let CONTENTS-RULE = 0.6pt
#let CONTENTS-HEAD-RULE = 1.4pt
#let CONTENTS-FOLIO = 22pt
#let CONTENTS-GAP = (min: 5pt, max: 16pt)

#let ILLUSTRATED = "illustrated_paper_spots_v1"
#let PAPER-INK = rgb(23, 25, 28)
#let PAPER-BLUE = rgb(49, 93, 140)
#let PAPER-RULE = rgb(200, 192, 179)
#let PAPER-GRAY = rgb(93, 96, 96)
#let OPENER-ESCAPE = 11.5pt
#let OPENER-RAIL = 348pt
#let OPENER-ART-HEIGHT = 207.1pt
#let OPENER-ART-LIFT = 12.0004pt
#let OPENER-MARK-LIFT = 12pt
#let OPENER-ART-FLOW = 195.1pt
#let OPENER-META-MEASURE = 293pt
#let OPENER-LINE-RESERVE = 13.2pt
#let CONTENT-HEIGHT = PAGE-HEIGHT - MARGIN-TOP - MARGIN-BOTTOM
#let OPENER-FRAME-HEIGHT = 203pt
#let OPENER-OFFSET = 4.1pt
#let OPENER-BORDER = 2.4pt
#let OPENER-FOCUS = (49%, 47%)
#let OPENER-QR-QUIET = 4
#let OPENER-QR = 41pt
#let PLAIN-QR = 55.5pt
#let CODE-CREDIT-GAP = 4.5 * 3.15pt
#let INTER-CAP = 1490 / 2048
#let OPENER-GAP = 14pt
#let OPENER-META-RULE = 0.5pt
#let OPENER-LABEL-SIZE = 8.4pt
#let OPENER-LABEL-LEADING = 9pt
#let OPENER-LABEL-TRACKING = 0.14
#let OPENER-TITLE-LEADING-RATIO = 1.1
#let OPENER-TITLE-TRACKING = 0
#let OPENER-BYLINE-SIZE = 10pt
#let OPENER-BYLINE-LEADING = 12pt
#let OPENER-BYLINE-TRACKING = 0.09
#let OPENER-PREFIX-SIZE = 10pt
#let OPENER-PREFIX-TRACKING = 0
#let OPENER-PREFIX-GAP = 0
#let OPENER-NOTE-SIZE = 8.8pt
#let OPENER-NOTE-LEADING = 11pt
#let OPENER-NOTE-ABOVE = 2pt
#let DROP-LINES = 3
#let DROP-GAP = 4pt
#let DROP-SMALL-CAPS-WORDS = 0
#let BODY-CAP-HEIGHT = 0.65
#let DISPLAY-CAP-HEIGHT = 0.65
#let OPENER-STANDARD = (
  label: 22pt,
  title-gap: 9pt,
  tick: 13pt,
  meta-pad: 9pt,
  standfirst-gap: 22pt,
  standfirst-size: 11.25pt,
  standfirst-leading: 15pt,
)
#let OPENER-COMPACT = (
  label: 18pt,
  title-gap: 7pt,
  tick: 10pt,
  meta-pad: 7pt,
  standfirst-gap: 16pt,
  standfirst-size: 10.75pt,
  standfirst-leading: 14pt,
)
#let OPENER-SQUEEZED = (..OPENER-COMPACT, meta-pad: 5pt, standfirst-gap: 11pt)
#let OPENER-MIN-CARRY = 2

#let line-half(size, ascender: 1984, descender: -494, upem: 2048) = {
  let units = calc.floor(size / 1pt * 4 / 3 * 1024)
  let mult = calc.floor(units * 65536 / upem)
  let scaled(v) = calc.floor((v * mult + 32768) / 65536)
  (scaled(ascender) + scaled(descender)) / 2048 * 0.75pt
}
#let FACE-METRICS = ((HALF-SERIF, 1007, -298, 1000), (HALF-SANS, 1984, -494, 2048), (HALF-MONO, 1005, -295, 1000))
#let line-center(half, size) = {
  let (_, ascender, descender, upem) = FACE-METRICS.find(m => m.first() == half)
  line-half(size, ascender: ascender, descender: descender, upem: upem)
}
#let edges(size, leading, half) = (
  top-edge: leading / 2 + line-center(half, size),
  bottom-edge: leading / 2 + line-center(half, size) - leading,
)

#let pinned(leading) = (top-edge: DATUM, bottom-edge: DATUM - leading)

#let flat = (top-edge: 0pt, bottom-edge: 0pt)

#let tracked(amount) = (tracking: amount, features: (liga: 0, clig: 0))

#let publication = state("publication", [])

#let leading-zero(index) = if index < 10 { "0" + str(index) } else { str(index) }

#let small-caps(body, size: LABEL-SIZE, tracking: 0.1em, fill: INK, weight: 400) = text(
  font: SERIF,
  size: size,
  weight: weight,
  fill: fill,
  tracking: tracking,
  features: ALL-SMALL-CAPS,
  ..flat,
  body,
)

#let folio-text(body) = small-caps(body, size: CAPTION-SIZE)

#let live-left(index) = if calc.odd(index) { MARGIN-INNER } else { MARGIN-OUTER }

#let centered-at(index, y, body) = place(top + left, dx: live-left(index), dy: y, box(width: LIVE-WIDTH, align(center, body)))

#let folio(index) = centered-at(index, PAGE-HEIGHT - FOLIO-BASELINE, text(
  font: SERIF,
  size: FOLIO-SIZE,
  fill: INK,
  features: OLDSTYLE,
  ..flat,
  str(index),
))

#let running-head(index) = {
  let marks = query(<mag-piece>).filter(m => m.location().page() <= index)
  if marks.len() == 0 or marks.last().location().page() == index { return }
  let head = text(font: SERIF, size: 9.4pt, style: "italic", fill: STONE, features: OLDSTYLE, ..flat, marks.last().value.head)
  centered-at(index, RUNNING-BASELINE, head)
}

#let furniture() = context {
  let index = counter(page).at(here()).first()
  running-head(index)
  folio(index)
}

#let plain-page() = page(margin: 0pt, foreground: none, [])

#let COVER-W = PAGE-WIDTH.pt()
#let COVER-H = PAGE-HEIGHT.pt()
#let COVER-FACES = (
  bold: ("Inter", 700),
  regular: ("Inter", 400),
  display: ("Archivo", 700),
  serif: ("Source Serif 4 SmText", 400),
)
#let COVER-ROSTER = 6.5
#let COVER-WORDMARK-INSET = (2.85, -28.91)
#let COVER-WORDMARK-HEIGHT = 75.13

#let cover-front(spec) = state("mag-cover-front").update(_ => spec)
#let cover-back(spec) = state("mag-cover-back").update(_ => spec)
#let credits(lines) = state("mag-credits").update(_ => lines)

#let plain-text(body) = if type(body) == str { body } else if body == none { "" } else if body.has("text") {
  body.text
} else if body.has("children") {
  body.children.map(plain-text).join()
} else if body.has("body") { plain-text(body.body) } else if body == [ ] { " " } else { "" }

#let MONTHS = (
  en: ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
  es: ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"),
)

#let long-date(source, lang) = {
  let parts = source.trim().split("-")
  if parts.len() != 3 { return source }
  let (year, month, day) = parts.map(int)
  let months = MONTHS.at(lang, default: MONTHS.en)
  if lang == "es" { str(day) + " de " + months.at(month - 1) + " de " + str(year) } else { str(day) + " " + months.at(month - 1) + " " + str(year) }
}

#let edition-facts = state("mag-edition-facts", (:))
#let fact(key, body) = edition-facts.update(f => f + ((key): plain-text(body)))

#let ornament(size: 11pt, fill: RUBRIC, glyph: "\u{2767}", font: SERIF) = text(font: font, size: size, fill: fill, ..flat, glyph)

#let COLOPHON-TOP = 168pt
#let COLOPHON-MARK = 40pt

#let credits-page() = page(margin: 0pt, foreground: none, context {
  let c = state("mag-credits").final()
  let lines = if c == none { none } else { ("made by " + c.maker, c.site, c.issue_url, c.email) }
  let facts = edition-facts.final()
  let lang = text.lang
  let x0 = MARGIN-OUTER
  let at(y, body) = place(top + left, dx: x0, dy: COLOPHON-TOP + y, box(width: LIVE-WIDTH, align(center, body)))
  let name = plain-text(publication.final())
  let mark = image(bytes(read("/brand/mark.svg").replace(regex("var\\(--[a-z]+, *(#[0-9a-fA-F]+)\\)"), m => m.captures.first())), format: "svg", width: COLOPHON-MARK)
  place(top + left, dx: x0 + (LIVE-WIDTH - COLOPHON-MARK) / 2, dy: COLOPHON-TOP - COLOPHON-MARK - 26pt, mark)
  if name != "" { at(0pt, text(font: SERIF, size: 13pt, weight: 600, tracking: 0.02em, fill: INK, ..flat, name)) }
  if "issue" in facts {
    at(30pt, text(font: SERIF, size: 10.5pt, style: "italic", fill: STONE, features: OLDSTYLE, ..flat, facts.issue))
  }
  if "title" in facts {
    place(top + left, dx: x0 + 20pt, dy: COLOPHON-TOP + 40pt, block(width: LIVE-WIDTH - 40pt, {
      set par(leading: 0pt, spacing: 0pt, justify: false)
      align(center, text(font: SERIF, size: 26pt, weight: 600, fill: INK, hyphenate: false, features: PROSE-FIGURES, ..edges(26pt, 30pt, HALF-SERIF), facts.title))
    }))
  }
  if "date" in facts {
    let rows = if "title" in facts { calc.max(1, calc.round(measure(block(width: LIVE-WIDTH - 40pt, text(font: SERIF, size: 26pt, weight: 600, ..edges(26pt, 30pt, HALF-SERIF), facts.title))).height / 30pt)) } else { 0 }
    at(40pt + rows * 30pt + 18pt, text(font: SERIF, size: 10pt, fill: STONE, features: PROSE-FIGURES, ..flat, long-date(facts.date, lang)))
  }
  if lines != none {
    place(bottom + left, dx: x0, dy: -MARGIN-BOTTOM, block(width: LIVE-WIDTH, {
      set par(leading: 0pt, spacing: 0pt, justify: false)
      set align(center)
      for (index, line) in lines.enumerate() {
        block(below: 0pt, text(font: SERIF, size: 9pt, fill: if index == 0 { INK } else { STONE }, style: if index == 0 { "italic" } else { "normal" }, features: OLDSTYLE, ..pinned(12.5pt), line))
      }
    }))
  }
})

#let cover-page(key, draw) = page(margin: 0pt, foreground: none, context {
  let spec = state(key).final()
  if spec != none { draw(spec) }
})

#let cover-put(x, y, body) = place(top + left, dx: x * 1pt, dy: y * 1pt, body)

#let cover-box(width, height, fill: none, stroke: none) = rect(width: width * 1pt, height: height * 1pt, fill: fill, stroke: stroke)

#let cover-run(face, size, body, fill: black, tracking: 0, stretch: 100, stroke: none, edges: ("baseline", "baseline")) = {
  let (font, weight) = COVER-FACES.at(face)
  let run = box(text(font: font, weight: weight, size: size * 1pt, fill: fill, tracking: tracking * 1pt, stroke: stroke, top-edge: edges.at(0), bottom-edge: edges.at(1), body))
  if stretch == 100 { run } else { scale(x: stretch * 1%, y: 100%, origin: left + top, reflow: true, run) }
}

#let cover-width(face, size, body, tracking: 0, stretch: 100) = {
  measure(cover-run(face, size, body, tracking: tracking, stretch: stretch)).width.pt() - tracking * stretch / 100
}

#let cover-wrap(source, limit, width-of) = {
  let lines = ()
  let current = ""
  for word in source.split().filter(w => w != "") {
    let candidate = if current == "" { word } else { current + " " + word }
    if current != "" and width-of(candidate) > limit {
      lines.push(current)
      current = word
    } else {
      current = candidate
    }
  }
  if current != "" { lines.push(current) }
  lines
}

#let cover-wordmark(d, dark, size, dx, dy) = {
  let colors = d.color
  let svg = read("/brand/wordmark.svg")
  let head = if dark { colors.paper } else { colors.ink }
  for (name, value) in (ink: head, paper: colors.paper, red: colors.orange, box: colors.ink) {
    svg = svg.replace(regex("var\\(--" + name + "[^)]*\\)"), value)
  }
  let (vx, vy, vw, vh) = svg.match(regex("viewBox=\"([^\"]+)\"")).captures.first().split(" ").map(float)
  let (inset-x, inset-y) = COVER-WORDMARK-INSET
  let room = COVER-W - d.spine.wrap - d.wordmark.right_reserve - inset-x
  let fit = calc.min(COVER-WORDMARK-HEIGHT / vh, room / vw)
  cover-put(
    dx + size * (d.wordmark.x + inset-x),
    dy + size * (d.wordmark.top + inset-y),
    image(bytes(svg), format: "svg", width: size * fit * vw * 1pt),
  )
}

#let cover-spine(d) = cover-put(-1.5, -1.5, cover-box(d.spine.wrap + 1.5, COVER-H + 3, fill: rgb(d.color.orange)))

#let cover-headline(d, source) = {
  let words = upper(source).trim().split().filter(w => w != "")
  let width-of = (line, size) => cover-width("display", size, line)
  let size = 29.0
  let lines = ()
  while true {
    let best = none
    for split in range(1, words.len()) {
      let pair = (words.slice(0, split).join(" "), words.slice(split).join(" "))
      let (a, b) = pair.map(line => width-of(line, size))
      if calc.max(a, b) <= d.headline.width and (best == none or calc.abs(a - b) < best.at(0)) {
        best = (calc.abs(a - b), pair)
      }
    }
    lines = if best != none { best.at(1) } else { cover-wrap(words.join(" "), d.headline.width, line => width-of(line, size)) }
    if lines.len() <= 3 or size < 20 { break }
    size -= 0.5
  }
  assert(size >= 20, message: "Cover headline cannot fit: " + source)
  let colors = (rgb(d.color.ink), rgb(d.color.violet), rgb(d.color.ink))
  let baseline = d.headline.top + size
  for (index, line) in lines.enumerate() {
    let odd = calc.odd(index)
    let stroke = if odd { none } else { 0.09pt + colors.at(index) }
    cover-put(
      d.headline.x + if odd { 23 } else { -0.65 },
      baseline + if odd { 1 } else { 0 },
      cover-run("display", if odd { 28 } else { size }, line, fill: colors.at(index), tracking: -1.35, stroke: stroke),
    )
    baseline += size * 0.78
  }
}

#let cover-deck(d, source) = {
  if source == "" { return }
  let lines = cover-wrap(source, d.art.width, line => cover-width("regular", d.deck.wrap_size, line))
  assert(lines.len() <= 5, message: "Cover deck cannot fit: " + source)
  for (index, line) in lines.enumerate() {
    cover-put(
      d.art.x - if index == 0 { 0.65 } else { 0 },
      d.deck.top + d.deck.size + index * d.deck.leading,
      cover-run("regular", d.deck.size, line, fill: rgb(d.color.ink), tracking: d.deck.tracking, stretch: d.deck.horizontal_scale),
    )
  }
}

#let cover-title(title, limit, size) = {
  let size = size
  while size >= 12 and cover-width("display", size, title, tracking: 0.2) > limit { size -= 0.5 }
  assert(size >= 12, message: "Cover title cannot fit on one line: " + title)
  size
}

#let cover-right(source, edge, y, size, fill) = {
  let width = cover-width("bold", size, source, tracking: 1.4)
  cover-put(edge - width, y, cover-run("bold", size, source, fill: fill, tracking: 1.4))
}

#let cover-justified(source, x, y, size, fill, width) = {
  let spare = width - cover-width("regular", size, source)
  let gaps = calc.max(source.codepoints().len() - 1, 1)
  cover-put(x, y, cover-run("regular", size, source, fill: fill, tracking: calc.max(0, spare / gaps)))
}

#let cover-roster(source, size, limit) = {
  let names = source.split(" / ")
  for keep in range(names.len(), 0, step: -1) {
    let line = if keep == names.len() { source } else { names.slice(0, keep).join(" / ") + " / …" }
    if cover-width("regular", size, line) <= limit { return line }
  }
  "…"
}

#let cover-fade(width, top, height, stops) = cover-put(0, top, cover-box(width, height, fill: gradient.linear(dir: ttb, space: rgb, ..stops)))

#let cover-framed(d, t, spec) = {
  let (ink, a) = (rgb(d.color.ink), d.art)
  cover-spine(d)
  cover-wordmark(d, false, 1, d.spine.wrap / 2, 0)
  cover-headline(d, t.headline)
  if spec.art == none {
    cover-put(a.x, a.top, cover-box(a.width, a.height, fill: rgb(d.color.violet)))
    cover-put(a.x + a.width / 2 - 56, a.top + a.height / 2 - 56, circle(radius: 56pt, stroke: 1pt + rgb(d.color.paper)))
  } else {
    cover-put(a.x, a.top, image(spec.art, width: a.width * 1pt, height: a.height * 1pt, fit: "cover"))
  }
  cover-put(a.x, a.top, cover-box(a.width, a.height, stroke: 0.7pt + ink))
  cover-deck(d, t.contributors)
  cover-put(d.footer.x + d.spine.wrap / 2, COVER-H - d.footer.bottom, cover-run("bold", d.footer.size, t.issue + " / " + t.date_line, fill: ink, tracking: d.footer.tracking))
}

#let cover-caption(d, t, spec) = {
  let (c, s) = (d.layout.footer_caption, spec.scrim)
  let (fill, tint, wrap) = (rgb(s.fill), rgb(s.scrim), d.spine.wrap)
  let (left, title) = (d.spine.wrap + c.margin, upper(t.headline).trim())
  let right = COVER-W - c.margin
  let top = COVER-H - 46 - c.title_size - 60
  let veil = tint.transparentize((1 - s.alpha) * 100%)
  cover-put(wrap - 2, 0, image(spec.art, width: (COVER-W - wrap + 3.5) * 1pt, height: COVER-H * 1pt, fit: "cover"))
  cover-fade(COVER-W + 1.5, top, COVER-H - top, ((tint.transparentize(100%), 0%), (veil, 60 / (COVER-H - top) * 100%), (veil, 100%)))
  if s.top_gradient {
    let ink = rgb(d.color.ink)
    cover-fade(COVER-W + 1.5, 0, 120, ((ink.transparentize(58%), 0%), (ink.transparentize(100%), 100%)))
  }
  cover-spine(d)
  cover-wordmark(d, s.on_dark, c.wordmark_scale, left - (d.wordmark.x + 0.36) * c.wordmark_scale, c.wordmark_dy)
  let (base, edges, gap) = (COVER-H - 46, ("cap-height", "baseline"), 11)
  let day = cover-run("bold", 6.5, t.date_line, fill: fill, tracking: 1.4, edges: edges)
  let (dcap, dw) = (measure(day).height.pt(), measure(day).width.pt() - 1.4)
  let cap-of = size => measure(cover-run("display", size, "H", edges: edges)).height.pt()
  let numeral = cap => {
    let unit = measure(cover-run("display", 100, t.issue, edges: edges)).height.pt() / 100
    cover-run("display", cap / unit, t.issue, fill: fill, tracking: 0.2, edges: edges)
  }
  let width-of = (line, size) => cover-width("display", size, line, tracking: 0.2)
  let room = right - left - measure(numeral(cap-of(c.title_size) + 9 + dcap)).width.pt() - gap
  let (lines, size) = ((title,), c.title_size)
  while size > 20 and width-of(title, size) > room { size -= 0.5 }
  if width-of(title, size) > room {
    let words = title.split(" ")
    let best = none
    for cut in range(1, words.len()) {
      let pair = (words.slice(0, cut).join(" "), words.slice(cut).join(" "))
      let widest = calc.max(..pair.map(line => width-of(line, 20)))
      if best == none or widest < best.at(0) { best = (widest, pair) }
    }
    assert(best != none, message: "Cover title cannot fit: " + title)
    lines = best.at(1)
    size = c.title_size
    while size > 16 and lines.any(line => width-of(line, size) > room - 18) { size -= 0.5 }
    assert(lines.all(line => width-of(line, size) <= room - 18), message: "Cover title cannot fit on two lines: " + title)
  }
  let (tcap, lead) = (cap-of(size), size * 0.92)
  let top = base - (lines.len() - 1) * lead - tcap - 9 - dcap
  let run = numeral(base - top)
  let edge = right - measure(run).width.pt() - gap
  cover-put(right - measure(run).width.pt(), top, run)
  cover-put(edge - dw, top, day)
  for (index, line) in lines.enumerate() {
    let y = base - (lines.len() - 1 - index) * lead
    cover-put(edge - width-of(line, size) + 0.2, y, cover-run("display", size, line, fill: fill, tracking: 0.2))
  }
  if t.contributors != "" {
    let names = t.contributors
    let measure-names = 0.8 * (right - left)
    let wrap-at = limit => cover-wrap(names, limit, line => cover-width("regular", COVER-ROSTER, line))
    let count = wrap-at(measure-names).len()
    let measure-names = if count > 3 { measure-names } else {
      let limit = measure-names
      while limit > 40 and wrap-at(limit - 4).len() == count { limit -= 4 }
      limit
    }
    let rows = wrap-at(measure-names)
    let rows = if rows.len() <= 3 { rows } else {
      rows.slice(0, 2) + (cover-roster(rows.slice(2).join(" "), COVER-ROSTER, measure-names),)
    }
    for (index, line) in rows.enumerate() {
      cover-put(right - cover-width("regular", COVER-ROSTER, line), base + 12 + index * COVER-ROSTER * 1.3, cover-run("regular", COVER-ROSTER, line, fill: fill))
    }
  }
}

#let cover-plate(d, t, spec) = {
  let (p, ink) = (d.layout.honored_plate, rgb(d.color.ink))
  let (left, margin) = (d.spine.wrap + p.margin, p.margin)
  let (width, height) = (COVER-W - left - margin, COVER-H - 2 * margin - p.footer)
  let right = COVER-W - margin - 8
  let title = upper(t.headline).trim()
  cover-put(left, margin, image(spec.art, width: width * 1pt, height: height * 1pt, fit: "cover"))
  cover-put(left, margin, cover-box(width, height, stroke: 0.7pt + ink))
  cover-spine(d)
  cover-wordmark(d, false, p.wordmark_scale, 6 + d.spine.wrap, COVER-H - p.footer - 36)
  let size = cover-title(title, 190, p.title_size)
  cover-put(right - cover-width("display", size, title, tracking: 0.2), COVER-H - p.footer + 22, cover-run("display", size, title, fill: ink, tracking: 0.2))
  if t.contributors != "" {
    let room = right - left - 68
    cover-justified(cover-roster(t.contributors, COVER-ROSTER - 0.5, room), left + 8, COVER-H - 26, COVER-ROSTER - 0.5, ink, room)
  }
  cover-right(t.issue + " / " + t.date_line, right, COVER-H - 13, COVER-ROSTER - 0.5, ink)
}

#let cover-front-page(spec) = {
  let d = spec.design
  cover-put(0, 0, cover-box(COVER-W, COVER-H, fill: rgb(d.color.paper)))
  let modes = (framed: cover-framed, footer_caption: cover-caption, honored_plate: cover-plate)
  assert(spec.layout in modes, message: "Unknown cover layout '" + spec.layout + "': expected framed, footer_caption, or honored_plate")
  (modes.at(spec.layout))(d, spec.text, spec)
}

#let cover-statement(b, source, panel, height) = {
  let size = b.statement_max_size
  while size >= b.statement_min_size {
    let lines = cover-wrap(source, panel, line => cover-width("serif", size, line))
    let leading = size * b.statement_leading_ratio
    let rise = measure(cover-run("serif", size, lines.first(), edges: ("bounds", "baseline"))).height.pt()
    let drop = measure(cover-run("serif", size, lines.last(), edges: ("baseline", "bounds"))).height.pt()
    let extent = rise + (lines.len() - 1) * leading + drop
    if extent <= height { return (lines: lines, size: size, rise: rise, leading: leading, extent: extent) }
    size -= 0.5
  }
  assert(false, message: "Back-cover issue statement cannot fit: " + source)
}

#let cover-back-page(spec) = {
  let (d, b, t) = (spec.design, spec.design.back, spec.text)
  let (ink, paper) = (rgb(d.color.ink), rgb(d.color.paper))
  cover-put(-b.overdraw, -b.overdraw, cover-box(COVER-W + 2 * b.overdraw, COVER-H + 2 * b.overdraw, fill: rgb(d.color.orange)))
  let room = COVER-W - d.spine.wrap - b.mass_x - 6
  let size = b.mass_size
  while size >= 72 and not t.mass.all(word => cover-width("bold", size, word, tracking: b.mass_tracking) <= room) { size -= 0.5 }
  assert(size >= 72, message: "Back-cover display words cannot fit: " + t.mass.join(" / "))
  cover-put(0, 0, block(width: (COVER-W - d.spine.wrap) * 1pt, height: COVER-H * 1pt, clip: true, {
    for (index, word) in t.mass.enumerate() {
      let fill = if index == 0 { rgb(d.color.violet) } else { ink }
      cover-put(b.mass_x, b.mass_top + size + index * b.mass_leading * size / b.mass_size, cover-run("bold", size, word, fill: fill, tracking: b.mass_tracking))
    }
  }))
  let (panel, pad) = (COVER-W - b.panel_x - b.panel_right, b.panel_padding)
  let fit = cover-statement(b, t.statement, panel - 2 * pad, COVER-H - b.panel_top - b.panel_bottom - 2 * pad)
  cover-put(b.panel_x, b.panel_top, cover-box(panel, fit.extent + 2 * pad, fill: paper))
  for (index, line) in fit.lines.enumerate() {
    cover-put(b.panel_x + pad, b.panel_top + pad + fit.rise + index * fit.leading, cover-run("serif", fit.size, line, fill: ink, tracking: -0.12))
  }
  cover-put(b.slug_x, COVER-H - b.slug_bottom, cover-run("bold", b.slug_size, t.slug, fill: paper, tracking: b.slug_tracking))
}

#let column(body) = pad(left: RAIL, right: RAIL - MEASURE-DELTA, body)

#let NO-ESCAPE = (left: 0pt, right: 0pt)
#let BAND-ESCAPE = (left: -RAIL, right: MEASURE-DELTA - RAIL)
#let COMPACT-ESCAPE = (left: 0pt, right: COMPACT-BAND-INSET + MEASURE-DELTA)
#let FIGURE-ESCAPE = (left: 0pt, right: MEASURE-DELTA)

#let flow-counter = counter("mag-flow")

#let flow-mark(kind, layout, body, id: none, float: none) = {
  flow-counter.step()
  context [#metadata((
      kind: kind,
      layout: layout,
      index: flow-counter.get().first(),
      id: id,
      float: float,
    ))<mag-flow>]
  context body(flow-counter.get().first())
}

#let figure-spec(layout, anchor) = {
  let opener = anchor == OPENER-ANCHOR
  let compact = layout == COMPACT-BAND
  (
    escape: if BAND-LAYOUTS.contains(layout) {
      BAND-ESCAPE
    } else if compact { COMPACT-ESCAPE } else { FIGURE-ESCAPE },
    gap: if compact { COMPACT-FIGURE-GAP } else { FIGURE-GAP },
    shift: if BAND-LAYOUTS.contains(layout) { RAIL } else { 0pt },
    max-height: if layout == "full_band" {
      FULL-FIGURE-MAX-HEIGHT
    } else if opener {
      OPENER-FIGURE-MAX-HEIGHT
    } else if compact { COMPACT-FIGURE-MAX-HEIGHT } else { FIGURE-MAX-HEIGHT },
  )
}

#let is-band(layout) = BAND-LAYOUTS.contains(layout) or layout == COMPACT-BAND

#let next-flow(index) = query(<mag-flow>).filter(m => m.value.index == index + 1).map(m => m.value).at(0, default: (kind: none, layout: none, float: none))
#let band-anchored(index) = next-flow(index).kind == "figure" and is-band(next-flow(index).layout)

#let backdrop(body) = [#body<mag-backdrop>]
#let prose(body) = [#body<mag-prose>]
#let caption-edge = state("mag-caption-edge", none)
#let edge-prose(body) = context {
  let edge = caption-edge.get()
  if edge == "band" [#body<mag-prose-band>] else if edge == "compact" [#body<mag-prose-compact>] else [#body<mag-prose>]
}
#let clipped(width, height, body) = box(width: width, height: height, clip: true, body)

#let tail-baseline(at) = query(selector(<mag-end-baseline>).before(at)).last().location().position()
#let tail-room(baseline) = PAGE-HEIGHT - baseline.y - TAIL-FRAME-BOTTOM - TAIL-CLEARANCE

#let tail-layer() = context {
  let page = here().page()
  for mark in query(<mag-tail-art>) {
    let (tail, baseline) = (mark.value, tail-baseline(mark.location()))
    if baseline.page == page and tail-room(baseline) >= tail.height {
      let x = if calc.odd(page) { MARGIN-INNER } else { MARGIN-OUTER }
      let y = PAGE-HEIGHT - MARGIN-BOTTOM + DATUM - tail.height - TAIL-FOOT-F32-LIFT
      place(top + left, dx: x + RAIL, dy: y, clipped(MEASURE, tail.height, image(tail.path, width: MEASURE, height: tail.height, fit: tail.fit)))
    }
  }
}

#let bookmark(level, body) = place(hide(heading(level: level, bookmarked: true, outlined: false, numbering: none, body)))

#let reader(body) = {
  set page(
    width: PAGE-WIDTH,
    height: PAGE-HEIGHT,
    margin: (
      top: MARGIN-TOP,
      bottom: MARGIN-BOTTOM,
      inside: MARGIN-INNER,
      outside: MARGIN-OUTER,
    ),
    binding: left,
    foreground: {
      tail-layer()
      furniture()
    },
  )
  set text(
    font: SERIF,
    size: BODY-SIZE,
    weight: 400,
    fill: INK,
    features: PROSE-FIGURES,
    ..(costs: (hyphenation: 300%, runt: 250%)),
    hyphenate: false,
    ..edges(BODY-SIZE, BODY-LEADING, HALF-SERIF),
  )
  set par(
    leading: 0pt,
    spacing: PARAGRAPH-AFTER,
    justify: false,
    linebreaks: "optimized",
    first-line-indent: 0pt,
  )
  cover-page("mag-cover-front", cover-front-page)
  credits-page()
  body
  plain-page()
  cover-page("mag-cover-back", cover-back-page)
}

#let edition-header(body) = body
#let publication-name(body) = publication.update(_ => body)
#let issue-line(body) = fact("issue", body)
#let edition-title(body) = fact("title", body)
#let edition-subtitle(body) = none
#let edition-date(body) = fact("date", body)

#let tag(name, body) = metadata((tag: name, body: body))

#let parts(body) = {
  let items = if body.has("children") { body.children } else { (body,) }
  items.filter(i => i.func() == metadata).map(i => i.value)
}

#let part(rows, name) = {
  let found = rows.filter(r => r.tag == name)
  if found.len() == 0 { none } else { found.first().body }
}

#let contents-kicker(body) = tag("kicker", body)
#let contents-label(body) = tag("label", body)
#let entry-label(body) = tag("entry-label", body)
#let entry-title(body) = tag("entry-title", body)
#let entry-author(body) = tag("entry-author", body)
#let contents-entry(destination: none, body) = metadata((
  tag: "entry",
  body: body,
  destination: destination,
))

#let contents-caption(body, tracking: 0pt) = small-caps(body, tracking: 0.16em)

#let subtitle-split(full) = {
  let m = full.match(regex("(: | \u{2014} |\u{2014})"))
  if m == none { (full, "") } else { (full.slice(0, m.end), full.slice(m.end)) }
}

#let contents-row(entry, size) = {
  let rows = parts(entry.body)
  let (label, title, author) = ("entry-label", "entry-title", "entry-author").map(name => part(rows, name))
  let target = query(<mag-piece>).find(m => m.value.id == entry.destination).location()
  let leading = size * 1.1
  let room = LIVE-WIDTH - CONTENTS-FOLIO - 12pt
  let folio = text(font: SERIF, size: size, fill: STONE, features: LINING, ..edges(size, leading, HALF-SERIF), str(counter(page).at(target).first()))
  let (roman, italic) = (plain-text(title).trim(), "")
  let tokens = roman.split(" ").filter(w => w != "").map(w => (w, false)) + italic.split(" ").filter(w => w != "").map(w => (w, true))
  let face(body) = text(font: SERIF, size: size, weight: 600, hyphenate: false, features: PROSE-FIGURES, ..edges(size, leading, HALF-SERIF), body)
  let run(from, to) = face(tokens.slice(from, to).map(((w, it)) => if it { text(style: "italic", w) } else { w }).join(" "))
  let byline = if author == none { none } else {
    h(0.5em) + text(font: SERIF, size: size * 0.86, style: "italic", fill: STONE, features: PROSE-FIGURES, ..edges(size * 0.86, leading, HALF-SERIF), author)
  }
  let whole = run(0, tokens.len()) + byline
  let lines = if measure(whole).width <= room { (whole,) } else {
    let best = none
    for cut in range(1, tokens.len()) {
      let (first, second) = (run(0, cut), run(cut, tokens.len()) + byline)
      let widths = (measure(first).width, measure(second).width)
      if widths.at(0) <= room and widths.at(1) <= room and (best == none or calc.max(..widths) < best.at(0)) {
        best = (calc.max(..widths), (first, second))
      }
    }
    if best == none { (whole,) } else { best.at(1) }
  }
  let words = {
    set par(leading: 0pt, spacing: 0pt, justify: false, first-line-indent: 0pt, hanging-indent: 0pt)
    if label != none { block(below: 3pt, small-caps(label, size: 7.6pt, fill: RUBRIC, tracking: 0.12em)) }
    link(target, lines.join(linebreak()))
  }
  grid(columns: (CONTENTS-FOLIO, 1fr), align: (right + top, left + top), column-gutter: 12pt, link(target, folio), words)
}

#let contents(body) = {
  pagebreak(weak: true)
  let rows = parts(body)
  let entries = rows.filter(r => r.tag == "entry")
  let live = PAGE-HEIGHT - MARGIN-TOP - MARGIN-BOTTOM
  block(height: live, width: 100%, context {
    let (kicker, label) = ("kicker", "label").map(name => part(rows, name))
    let head = 0pt
    if kicker != none {
      let issue = plain-text(kicker).split(" / ").first()
      place(top + left, dy: 6pt, contents-caption(issue))
    }
    if label != none {
      place(top + left, bookmark(1, label))
      place(top + left, dy: 18pt, block(text(font: SERIF, size: 28pt, weight: 600, fill: INK, ..edges(28pt, 32pt, HALF-SERIF), label)))
    }
    let first = 82pt
    let room = live - first
    let gaps = calc.max(1, entries.len() - 1)
    let gap-at = size => (room - entries.map(e => measure(block(width: LIVE-WIDTH, contents-row(e, size))).height).sum()) / gaps
    let size = 11pt
    while size > 8.5pt and gap-at(size) < CONTENTS-GAP.min { size -= 0.25pt }
    assert(gap-at(size) >= CONTENTS-GAP.min, message: "The contents cannot fit " + str(entries.len()) + " entries on one page; shorten the longest titles")
    let gap = calc.min(gap-at(size), CONTENTS-GAP.max)
    place(top + left, dy: first, block(width: LIVE-WIDTH, {
      set block(spacing: 0pt)
      for (index, entry) in entries.enumerate() {
        contents-row(entry, size)
        if index + 1 < entries.len() { v(gap) }
      }
    }))
  })
  pagebreak(weak: true)
}

#let opener-parts = state("opener-parts", none)
#let opener-end() = [#metadata(none)<mag-opener-end>]

#let plain-head = state("plain-head", none)
#let PLAIN-TITLE-TOP = DATUM + 37pt
#let PLAIN-LABEL-TOP = 7.53085pt
#let LABEL-TRACKING = 0.45pt
#let PLAIN-NOTE-DROP = 12pt
#let NOTE-LEADING = 9.45pt

#let plain-opener(size: 35pt, field: 0pt, tracking: 0pt, title: "", wide: false, body) = {
  plain-head.update((size: size, tracking: tracking, title: title, escape: if wide { RAIL } else { 0pt }))
  block(height: field, width: 100%, above: 0pt, below: 0pt, breakable: false, body)
  plain-head.update(none)
}

#let SUBTITLE = regex("(: | \u{2014} |\u{2014}).+")

#let title-text(size, body, fill: INK, leading: OPENER-TITLE-LEADING-RATIO) = {
  show regex("\\S+-\\S+"): it => box(it)
  text(
    font: SERIF,
    size: size,
    weight: 600,
    fill: fill,
    hyphenate: false,
    tracking: -0.005em,
    features: PROSE-FIGURES,
    ..edges(size, size * leading, HALF-SERIF),
    body,
  )
}

#let balanced(width, leading, body) = {
  let set-at(w) = block(width: w, {
    set par(justify: false, linebreaks: "simple", first-line-indent: 0pt, leading: 0pt, spacing: 0pt)
    body
  })
  let lines(w) = calc.round(measure(set-at(w)).height / leading)
  let target = lines(width)
  if target < 2 { return set-at(width) }
  let (low, high) = (width * 0.5, width)
  for _ in range(10) {
    let middle = (low + high) / 2
    if lines(middle) <= target { high = middle } else { low = middle }
  }
  block(width: width, set-at(high + 0.5pt))
}

#let plain-title-text(size, body) = title-text(size, body)

#let plain-title-block(head, body) = block(width: MEASURE + MEASURE-DELTA + 2 * head.escape, plain-title-text(head.size, body))

#let plain-byline-baseline(head) = {
  let leading = head.size * OPENER-TITLE-LEADING-RATIO
  let lines = calc.round(measure(plain-title-block(head, head.title)).height / leading)
  PLAIN-TITLE-TOP + head.size + lines * leading + 10pt
}

#let unspaced(body) = if body.has("children") {
  body.children.filter(c => c != [ ]).join()
} else { body }

#let escaped(body) = pad(left: -OPENER-ESCAPE, right: -OPENER-ESCAPE, body)

#let collect(name, body) = opener-parts.update(p => if p == none {
  p
} else {
  p + ((tag: name, body: body),)
})

#let frame-ring(width, height, border) = curve(
  fill: PAPER-INK,
  fill-rule: "even-odd",
  stroke: none,
  curve.move((border, border)),
  curve.line((width - border, border)),
  curve.line((width - border, height - border)),
  curve.line((border, height - border)),
  curve.close(mode: "straight"),
  curve.move((0pt, 0pt)),
  curve.line((width, 0pt)),
  curve.line((width, height)),
  curve.line((0pt, height)),
  curve.close(mode: "straight"),
)

#let covered(art, width, height) = {
  let scale = calc.max(width / art.pixels.at(0), height / art.pixels.at(1))
  let (w, h) = (art.pixels.at(0) * scale, art.pixels.at(1) * scale)
  box(width: width, height: height, clip: true, place(
    top + left,
    dx: (width - w) * OPENER-FOCUS.at(0),
    dy: (height - h) * OPENER-FOCUS.at(1),
    image(art.path, width: w, height: h, fit: "stretch"),
  ))
}

#let opener-art(art) = {
  place(top + left, frame-ring(OPENER-RAIL, OPENER-FRAME-HEIGHT, OPENER-BORDER))
  if art != none {
    place(top + left, dx: OPENER-BORDER, dy: OPENER-BORDER, covered(
      art,
      OPENER-RAIL - 2 * OPENER-BORDER,
      OPENER-FRAME-HEIGHT - 2 * OPENER-BORDER,
    ))
  }
}

#let kicker-text(body, size: LABEL-SIZE, tracking: 0.14em) = {
  show regex("\s*/\s*"): h(0.5em) + text(fill: STONE, "\u{00b7}") + h(0.5em)
  small-caps(body, size: size, tracking: tracking)
}

#let content-label(body) = context if plain-head.get() != none {
  let escape = plain-head.get().escape
  let items = (if body.has("children") { body.children } else { (body,) }).enumerate().map(((i, item)) => {
    (if i == 1 { box(move(dx: LABEL-TRACKING, item)) } else { unspaced(item) }) + h(LABEL-TRACKING)
  })
  place(top + left, dx: -escape, dy: PLAIN-LABEL-TOP + ZERO-LEADING-SANS, [#box(width: 100% - MEASURE-DELTA + 2 * escape, small-caps(items.intersperse(h(1fr)).join(), tracking: 0.12em))])
} else if opener-parts.get() == none {
  block(kicker-text(body), spacing: 9pt)
} else {
  collect("label", body)
}
#let label-primary(body) = text(fill: RUBRIC, body)
#let own-run(body) = context if plain-head.get() == none { h(0pt) + body } else { body }
#let label-secondary(body) = own-run(text(body))
#let label-separator(body) = own-run(text(body))
#let label-date(body) = own-run(text(fill: STONE, body))

#let opener-title-text(size, body) = title-text(size, body, fill: PAPER-INK)

#let wrapped(width, body) = block(width: width, {
  set par(leading: 0pt, spacing: 0pt, linebreaks: "simple", justify: false, first-line-indent: 0pt)
  body
})

#let piece-title(body) = context if plain-head.get() != none {
  let head = plain-head.get()
  let (size, leading) = (head.size, head.size * OPENER-TITLE-LEADING-RATIO)
  place(top + left, dx: -head.escape, dy: PLAIN-TITLE-TOP + size - (leading / 2 + HALF-DISPLAY * size), bookmark(1, body) + plain-title-block(head, body))
} else if opener-parts.get() == none {
  block(
    bookmark(1, body) + title-text(28pt, body, leading: 1.04),
    spacing: 10pt,
  )
} else {
  collect("title", body)
}

#let byline-prefix(body) = text(style: "italic", features: OLDSTYLE, tracking: 0pt, body) + h(OPENER-PREFIX-GAP * 1em)
#let byline-name(body) = text(weight: 600, body)
#let qr-symbol(rows, side: OPENER-QR) = {
  let unit = side / (rows.len() + 2 * OPENER-QR-QUIET)
  let svg(length) = calc.round(length / 1pt, digits: 4) * 1pt
  let runs = ()
  for (y, row) in rows.enumerate() {
    for run in row.matches(regex("1+")) {
      let (x0, y0) = (svg((run.start + OPENER-QR-QUIET) * unit), svg((y + OPENER-QR-QUIET) * unit))
      let (x1, y1) = (x0 + svg(run.text.len() * unit), y0 + svg(unit))
      runs += (curve.move((x0, y0)), curve.line((x1, y0)), curve.line((x1, y1)), curve.line((x0, y1)), curve.close(mode: "straight"))
    }
  }
  place(top + left, rect(width: side, height: side, fill: white, stroke: none))
  place(top + left, curve(fill: INK, stroke: none, ..runs))
}

#let PLAIN-BYLINE-SIZE = 8.6pt
#let byline-text(body, tracking: 0pt) = text(
  font: SERIF,
  size: PLAIN-BYLINE-SIZE,
  weight: 400,
  fill: PAPER-INK,
  tracking: tracking,
  ..flat,
  body,
)

#let code-quiet(code) = OPENER-QR-QUIET * PLAIN-QR / (code.len() + 2 * OPENER-QR-QUIET)
#let credit-inset(code) = if code == none { 0pt } else { PLAIN-QR - 2 * code-quiet(code) + CODE-CREDIT-GAP }
#let byline(code: none, body) = context if opener-parts.get() == none {
  let head = plain-head.get()
  let tracking = if head == none { 0pt } else { head.tracking }
  let line = byline-text(body, tracking: tracking)
  let credit = {
    if code != none {
      let quiet = code-quiet(code)
      place(top + left, dx: -quiet, dy: -PLAIN-BYLINE-SIZE * INTER-CAP - quiet, qr-symbol(code, side: PLAIN-QR))
    }
    pad(left: credit-inset(code), line)
  }
  if head == none {
    block(above: 14pt, below: 0pt, credit)
  } else {
    place(top + left, dx: -head.escape, dy: plain-byline-baseline(head), block(width: 100% + 2 * head.escape, credit))
  }
} else {
  collect("byline", body)
}
#let note-text(body) = text(
  font: SERIF,
  size: OPENER-NOTE-SIZE,
  style: "italic",
  fill: STONE,
  features: OLDSTYLE,
  ..edges(OPENER-NOTE-SIZE, OPENER-NOTE-LEADING, HALF-SERIF),
  body,
)
#let author-note(code: none, body) = context if opener-parts.get() == none {
  let head = plain-head.get()
  let note = block(
    width: 100%,
    inset: (left: credit-inset(code)),
    above: 7.49326pt,
    below: 0pt,
    { set par(justify: false, first-line-indent: 0pt); note-text(body) },
  )
  if head == none { note } else {
    let baseline = plain-byline-baseline(head) + PLAIN-NOTE-DROP
    place(top + left, dy: baseline - OPENER-NOTE-LEADING / 2 - HALF-SERIF * OPENER-NOTE-SIZE, note)
  }
} else {
  collect("note", body)
}
#let provenance(body) = none
#let source-link(destination: none, source-id: none, code: none, body) = context if opener-parts.get() != none {
  collect("source", (destination: destination, code: code))
}

#let opener-part(rows, name) = {
  let found = rows.filter(r => r.tag == name)
  if found.len() == 0 { none } else { found.first().body }
}

#let credit-column(rows) = {
  let note = opener-part(rows, "note")
  set par(justify: false, first-line-indent: 0pt)
  block(above: 0pt, below: 0pt, text(
    font: SERIF,
    size: OPENER-BYLINE-SIZE,
    fill: PAPER-INK,
    ..edges(OPENER-BYLINE-SIZE, OPENER-BYLINE-LEADING, HALF-SERIF),
    opener-part(rows, "byline"),
  ))
  if note != none {
    block(above: OPENER-NOTE-ABOVE, below: 0pt, note-text(note))
  }
}

#let standfirst-cuts(body) = {
  let parts = if body.has("children") { body.children } else { (body,) }
  let words(part) = if part.func() == text { part.text } else if part == [ ] { " " } else { "\u{fffc}" }
  let cuts = ()
  for (i, part) in parts.enumerate() {
    cuts += words(part).matches(regex("\\s+")).map(m => (i, m.start)).filter(((i, at)) => i > 0 or at > 0)
  }
  cuts.map(((i, at)) => (
    (parts.slice(0, i) + (text(words(parts.at(i)).slice(0, at)),)).join(),
    ((text(words(parts.at(i)).slice(at).trim(at: start)),) + parts.slice(i + 1)).join(),
  ))
}

#let initial-split(body) = {
  let parts = if body.has("children") { body.children } else { (body,) }
  let count = parts.position(p => not ((p.func() != link and p.has("text")) or p == [ ]))
  let count = if count == none { parts.len() } else { count }
  if count == 0 and parts.first().func() == strong and plain-text(parts.first().body).len() > 1 {
    let letters = plain-text(parts.first().body).clusters()
    return (cap: letters.first(), lead: [], rest: (strong(letters.slice(1).join(default: "")),) + parts.slice(1))
  }
  if count == 0 or parts.first().func() != text { return none }
  let lead-text = parts.slice(0, count).map(p => if p == [ ] { " " } else { p.text }).join()
  let letters = lead-text.clusters()
  let lead = letters.position(c => c.match(regex("^\\p{P}$")) == none)
  if lead == none { return none }
  let rest = letters.slice(lead + 1).join(default: "")
  let words = rest.matches(regex("\\S+"))
  let cut = if rest.starts-with(" ") { DROP-SMALL-CAPS-WORDS - 1 } else { DROP-SMALL-CAPS-WORDS }
  let stop = if cut <= 0 { 0 } else if words.len() >= cut { words.at(cut - 1).end } else { rest.len() }
  (
    cap: letters.slice(0, lead + 1).join(),
    lead: text(features: SMALL-CAPS, tracking: 0.04em, rest.slice(0, stop)),
    rest: (text(rest.slice(stop)),) + parts.slice(count),
  )
}

#let initial(body) = {
  let split = initial-split(body)
  if split == none { return body }
  text(weight: 400, fill: RUBRIC, split.cap)
  split.lead
  split.rest.join()
}

#let drop-cap-size(size, leading) = ((DROP-LINES - 1) * leading + BODY-CAP-HEIGHT * size) / DISPLAY-CAP-HEIGHT

#let opening-paragraph(size, leading, body) = layout(region => {
  let split = initial-split(body)
  let plain = par(text(size: size, ..edges(size, leading, HALF-SERIF), body))
  if split == none { return plain }
  let cap-size = drop-cap-size(size, leading)
  let cap = text(font: SERIF, size: cap-size, weight: 400, fill: RUBRIC, top-edge: "cap-height", bottom-edge: "baseline", split.cap)
  let indent = measure(cap).width + DROP-GAP
  let narrow = region.width - indent
  let set-text(body) = text(size: size, ..edges(size, leading, HALF-SERIF), body)
  let rest = ([#split.lead],) + split.rest
  let whole = rest.join()
  let lines-of(body) = calc.round(measure(block(width: narrow, par(set-text(body)))).height / leading)
  let (head, tail) = (whole, none)
  if lines-of(whole) > DROP-LINES {
    let cuts = standfirst-cuts(whole)
    let (low, high) = (0, cuts.len())
    while low < high {
      let middle = calc.quo(low + high + 1, 2)
      if lines-of(cuts.at(middle - 1).first() + linebreak()) <= DROP-LINES { low = middle } else { high = middle - 1 }
    }
    if low > 0 { (head, tail) = cuts.at(low - 1) }
  }
  let rise = leading / 2 + line-center(HALF-SERIF, size) - BODY-CAP-HEIGHT * size
  block(above: 0pt, below: 0pt, width: 100%, {
    set par(first-line-indent: 0pt)
    place(top + left, dy: rise, cap)
    pad(left: indent, par(set-text(if tail == none { head } else { head + linebreak() })))
    if tail != none { par(set-text(tail)) }
  })
})

#let standfirst-text(density, body) = opening-paragraph(density.standfirst-size, density.standfirst-leading, body)

#let opener-stack(density, title, rows, body) = {
  let credit = measure(wrapped(OPENER-META-MEASURE, credit-column(rows))).height
  let standfirst = measure(wrapped(OPENER-RAIL, standfirst-text(density, body))).height
  (
    OPENER-ART-FLOW
      + density.label
      + OPENER-LABEL-LEADING
      + density.title-gap
      + title.lines * title.size * OPENER-TITLE-LEADING-RATIO
      + density.tick
      + calc.max(OPENER-QR, credit)
      + 2 * density.meta-pad
      + OPENER-META-RULE
      + density.standfirst-gap
      + standfirst
  )
}

#let source-code(source) = {
  let code = rect(width: OPENER-QR, height: OPENER-QR, fill: none, stroke: none)
  if source == none { return code }
  place(top + left, link(source.destination, box(width: OPENER-QR, height: OPENER-QR)))
  link(source.destination, box(width: OPENER-QR, height: OPENER-QR, if source.code != none { qr-symbol(source.code) }))
}

#let standfirst-keep(body, fits, lines) = {
  let cuts = standfirst-cuts(body)
  let (low, high) = (0, cuts.len())
  while low < high {
    let middle = calc.quo(low + high + 1, 2)
    if fits(OPENER-COMPACT, cuts.at(middle - 1).first()) { low = middle } else { high = middle - 1 }
  }
  let runt(keep) = keep > 0 and lines(cuts.at(keep - 1).last()) < OPENER-MIN-CARRY
  if runt(low) and fits(OPENER-SQUEEZED, body) { return none }
  while low > 1 and runt(low) { low -= 1 }
  low
}

#let opener-page(rows, body, split) = {
  let title = opener-part(rows, "title")
  let titles = opener-part(rows, "titles")
  let rail(body) = block(width: OPENER-RAIL, above: 0pt, below: 0pt, {
    set par(justify: false, first-line-indent: 0pt)
    body
  })
  let label = rail(box(height: OPENER-LABEL-LEADING, align(bottom, kicker-text(opener-part(rows, "label"), size: OPENER-LABEL-SIZE, tracking: OPENER-LABEL-TRACKING * 1em))))
  let heading(density) = rail({
    set par(leading: 0pt, spacing: 0pt)
    let size = titles.at(int(density != OPENER-STANDARD)).size
    balanced(OPENER-RAIL, size * OPENER-TITLE-LEADING-RATIO, text(tracking: OPENER-TITLE-TRACKING * size, opener-title-text(size, title)))
  })
  let meta = rail(grid(
    columns: (1fr, OPENER-QR),
    column-gutter: OPENER-GAP,
    align: horizon,
    credit-column(rows),
    source-code(opener-part(rows, "source")),
  ))
  let set-standfirst(density, body) = rail({
    set par(leading: 0pt, spacing: 0pt, justify: false)
    standfirst-text(density, body)
  })
  let y-label(density) = OPENER-ART-HEIGHT - OPENER-ART-LIFT + density.label
  let y-title(density) = y-label(density) + measure(label).height + density.title-gap
  let y-tick(density) = y-title(density) + measure(heading(density)).height + density.tick
  let y-meta(density) = y-tick(density) + density.meta-pad
  let y-rule(density) = y-meta(density) + measure(meta).height + density.meta-pad
  let y-standfirst(density) = y-rule(density) + OPENER-META-RULE + density.standfirst-gap
  let fits(density, body) = y-standfirst(density) + measure(set-standfirst(density, body)).height <= CONTENT-HEIGHT
  let lines(body) = calc.round(measure(set-standfirst(OPENER-COMPACT, body)).height / OPENER-COMPACT.standfirst-leading)
  let density = OPENER-STANDARD
  if split or opener-stack(density, titles.first(), rows, body) + OPENER-LINE-RESERVE > CONTENT-HEIGHT {
    density = OPENER-COMPACT
  }
  if not split {
    let keep = if fits(density, body) { none } else { standfirst-keep(body, fits, lines) }
    if keep == none and not fits(density, body) { density = OPENER-SQUEEZED }
    [#metadata(keep)<mag-standfirst>]
  }
  let standfirst = set-standfirst(density, body)
  let at(y, body) = place(top + left, dx: -OPENER-ESCAPE, dy: y, body)
  block(breakable: false, above: 0pt, below: 0pt, width: 100%, height: y-standfirst(density) + measure(standfirst).height, {
    at(y-label(density), label)
    at(y-title(density), heading(density))
    at(y-title(density), bookmark(1, title))
    at(y-standfirst(density), standfirst)
    place(top + left, dx: OPENER-OFFSET - OPENER-ESCAPE, dy: OPENER-OFFSET - OPENER-ART-LIFT, {
      rect(width: OPENER-RAIL, height: OPENER-FRAME-HEIGHT, fill: SIGNAL-ORANGE, stroke: none)
    })
    at(y-rule(density), rect(width: OPENER-RAIL, height: OPENER-META-RULE, fill: COOL-GRAY, stroke: none))
    at(y-meta(density), meta)
    at(-OPENER-ART-LIFT, opener-art(opener-part(rows, "art")))
  })
}

#let opener-standfirst(rows, body, split) = {
  opener-page(rows, body, split)
  opener-parts.update(_ => none)
  context v(PAGE-HEIGHT - MARGIN-BOTTOM - here().position().y)
}

#let doc-link(destination: none, title: none, body) = {
  link(destination, body)
}

#let code-pad = text(font: MONO, size: CODE-PAD-X / MONO-ADVANCE, ..flat, "\u{a0}")

#let inline-code(body) = context {
  let size = CODE-SIZE * text.size
  let leading = (text.top-edge - text.bottom-edge).to-absolute()
  let lift = calc.min(0pt, text.top-edge.to-absolute() - leading / 2 - line-center(HALF-SERIF, text.size))
  let (top-edge, bottom-edge) = edges(size, leading, HALF-MONO)
  code-pad
  highlight(
    fill: CODE-PALE,
    radius: CODE-RADIUS,
    extent: CODE-PAD-X,
    top-edge: (0.5 + HALF-MONO) * size + CODE-PAD-Y,
    bottom-edge: (HALF-MONO - 0.5) * size - CODE-PAD-Y,
    text(
      font: MONO,
      size: size,
      weight: 500,
      fill: CODE-VIOLET,
      hyphenate: false,
      top-edge: top-edge + lift,
      bottom-edge: bottom-edge + lift,
      body,
    ),
  )
  code-pad
}

#let doc-paragraph(standfirst: false, roster: false, split: false, body) = {
  if standfirst {
    context {
      let rows = opener-parts.get()
      if rows == none {
        block(prose(opening-paragraph(12pt, 16pt, body)), below: 14pt)
      } else {
        opener-standfirst(rows, body, split)
      }
    }
  } else {
    prose(par(body))
  }
}

#let HEADINGS = (
  (font: SERIF, size: 18pt, leading: 22pt, above: 28pt, after-standfirst: 31pt, below: 6pt, style: "normal", weight: 600, tracking: 0em, features: PROSE-FIGURES, half: HALF-SERIF),
  (font: SERIF, size: 15pt, leading: 18pt, above: 24pt, after-standfirst: 28pt, below: 4pt, style: "normal", weight: 600, tracking: 0em, features: PROSE-FIGURES, half: HALF-SERIF, drop: 14pt),
  (font: SERIF, size: 11.5pt, leading: 14pt, above: 16pt, after-standfirst: 23pt, below: 3pt, style: "normal", weight: 600, tracking: 0em, features: PROSE-FIGURES, half: HALF-SERIF, drop: 10pt),
)

#let heading-stack(level, spec, above, escape, drop, body, sticky: false) = {
  block(above: above, below: 0pt, breakable: false, sticky: true, width: 100%, inset: escape, {
    bookmark(level, body)
    set par(justify: false, first-line-indent: 0pt)
    move(dy: drop, text(
      font: spec.font,
      size: spec.size,
      weight: spec.weight,
      style: spec.style,
      tracking: spec.tracking,
      features: spec.features,
      fill: INK,
      hyphenate: false,
      ..pinned(spec.leading),
      body,
    ))
    v(spec.below)
    block(height: HEADING-CLEARANCE, width: 100%, spacing: 0pt, [])
  })
  v(-HEADING-CLEARANCE)
}

#let doc-heading(level: 1, standfirst: false, body) = {
  let spec = HEADINGS.at(calc.min(level, 3) - 1)
  flow-mark("heading", none, index => {
    let anchor = level >= 2 and level <= 3 and band-anchored(index) and next-flow(index).float != true
    let midpage = anchor and here().position().y > MARGIN-TOP + PAGE-TOP-EPSILON
    heading-stack(
      level,
      spec,
      if anchor { auto } else if standfirst { spec.after-standfirst } else { spec.above },
      if anchor { BAND-ESCAPE } else { NO-ESCAPE },
      if midpage { spec.drop } else { 0pt },
      body,
      sticky: next-flow(index).kind == "figure",
    )
  })
}

#let section-break() = block(above: 14pt, below: 14pt, width: 100%, align(center, line(length: 36pt, stroke: 0.5pt + STONE)))

#let ruled(pad-left, pad-rest, fill-color, body) = backdrop(pad(left: 2pt, right: pad-left - MEASURE-DELTA, block(width: 100%, spacing: 0pt, stroke: (left: 1pt + COOL-GRAY), inset: (left: pad-left - 2pt, y: 1pt), body)))

#let doc-quote(body) = block(
  {
    set par(spacing: 6pt, justify: false)
    set text(size: QUOTE-SIZE, ..edges(QUOTE-SIZE, QUOTE-LEADING, HALF-SERIF))
    ruled(QUOTE-PAD, 0pt, none, body)
  },
  above: 12pt,
  below: 12pt,
)

#let unbroken(run) = run.replace(regex("\\S{30,}"), token => token.text.clusters().join("\u{200B}"))

#let code-runs(source, inks) = {
  let runs = if inks.len() == 0 { ((source.len(), none),) } else { inks }
  assert(runs.map(r => r.at(0)).sum() == source.len(), message: "the code inks do not cover the code block")
  let at = 0
  for (length, ink) in runs {
    let run = source.slice(at, at + length)
    at += length
    if ink == none { unbroken(run) } else { text(fill: ink, unbroken(run)) }
  }
}

#let code-ruled(pad-left, pad-rest, fill-color, body) = backdrop(block(fill: fill-color, outset: (right: -MEASURE-DELTA), width: 100%, spacing: 0pt, pad(
  left: QUOTE-RULE / 2,
  block(
    stroke: (left: QUOTE-RULE + CODE-VIOLET),
    inset: (left: pad-left + QUOTE-RULE / 2, rest: pad-rest),
    width: 100%,
    above: 0pt,
    below: 0pt,
    body,
  ),
)))

#let code-panel(inks: (), collapse: false, body) = {
  set par(leading: 0pt, spacing: 0pt, justify: false, first-line-indent: 0pt)
  set text(
    font: MONO,
    size: CODE-BLOCK-SIZE,
    weight: 400,
    fill: CODE-INK,
    hyphenate: false,
    features: (),
    ..edges(CODE-BLOCK-SIZE, CODE-BLOCK-SIZE * CODE-BLOCK-LEADING, HALF-MONO),
  )
  let lines = body.text.split("\n").map(line => line.trim().replace(regex("\\s+"), " "))
  code-ruled(CODE-BLOCK-PAD, CODE-BLOCK-PAD, CODE-PALE, if collapse {
    lines.join(linebreak())
  } else {
    code-runs(body.text, inks)
  })
}

#let doc-code(lang: "", inks: (), body) = context {
  let panel = code-panel(inks: inks, body)
  let tall = measure(block(width: MEASURE + MEASURE-DELTA, panel)).height > CONTENT-HEIGHT
  block(panel, above: PARAGRAPH-AFTER + 3pt, below: PARAGRAPH-AFTER + 3pt, breakable: tall)
}

#let doc-table(..rows) = block(above: TABLE-GAP, below: TABLE-GAP, width: 100%, {
  let rows = rows.pos()
  let rule(y) = if y == 0 or y == rows.len() { 0.8pt + INK } else if y == 1 { 0.4pt + INK } else { TABLE-RULE + COOL-GRAY }
  set text(font: SERIF, size: TABLE-SIZE, fill: INK, hyphenate: false, features: LINING, ..edges(TABLE-SIZE, TABLE-LEADING, HALF-SERIF))
  set par(leading: 0pt, spacing: 0pt, justify: false, first-line-indent: 0pt)
  table(
    columns: rows.first().len(),
    stroke: (_, y) => (top: rule(y), bottom: if y == rows.len() - 1 { rule(rows.len()) }),
    inset: (x, y) => (left: if x == 0 { 0pt } else { TABLE-PAD + 2pt }, right: TABLE-PAD, top: if y == 0 { TABLE-PAD + 1pt } else { TABLE-PAD }, bottom: TABLE-PAD + 0.5pt),
    table.header(..rows.first().map(cell => text(weight: 600, cell))),
    ..rows.slice(1).flatten(),
  )
})

#let reference-list = state("reference-list", false)
#let list-stack = state("mag-list-stack", ())

#let doc-item(body) = context {
  if reference-list.get() {
    block(prose(move(dy: DATUM - REFERENCE-LEADING / 2 - HALF-SERIF * REFERENCE-SIZE, body)), above: 0pt, below: REFERENCE-AFTER)
  } else {
    list-stack.update(stack => stack.slice(0, -1) + ((..stack.last(), n: stack.last().n + 1),))
    context {
      let stack = list-stack.get()
      let level = stack.last()
      let marker = if level.ordered {
        text(features: LINING, ..flat, str(level.n) + ".")
      } else { text(fill: STONE, ..flat, if calc.odd(stack.len()) { "\u{2022}" } else { "\u{2013}" }) }
      block(
        {
          place(top + left, dy: DATUM, box(width: LIST-INDENT - 5pt, align(right, marker)))
          prose(pad(left: LIST-INDENT, { set par(first-line-indent: 0pt, spacing: 3.5pt); body }))
        },
        above: 0pt,
        below: ITEM-AFTER,
      )
    }
  }
}

#let doc-list(ordered: false, start: 1, references: false, body) = {
  let references = references and not ordered
  block(
    {
      reference-list.update(_ => references)
      list-stack.update(stack => stack + ((ordered: ordered, n: start - 1),))
      set par(spacing: 0pt)
      if references {
        set text(size: REFERENCE-SIZE, ..edges(REFERENCE-SIZE, REFERENCE-LEADING, HALF-SERIF))
        set par(hanging-indent: REFERENCE-HANG, justify: false)
        body
      } else {
        body
      }
      list-stack.update(stack => stack.slice(0, -1))
      reference-list.update(_ => false)
    },
    above: PARAGRAPH-AFTER,
    below: if references { REFERENCE-AFTER } else { PARAGRAPH-AFTER + 1pt },
  )
}

#let key-ideas-label(body) = block(
  text(size: LABEL-SIZE + 1pt, weight: 600, fill: INK, body),
  above: 0pt,
  below: 14pt,
)
#let key-idea(body) = par(body)
#let key-ideas(body) = block(
  breakable: false,
  above: 14pt,
  below: 0pt,
  {
    line(length: 100%, stroke: 0.5pt + RUBRIC)
    v(10pt - 0.5pt)
    body
  },
)

#let END-MARK-DROP = 42pt
#let end-mark(body) = {
  set par(spacing: 0pt)
  v(-20pt)
  block(
    height: 0pt,
    width: 100%,
    above: auto,
    below: 0pt,
    {
      place(top + left, dy: END-MARK-DROP, [#metadata(none)<mag-end-baseline>])
      place(top + left, dy: END-MARK-DROP, box(width: 100%, align(center, ornament(size: 12pt))))
    },
  )
}

#let figure-caption(body) = block(
  edge-prose(move(dy: CAPTION-NUDGE, {
    set par(justify: false, first-line-indent: 0pt)
    text(size: CAPTION-SIZE, fill: CAPTION-INK, features: PROSE-FIGURES, ..edges(CAPTION-SIZE, CAPTION-LEADING, HALF-SERIF), body)
  })),
  above: FIGURE-CAPTION-ABOVE,
  below: 0pt,
)
#let figure-counter = counter("mag-figure")

#let fitted-image-height(width, pixels, max-height) = (
  pixels.at(1) * calc.min(width / pixels.at(0), max-height / pixels.at(1))
)

#let framed-image(id, path, width, height, turned: false) = block(width: width, height: height, spacing: 0pt, {
  place(top + left, [#metadata((id: id, width: width, height: height, turned: turned))<mag-figure-box>])
  place(top + left, clipped(width, height, image(path, width: width, height: height, fit: "stretch")))
  place(top + left, rect(width: width, height: height, stroke: FIGURE-RULE + INK))
})

#let figure-image(id, path, pixels, spec) = layout(size => {
  let height = fitted-image-height(size.width, pixels, spec.max-height)
  let width = pixels.at(0) * height / pixels.at(1)
  let shift = calc.min(spec.at("shift", default: 0pt), calc.max(0pt, size.width - width))
  block(height: height, width: 100%, spacing: 0pt, move(dx: shift, framed-image(id, path, width, height)))
})

#let rotated-plate(id, path, pixels, body) = {
  let scale = calc.min(ROTATED-PLATE-LENGTH / pixels.at(0), ROTATED-PLATE-DEPTH / pixels.at(1))
  let (width, height) = (pixels.at(0) * scale, pixels.at(1) * scale)
  caption-edge.update(none)
  flow-mark("figure", ROTATED-PLATE, id: id, _ => place(top, float: true, clearance: 0pt, block(
    width: 100%,
    height: CONTENT-HEIGHT,
    place(center + horizon, dy: (MARGIN-BOTTOM - MARGIN-TOP) / 2, rotate(90deg, reflow: true, block(width: width, {
      framed-image(id, path, width, height, turned: true)
      body
    }))),
  )))
}

#let band-clearance() = context {
  let room = BAND-CLEARANCE-LINES * (text.top-edge - text.bottom-edge).to-absolute()
  block(height: room, width: 100%, breakable: false, above: 0pt, below: 0pt)
  v(-room)
}

#let carried-shift(index) = {
  let anchor = query(<mag-flow>).filter(m => m.value.index == index - 1 and m.value.kind == "heading")
  let top = anchor.len() > 0 and anchor.first().location().position().y <= MARGIN-TOP + PAGE-TOP-EPSILON
  if not top { 0pt } else if calc.odd(here().page()) { MARGIN-OUTER - MARGIN-INNER } else { MARGIN-INNER - MARGIN-OUTER }
}

#let plain-figure(id, anchor, layout, path, pixels, trim, float, body) = {
  let spec = figure-spec(layout, anchor)
  spec.max-height -= trim
  caption-edge.update(if BAND-LAYOUTS.contains(layout) { "band" } else if layout == COMPACT-BAND { "compact" })
  flow-mark("figure", layout, id: id, float: float, index => {
    let framed = block(
      above: 0pt,
      below: spec.gap,
      breakable: false,
      width: 100%,
      inset: spec.escape,
      move(dx: if is-band(layout) and anchor != OPENER-ANCHOR { carried-shift(index) } else { 0pt }, dy: DATUM, {
        figure-image(id, path, pixels, spec)
        body
      }),
    )
    if float == true { place(top, float: true, clearance: spec.gap, framed) } else { framed }
  })
  if float != true { band-clearance() }
}

#let figure-block(
  id: none,
  source-id: none,
  anchor: none,
  layout: none,
  word: none,
  alt: none,
  path: none,
  pixels: none,
  trim: 0pt,
  float: none,
  body,
) = {
  assert(pixels != none, message: "figure " + id + " carries no pixel size; the emitter must state it")
  figure-counter.step()
  if layout == ROTATED-PLATE { rotated-plate(id, path, pixels, body) } else { plain-figure(id, anchor, layout, path, pixels, trim, float, body) }
}

#let quote-line(body) = par(body)
#let extract-caption(body) = block(
  { set par(justify: false, first-line-indent: 0pt); text(size: CAPTION-SIZE, style: "italic", fill: INK, ..edges(CAPTION-SIZE, CAPTION-LEADING, HALF-SERIF), body) },
  above: EXTRACT-CAPTION-ABOVE,
  below: 0pt,
)
#let extract-label(word) = block(
  box(height: BODY-LEADING, align(horizon, text(size: LABEL-SIZE + 1pt, weight: 600, ..flat, word))),
  above: 0pt,
  below: EXTRACT-LABEL-AFTER,
)
#let extract(id: none, source-id: none, anchor: none, style: none, word: none, body) = {
  flow-mark("extract", none, _ => block(
    { extract-label(word); body },
    above: EXTRACT-GAP,
    below: EXTRACT-GAP,
    breakable: false,
  ))
}

#let tail-art(article: none, path: none, pixels: none, fit: "cover") = {
  let height = calc.min(MEASURE * pixels.at(1) / pixels.at(0), TAIL-MAX-HEIGHT)
  [#metadata((height: height, path: path, fit: fit))<mag-tail-art>]
  context {
    let baseline = tail-baseline(here())
    let room = tail-room(baseline)
    [#metadata((article: article, printed: room >= height, height: height, room: room, page: baseline.page))<mag-tail>]
  }
}


#let plates = state("mag-plates", ())

#let py-round(value) = {
  let whole = calc.floor(value)
  let rest = value - whole
  if rest > 0.5 or (rest == 0.5 and calc.odd(whole)) { whole + 1 } else { whole }
}

#let signature-plates(content, target) = {
  let minimum = content + 2
  let pages = calc.ceil(calc.max(if target == none { minimum } else { target }, minimum) / 4) * 4
  let count = pages - 2 - content
  if count < 4 { count + 4 } else { count }
}

#let plate-page(plate) = page(
  foreground: none,
  [#metadata(none)<mag-plate>] + place(top + left, dy: -MARGIN-TOP, clipped(LIVE-WIDTH, PAGE-HEIGHT, image(plate.path, width: LIVE-WIDTH, height: PAGE-HEIGHT, fit: "contain"))),
)

#let plate-content = state("mag-plate-content", none)
#let closing-signature(content) = plate-content.update(content)

#let plates-after(ordinal, of: 1) = context {
  let all = plates.get()
  let content = plate-content.get()
  if all.len() == 0 or content == none { return }
  let count = signature-plates(content, all.first().target)
  assert(
    count <= all.len(),
    message: "Edition needs " + str(count) + " closing plates to close the signature but configures "
      + str(all.len()) + "; add " + str(count - all.len())
      + " more to closing_plates (mag art <edition> --only closing, then pick in art/showcase.html)",
  )
  let slots = range(1, count + 1).map(j => py-round(j * of / count))
  for j in range(count).rev() {
    if slots.at(j) == ordinal or (slots.at(j) == 0 and ordinal == of) { plate-page(all.at(j)) }
  }
}

#let closing-plate(index: 1, alt: none, path: none, target: none) = plates.update(p => p + ((index: index, alt: alt, path: path, target: target),))

#let page-cap(id, kind) = context {
  let head = query(<mag-piece>).find(m => m.value.id == id)
  let foot = query(<mag-piece-end>).find(m => m.value == id)
  let span = foot.location().page() - head.location().page() + 1
  assert(
    kind == "verbatim" or span <= ARTICLE-PAGE-CAP,
    message: id + " spans " + str(span) + " reader pages; the hard cap is "
      + str(ARTICLE-PAGE-CAP) + ". Condense it as a faithful_synthesis before building.",
  )
}

#let piece(
  id: none,
  kind: none,
  short-title: none,
  source-ids: (),
  figure-layouts: (),
  opener: "plain",
  art: none,
  titles: none,
  body,
) = {
  pagebreak(weak: true)
  figure-counter.update(0)
  let plate = figure-layouts.any(l => l.starts-with("landscape_plate"))
  let after = if kind == "original_editorial" {
    EDITORIAL-AFTER
  } else if plate {
    PLATE-AFTER
  } else {
    PARAGRAPH-AFTER
  }
  set par(spacing: after)
  set text(..edges(BODY-SIZE, PLATE-LEADING, HALF-SERIF)) if plate
  column({
    let mark = [#metadata((id: id, head: short-title))<mag-piece>]
    if opener == ILLUSTRATED { place(top + left, dy: -OPENER-MARK-LIFT, mark) } else { mark }
    if opener == ILLUSTRATED {
      opener-parts.update(_ => ((tag: "art", body: art), (tag: "titles", body: titles)))
    }
    body
    flow-mark("end", none, _ => none)
    [#metadata(id)<mag-piece-end>]
  })
  page-cap(id, kind)
}
