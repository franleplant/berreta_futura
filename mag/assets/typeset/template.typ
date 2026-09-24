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

#let INK = rgb(5.5%, 7.5%, 8.5%)
#let VIOLET = rgb(25%, 10%, 43%)
#let SLATE = rgb(31%, 35%, 37%)
#let COOL-GRAY = rgb(88%, 89%, 230)
#let PALE-VIOLET = rgb(95.5%, 94.5%, 97.5%)
#let SIGNAL-ORANGE = rgb(240, 87, 56)

#let SERIF = "Source Serif 4 SmText"
#let DISPLAY = ("Source Serif 4 Display", "Source Serif 4 SmText")
#let SANS = "Inter"
#let MONO = "Geist Mono"

#let HALF-SERIF = 0.3505
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
#let DISC = 5pt
#let DISC-KAPPA = 0.55

#let DATUM = 10.0046pt
#let BODY-SIZE = 10pt
#let BODY-LEADING = 13pt
#let PARAGRAPH-AFTER = 5.4pt
#let EDITORIAL-AFTER = 6.2pt
#let PLATE-LEADING = 12.2pt
#let PLATE-AFTER = 4pt
#let CAPTION-SIZE = 6.8pt
#let FOLIO-BASELINE = 19.5pt
#let LIST-INDENT = 14pt
#let ITEM-AFTER = 6pt
#let REFERENCE-AFTER = 3pt
#let REFERENCE-SIZE = 7.2pt
#let REFERENCE-LEADING = 9.4pt
#let REFERENCE-HANG = 12.9744pt
#let QUOTE-RULE = 1.5pt
#let QUOTE-PAD = 4mm
#let HEADING-CLEARANCE = 25pt
#let ZERO-LEADING-SANS = 2.47375pt
#let RUNNING-BASELINE = 20pt
#let RUNNING-RULE = 0.55pt
#let RUNNING-RULE-TOP = 27.725pt
#let RUNNING-TICK-WIDTH = 14pt
#let RUNNING-TICK = 1.15pt
#let RUNNING-TICK-TOP = 27.425pt
#let ARTICLE-PAGE-CAP = 7
#let VERBATIM-PAGE-CAP = 10
#let INLINE-LINK = " mag-inline-link"

#let FIGURE-LABEL-ZONE = 13.1pt
#let FIGURE-LABEL-PAD = 4.32625pt
#let FIGURE-LABEL-TRACKING = 0.25pt
#let FIGURE-CAPTION-ABOVE = 6.3pt
#let FIGURE-GAP = 15.75pt
#let COMPACT-FIGURE-GAP = 12pt
#let FIGURE-MAX-HEIGHT = 205pt
#let COMPACT-FIGURE-MAX-HEIGHT = 170pt
#let OPENER-FIGURE-MAX-HEIGHT = 270pt
#let COMPACT-BAND-INSET = 32.5pt
#let FIGURE-RULE = 0.55pt
#let CAPTION-NUDGE = 0.1166pt
#let CREDIT-NUDGE = -0.09023pt
#let TAIL-MAX-HEIGHT = 214pt
#let TAIL-FRAME-BOTTOM = 45pt
#let TAIL-CLEARANCE = 12pt
#let TAIL-FOOT-F32-LIFT = 0.0001pt
#let PAGE-TOP-EPSILON = 0.01pt
#let BAND-LAYOUTS = ("evidence_band", "evidence_band_prose", "adaptive_band")
#let COMPACT-BAND = "compact_band"
#let OPENER-ANCHOR = "__opener__"
#let EXTRACT-GAP = 5mm
#let EXTRACT-LABEL-AFTER = 2pt
#let EXTRACT-CAPTION-ABOVE = 2pt
#let EXTRACT-LABEL-TRACKING = 0.45pt

#let CONTENTS-KICKER-TOP = -13.46915pt
#let CONTENTS-TITLE-TOP = 32.54098pt
#let CONTENTS-TITLE-SIZE = 27pt
#let CONTENTS-BAND-TOP = 74.2802pt
#let CONTENTS-BAND = 393pt
#let CONTENTS-RULE = 0.7pt
#let CONTENTS-ENTRY-LEFT = 47pt
#let CONTENTS-STANDARD = (label: 8.6pt, folio: 17.7pt, title: 17.5pt, author: 32.2pt)
#let CONTENTS-TIGHT = (label: 6.8pt, folio: 15.9pt, title: 15.8pt, author: 30.5pt)

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
#let OPENER-PANGO-RESERVE = 13.2pt
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
#let OPENER-TICK-WIDTH = 14.5pt
#let OPENER-TICK = 2.4pt
#let OPENER-META-RULE = 1pt
#let OPENER-LABEL-SIZE = 6.5pt
#let OPENER-LABEL-LEADING = 7.15pt
#let OPENER-LABEL-TRACKING = 0.16
#let OPENER-TITLE-LEADING-RATIO = 0.96
#let OPENER-TITLE-TRACKING = -0.045
#let OPENER-TITLE-MAX = 32.5pt
#let OPENER-COMPACT-TITLE-MAX = 30pt
#let OPENER-TITLE-MIN = 22pt
#let OPENER-TITLE-STEP = 0.5pt
#let OPENER-TITLE-BOX = 64pt
#let OPENER-TITLE-MAX-LINES = 2
#let OPENER-BYLINE-SIZE = 7.4pt
#let OPENER-BYLINE-LEADING = 8.5pt
#let OPENER-BYLINE-TRACKING = 0.04
#let OPENER-PREFIX-SIZE = 6.2pt
#let OPENER-PREFIX-TRACKING = 0.15
#let OPENER-PREFIX-GAP = 0.35
#let OPENER-NOTE-LEADING = 9.4pt
#let OPENER-NOTE-ABOVE = 3.2pt
#let OPENER-DROP-SIZE = 18.7pt
#let OPENER-DROP-GAP = 1pt
#let OPENER-DROP-TOP = 13.0992pt
#let OPENER-STANDARD = (
  label: 24pt,
  title-gap: 8pt,
  tick: 25pt,
  meta-pad: 9pt,
  standfirst-gap: 32.5pt,
  standfirst-size: 10.2pt,
  standfirst-leading: 14.4pt,
)
#let OPENER-COMPACT = (
  label: 20pt,
  title-gap: 6pt,
  tick: 18pt,
  meta-pad: 7pt,
  standfirst-gap: 22pt,
  standfirst-size: 9.6pt,
  standfirst-leading: 13.2pt,
)

#let edges(size, leading, half) = (
  top-edge: leading / 2 + half * size,
  bottom-edge: leading / 2 + half * size - leading,
)

#let pinned(leading) = (top-edge: DATUM, bottom-edge: DATUM - leading)

#let flat = (top-edge: 0pt, bottom-edge: 0pt)

#let tracked(amount) = (tracking: amount, features: (liga: 0, clig: 0))

#let publication = state("publication", [])

#let leading-zero(index) = if index < 10 { "0" + str(index) } else { str(index) }

#let folio-text(body) = text(
  font: SANS,
  size: CAPTION-SIZE,
  weight: 500,
  fill: INK,
  ..flat,
  upper(body),
)

#let folio(index) = {
  place(
    top + left,
    dx: MARGIN-OUTER,
    dy: PAGE-HEIGHT - FOLIO-BASELINE,
    folio-text(publication.final()),
  )
  place(
    top + right,
    dx: -MARGIN-OUTER,
    dy: PAGE-HEIGHT - FOLIO-BASELINE,
    folio-text(leading-zero(index)),
  )
}

#let running-head(index) = {
  let marks = query(<mag-piece>).filter(m => m.location().page() <= index)
  if marks.len() == 0 or marks.last().location().page() == index { return }
  let inner = if calc.odd(index) { MARGIN-INNER } else { MARGIN-OUTER }
  let outer = if calc.odd(index) { MARGIN-OUTER } else { MARGIN-INNER }
  place(top + left, dx: inner, dy: RUNNING-BASELINE, folio-text(publication.final()))
  place(top + right, dx: -outer, dy: RUNNING-BASELINE, folio-text(marks.last().value.head))
  place(
    top + left,
    dx: inner,
    dy: RUNNING-RULE-TOP,
    rect(width: LIVE-WIDTH, height: RUNNING-RULE, fill: COOL-GRAY, stroke: none),
  )
  place(
    top + left,
    dx: inner,
    dy: RUNNING-TICK-TOP,
    rect(width: RUNNING-TICK-WIDTH, height: RUNNING-TICK, fill: SIGNAL-ORANGE, stroke: none),
  )
}

#let furniture() = context {
  let index = counter(page).at(here()).first()
  running-head(index)
  folio(index)
}

#let plain-page() = page(margin: 0pt, foreground: none, [])

#let column(body) = pad(left: RAIL, right: RAIL - MEASURE-DELTA, body)

#let NO-ESCAPE = (left: 0pt, right: 0pt)
#let BAND-ESCAPE = (left: -RAIL, right: MEASURE-DELTA - RAIL)
#let COMPACT-ESCAPE = (left: COMPACT-BAND-INSET, right: COMPACT-BAND-INSET)

#let flow-counter = counter("mag-flow")

#let flow-mark(kind, layout, body) = {
  flow-counter.step()
  context [#metadata((
      kind: kind,
      layout: layout,
      index: flow-counter.get().first(),
    ))<mag-flow>]
  context body(flow-counter.get().first())
}

#let figure-spec(layout, anchor) = {
  let opener = anchor == OPENER-ANCHOR
  let compact = layout == COMPACT-BAND
  (
    escape: if BAND-LAYOUTS.contains(layout) {
      BAND-ESCAPE
    } else if compact { COMPACT-ESCAPE } else { NO-ESCAPE },
    gap: if opener { 0pt } else if compact { COMPACT-FIGURE-GAP } else { FIGURE-GAP },
    max-height: if opener {
      OPENER-FIGURE-MAX-HEIGHT
    } else if compact { COMPACT-FIGURE-MAX-HEIGHT } else { FIGURE-MAX-HEIGHT },
  )
}

#let is-band(layout) = BAND-LAYOUTS.contains(layout) or layout == COMPACT-BAND

#let band-anchored(index) = {
  let next = query(<mag-flow>).filter(m => m.value.index == index + 1)
  next.len() > 0 and next.first().value.kind == "figure" and is-band(next.first().value.layout)
}

#let layer(body) = [#body<mag-layer>]
#let backdrop(body) = [#body<mag-backdrop>]
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
    hyphenate: false,
    ..edges(BODY-SIZE, BODY-LEADING, HALF-SERIF),
  )
  set par(
    leading: 0pt,
    spacing: PARAGRAPH-AFTER,
    linebreaks: "simple",
    justify: false,
    first-line-indent: 0pt,
  )
  plain-page()
  plain-page()
  body
  plain-page()
  plain-page()
}

#let edition-header(body) = body
#let publication-name(body) = publication.update(_ => body)
#let issue-line(body) = none
#let edition-title(body) = none
#let edition-subtitle(body) = none
#let edition-date(body) = none

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

#let contents-caption(body) = text(
  font: SANS,
  size: CAPTION-SIZE,
  weight: 500,
  ..flat,
  ..tracked(0.45pt),
  upper(body),
)

#let contents-row(row, offsets, destination, rows) = {
  let label = part(rows, "entry-label")
  let title = part(rows, "entry-title")
  let author = part(rows, "entry-author")
  if label != none {
    place(top + left, dx: CONTENTS-ENTRY-LEFT, dy: row + offsets.label + ZERO-LEADING-SANS, {
      contents-caption(label)
    })
  }
  let target = query(<mag-piece>).find(m => m.value.id == destination).location()
  let folio = text(
    font: SANS,
    size: 23pt,
    weight: 600,
    fill: VIOLET,
    ..flat,
    leading-zero(counter(page).at(target).first()),
  )
  for _ in range(2) {
    place(top + left, dy: row + offsets.folio, link(target, box(width: measure(folio).width, height: 0pt)))
  }
  place(top + left, dy: row + offsets.folio + 23pt * HALF-SANS, folio)
  if title != none {
    place(top + left, dx: CONTENTS-ENTRY-LEFT, dy: row + offsets.title, link(target, box(
      width: LIVE-WIDTH - CONTENTS-ENTRY-LEFT,
      text(font: DISPLAY, size: 9.8pt, weight: 600, ..edges(9.8pt, 10.2pt, HALF-SERIF), title),
    )))
  }
  if author != none {
    place(top + left, dx: CONTENTS-ENTRY-LEFT, dy: row + offsets.author + ZERO-LEADING-SANS, {
      text(font: SANS, size: CAPTION-SIZE, weight: 500, fill: SLATE, ..flat, upper(author))
    })
  }
}

#let contents(tight: false, body) = {
  pagebreak(weak: true)
  let rows = parts(body)
  let entries = rows.filter(r => r.tag == "entry")
  let offsets = if tight { CONTENTS-TIGHT } else { CONTENTS-STANDARD }
  let height = CONTENTS-BAND / calc.max(1, entries.len())
  block(height: PAGE-HEIGHT - MARGIN-TOP - MARGIN-BOTTOM, width: 100%, context {
    let kicker = part(rows, "kicker")
    let label = part(rows, "label")
    if kicker != none {
      place(top + left, dy: CONTENTS-KICKER-TOP + ZERO-LEADING-SANS, contents-caption(kicker))
    }
    if label != none {
      place(top + left, dy: CONTENTS-TITLE-TOP + CONTENTS-TITLE-SIZE * HALF-SERIF, {
        bookmark(1, label)
        text(font: DISPLAY, size: CONTENTS-TITLE-SIZE, weight: 600, ..flat, label)
      })
    }
    for (index, entry) in entries.enumerate() {
      let row = CONTENTS-BAND-TOP + index * height
      contents-row(row, offsets, entry.destination, parts(entry.body))
      if index + 1 < entries.len() {
        place(top + left, dy: row + height - CONTENTS-RULE / 2, {
          rect(width: LIVE-WIDTH, height: CONTENTS-RULE, fill: COOL-GRAY, stroke: none)
        })
      }
    }
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

#let plain-opener(size: 35pt, field: 0pt, tracking: 0pt, title: "", body) = {
  plain-head.update((size: size, tracking: tracking, title: title))
  block(height: field, width: 100%, above: 0pt, below: 0pt, breakable: false, body)
  plain-head.update(none)
}

#let plain-title-text(size, body) = text(
  font: DISPLAY,
  size: size,
  weight: 600,
  hyphenate: false,
  ..edges(size, size * OPENER-TITLE-LEADING-RATIO, HALF-SERIF),
  body,
)

#let plain-title-block(size, body) = block(width: MEASURE + MEASURE-DELTA, plain-title-text(size, body))

#let plain-byline-baseline(head) = {
  let leading = head.size * OPENER-TITLE-LEADING-RATIO
  let lines = calc.round(measure(plain-title-block(head.size, head.title)).height / leading)
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

#let content-label(body) = context if plain-head.get() != none {
  let items = body.children.enumerate().map(((i, item)) => {
    (if i == 1 { box(move(dx: LABEL-TRACKING, item)) } else { unspaced(item) }) + h(LABEL-TRACKING)
  })
  place(top + left, dy: PLAIN-LABEL-TOP + ZERO-LEADING-SANS, box(width: 100%, text(
    font: SANS, size: CAPTION-SIZE, weight: 500, ..flat, ..tracked(LABEL-TRACKING), upper(items.intersperse(h(1fr)).join()),
  )))
} else if opener-parts.get() == none {
  block(
    text(font: SANS, size: CAPTION-SIZE, weight: 500, ..flat, ..tracked(0.45pt), upper(body)),
    spacing: 7.53085pt,
  )
} else {
  collect("label", body)
}
#let label-primary(body) = context if opener-parts.get() == none {
  text(fill: VIOLET, body)
} else {
  body
}
#let label-secondary(body) = text(body)
#let label-separator(body) = text(body)
#let label-date(body) = context if opener-parts.get() == none {
  text(fill: PAPER-GRAY, weight: 600, body)
} else {
  text(weight: 600, body)
}

#let opener-title-text(size, body) = text(
  font: DISPLAY,
  size: size,
  weight: 600,
  fill: PAPER-INK,
  hyphenate: false,
  ..edges(size, size * OPENER-TITLE-LEADING-RATIO, HALF-SERIF),
  body,
)

#let wrapped(width, body) = block(width: width, {
  set par(leading: 0pt, spacing: 0pt, linebreaks: "simple", justify: false)
  body
})

#let fitted-title(body, maximum) = {
  let size = maximum
  while size > OPENER-TITLE-MIN {
    let leading = size * OPENER-TITLE-LEADING-RATIO
    let rows = calc.round(
      measure(wrapped(OPENER-RAIL, opener-title-text(size, body))).height / leading,
    )
    if rows <= OPENER-TITLE-MAX-LINES and size + (rows - 1) * leading <= OPENER-TITLE-BOX {
      return (size: size, lines: rows)
    }
    size -= OPENER-TITLE-STEP
  }
  (size: size, lines: OPENER-TITLE-MAX-LINES)
}

#let piece-title(body) = context if plain-head.get() != none {
  let size = plain-head.get().size
  let leading = size * OPENER-TITLE-LEADING-RATIO
  place(top + left, dy: PLAIN-TITLE-TOP + size - (leading / 2 + HALF-SERIF * size), bookmark(1, body) + plain-title-block(size, body))
} else if opener-parts.get() == none {
  block(
    bookmark(1, body) + text(font: DISPLAY, size: 24pt, weight: 600, ..edges(24pt, 24pt * 1.08, HALF-SERIF), body),
    spacing: 8pt,
  )
} else {
  collect("title", body)
}

#let byline-prefix(body) = context if opener-parts.get() == none {
  body
} else {
  text(
    size: OPENER-PREFIX-SIZE,
    fill: PAPER-BLUE,
    ..tracked(OPENER-PREFIX-TRACKING * OPENER-PREFIX-SIZE),
    body,
  )
  h(OPENER-PREFIX-GAP * OPENER-PREFIX-SIZE)
}
#let byline-name(body) = text(body)
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

#let code-quiet(code) = OPENER-QR-QUIET * PLAIN-QR / (code.len() + 2 * OPENER-QR-QUIET)
#let credit-inset(code) = if code == none { 0pt } else { PLAIN-QR - 2 * code-quiet(code) + CODE-CREDIT-GAP }
#let byline(code: none, body) = context if opener-parts.get() == none {
  let head = plain-head.get()
  let tracking = if head == none { 0pt } else { head.tracking }
  let line = text(font: SANS, size: OPENER-BYLINE-SIZE, weight: 600, ..flat, tracking: tracking, upper(body))
  let credit = {
    if code != none {
      let quiet = code-quiet(code)
      place(top + left, dx: -quiet, dy: -OPENER-BYLINE-SIZE * INTER-CAP - quiet, qr-symbol(code, side: PLAIN-QR))
    }
    pad(left: credit-inset(code), line)
  }
  if head == none {
    block(above: 12pt, below: 0pt, credit)
  } else {
    place(top + left, dy: plain-byline-baseline(head), block(width: 100%, credit))
  }
} else {
  collect("byline", body)
}
#let author-note(code: none, body) = context if opener-parts.get() == none {
  let head = plain-head.get()
  let note = block(
    width: 100%,
    inset: (left: credit-inset(code)),
    above: 7.49326pt,
    below: 0pt,
    text(font: SANS, size: CAPTION-SIZE, weight: 400, fill: SLATE, ..edges(CAPTION-SIZE, NOTE-LEADING, HALF-SANS), body),
  )
  if head == none { note } else {
    let baseline = plain-byline-baseline(head) + PLAIN-NOTE-DROP
    place(top + left, dy: baseline - NOTE-LEADING / 2 - HALF-SANS * CAPTION-SIZE, note)
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
  block(above: 0pt, below: 0pt, text(
    font: SANS,
    size: OPENER-BYLINE-SIZE,
    weight: 700,
    fill: PAPER-INK,
    top-edge: edges(OPENER-BYLINE-SIZE, OPENER-BYLINE-LEADING, HALF-SANS).top-edge,
    bottom-edge: edges(OPENER-PREFIX-SIZE, OPENER-BYLINE-LEADING, HALF-SANS).bottom-edge,
    ..tracked(OPENER-BYLINE-TRACKING * OPENER-BYLINE-SIZE),
    upper(opener-part(rows, "byline")),
  ))
  if note != none {
    block(above: OPENER-NOTE-ABOVE, below: 0pt, text(
      font: SANS,
      size: CAPTION-SIZE,
      weight: 400,
      fill: PAPER-GRAY,
      ..edges(CAPTION-SIZE, OPENER-NOTE-LEADING, HALF-SANS),
      note,
    ))
  }
}

#let initial(body) = {
  let parts = if body.has("children") { body.children } else { (body,) }
  let head = parts.at(0, default: none)
  if head == none or not head.has("text") { return body }
  let letters = head.text.clusters()
  let lead = letters.position(c => c.match(regex("^\\p{P}$")) == none)
  if lead == none { return body }
  box(inset: (right: OPENER-DROP-GAP), text(
    font: DISPLAY,
    size: OPENER-DROP-SIZE,
    weight: 600,
    fill: PAPER-BLUE,
    top-edge: OPENER-DROP-TOP,
    bottom-edge: 0pt,
    letters.slice(0, lead + 1).join(),
  ))
  letters.slice(lead + 1).join()
  parts.slice(1).join()
}

#let standfirst-text(density, body) = text(
  size: density.standfirst-size,
  ..edges(density.standfirst-size, density.standfirst-leading, HALF-SERIF),
  initial(body),
)

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
      + OPENER-TICK
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

#let opener-page(rows, body, split) = {
  let title = opener-part(rows, "title")
  let fit = fitted-title(title, OPENER-TITLE-MAX)
  let density = OPENER-STANDARD
  if split or opener-stack(density, fit, rows, body) + OPENER-PANGO-RESERVE > CONTENT-HEIGHT {
    density = OPENER-COMPACT
    fit = fitted-title(title, OPENER-COMPACT-TITLE-MAX)
  }
  let rail(body) = block(width: OPENER-RAIL, above: 0pt, below: 0pt, body)
  let label = rail(text(
    font: SANS,
    size: OPENER-LABEL-SIZE,
    weight: 600,
    fill: PAPER-BLUE,
    ..edges(OPENER-LABEL-SIZE, OPENER-LABEL-LEADING, HALF-SANS),
    ..tracked(OPENER-LABEL-TRACKING * OPENER-LABEL-SIZE),
    upper(opener-part(rows, "label")),
  ))
  let heading = rail({
    set par(leading: 0pt, spacing: 0pt)
    text(..tracked(OPENER-TITLE-TRACKING * fit.size), opener-title-text(fit.size, title))
  })
  let meta = rail(grid(
    columns: (1fr, OPENER-QR),
    column-gutter: OPENER-GAP,
    align: horizon,
    credit-column(rows),
    source-code(opener-part(rows, "source")),
  ))
  let standfirst = rail({
    set par(leading: 0pt, spacing: 0pt)
    standfirst-text(density, body)
  })
  let y-label = OPENER-ART-HEIGHT - OPENER-ART-LIFT + density.label
  let y-title = y-label + measure(label).height + density.title-gap
  let y-tick = y-title + measure(heading).height + density.tick
  let y-meta = y-tick + OPENER-TICK + density.meta-pad
  let y-rule = y-meta + measure(meta).height + density.meta-pad
  let y-standfirst = y-rule + OPENER-META-RULE + density.standfirst-gap
  let at(y, body) = place(top + left, dx: -OPENER-ESCAPE, dy: y, body)
  block(breakable: false, above: 0pt, below: 0pt, width: 100%, height: y-standfirst + measure(standfirst).height, {
    at(y-tick, rect(width: OPENER-TICK-WIDTH, height: OPENER-TICK, fill: SIGNAL-ORANGE, stroke: none))
    at(y-label, label)
    at(y-title, heading)
    at(y-title, bookmark(1, title))
    at(y-standfirst, standfirst)
    place(top + left, dx: OPENER-OFFSET - OPENER-ESCAPE, dy: OPENER-OFFSET - OPENER-ART-LIFT, {
      rect(width: OPENER-RAIL, height: OPENER-FRAME-HEIGHT, fill: SIGNAL-ORANGE, stroke: none)
    })
    at(y-rule, rect(width: OPENER-RAIL, height: OPENER-META-RULE, fill: PAPER-RULE, stroke: none))
    at(y-meta, meta)
    at(-OPENER-ART-LIFT, opener-art(opener-part(rows, "art")))
  })
}

#let opener-standfirst(rows, body, split) = {
  opener-page(rows, body, split)
  opener-parts.update(_ => none)
  context v(PAGE-HEIGHT - MARGIN-BOTTOM - here().position().y)
}

#let doc-link(destination: none, title: none, body) = {
  show emph: it => link(destination + INLINE-LINK, it)
  show strong: it => link(destination + INLINE-LINK, it)
  link(destination, body)
}

#let code-pad = text(font: MONO, size: CODE-PAD-X / MONO-ADVANCE, ..flat, "\u{a0}")

#let inline-code(body) = context {
  let size = CODE-SIZE * text.size
  let leading = (text.top-edge - text.bottom-edge).to-absolute()
  let lift = calc.min(0pt, text.top-edge.to-absolute() - leading / 2 - HALF-SERIF * text.size)
  let (top-edge, bottom-edge) = edges(size, leading, HALF-MONO)
  code-pad
  highlight(
    fill: PALE-VIOLET,
    radius: CODE-RADIUS,
    extent: CODE-PAD-X,
    top-edge: (0.5 + HALF-MONO) * size + CODE-PAD-Y,
    bottom-edge: (HALF-MONO - 0.5) * size - CODE-PAD-Y,
    text(
      font: MONO,
      size: size,
      weight: 500,
      fill: VIOLET,
      hyphenate: false,
      top-edge: top-edge + lift,
      bottom-edge: bottom-edge + lift,
      body,
    ),
  )
  code-pad
}

#let doc-rule() = block(
  line(length: 100%, stroke: 0.55pt + COOL-GRAY),
  above: PARAGRAPH-AFTER,
  below: PARAGRAPH-AFTER,
)

#let doc-paragraph(standfirst: false, roster: false, split: false, body) = {
  if standfirst {
    context {
      let rows = opener-parts.get()
      if rows == none {
        block(text(size: 12pt, ..pinned(16.4pt), body), below: 13pt)
      } else {
        opener-standfirst(rows, body, split)
      }
    }
  } else {
    par(body)
  }
}

#let HEADINGS = (
  (font: DISPLAY, size: 22pt, leading: 25pt, above: 23.4pt, after-standfirst: 31pt, below: 13pt, fill: INK, caps: false),
  (font: DISPLAY, size: 18.5pt, leading: 21.5pt, above: 20.4pt, after-standfirst: 28pt, below: 11pt, fill: INK, caps: false, drop: 15pt),
  (font: SANS, size: 8.5pt, leading: 12pt, above: 15.4pt, after-standfirst: 23pt, below: 8pt, fill: VIOLET, caps: true, drop: 10pt),
)

#let heading-stack(level, spec, above, escape, drop, body, lead: false) = {
  layer(block(above: if lead { 0pt } else { above }, below: 0pt, breakable: false, width: 100%, inset: escape, {
    if lead { v(above, weak: false) }
    bookmark(level, body)
    move(dy: drop, text(
      font: spec.font,
      size: spec.size,
      weight: 600,
      fill: spec.fill,
      ..pinned(spec.leading),
      if spec.caps { upper(body) } else { body },
    ))
    v(spec.below)
    block(height: HEADING-CLEARANCE, width: 100%, spacing: 0pt, [])
  }))
  v(-HEADING-CLEARANCE)
}

#let doc-heading(level: 1, lead: false, standfirst: false, body) = {
  let spec = HEADINGS.at(calc.min(level, 3) - 1)
  flow-mark("heading", none, index => {
    let anchor = level >= 2 and level <= 3 and band-anchored(index)
    let midpage = anchor and here().position().y > MARGIN-TOP + PAGE-TOP-EPSILON
    heading-stack(
      level,
      spec,
      if anchor { auto } else if standfirst { spec.after-standfirst } else { spec.above },
      if anchor { BAND-ESCAPE } else { NO-ESCAPE },
      if midpage { spec.drop } else { 0pt },
      body,
      lead: lead and not anchor,
    )
  })
}

#let ruled(pad-left, pad-rest, fill-color, body) = backdrop(block(fill: fill-color, outset: (right: -MEASURE-DELTA), width: 100%, spacing: 0pt, pad(
  left: QUOTE-RULE / 2,
  block(
    stroke: (left: QUOTE-RULE + VIOLET),
    inset: (left: pad-left + QUOTE-RULE / 2, rest: pad-rest),
    width: 100%,
    above: 0pt,
    below: 0pt,
    body,
  ),
)))

#let doc-quote(body) = block(
  {
    set par(spacing: 0pt)
    ruled(QUOTE-PAD, 0pt, none, body)
  },
  above: 4mm,
  below: 4mm,
)

#let code-runs(source, inks) = {
  let runs = if inks.len() == 0 { ((source.len(), none),) } else { inks }
  assert(runs.map(r => r.at(0)).sum() == source.len(), message: "the code inks do not cover the code block")
  let at = 0
  for (length, ink) in runs {
    let run = source.slice(at, at + length)
    at += length
    if ink == none { run } else { text(fill: ink, run) }
  }
}

#let code-panel(inks: (), collapse: false, body) = {
  set par(leading: 0pt, spacing: 0pt)
  set text(
    font: MONO,
    size: CODE-BLOCK-SIZE,
    weight: 400,
    fill: INK,
    hyphenate: false,
    ..edges(CODE-BLOCK-SIZE, CODE-BLOCK-SIZE * CODE-BLOCK-LEADING, HALF-MONO),
  )
  let lines = body.text.split("\n").map(line => line.trim().replace(regex("\\s+"), " "))
  ruled(CODE-BLOCK-PAD, CODE-BLOCK-PAD, PALE-VIOLET, if collapse {
    lines.join(linebreak())
  } else {
    code-runs(body.text, inks)
  })
}

#let doc-code(lang: "", inks: (), body) = block(
  code-panel(inks: inks, body),
  above: CODE-BLOCK-SIZE,
  below: CODE-BLOCK-SIZE,
)

#let reference-list = state("reference-list", false)

#let disc = {
  let (r, k) = (DISC / 2, DISC / 2 * (1 - DISC-KAPPA))
  curve(
    fill: VIOLET,
    stroke: none,
    curve.move((0pt, r)),
    curve.cubic((0pt, k), (k, 0pt), (r, 0pt)),
    curve.cubic((DISC - k, 0pt), (DISC, k), (DISC, r)),
    curve.cubic((DISC, DISC - k), (DISC - k, DISC), (r, DISC)),
    curve.cubic((k, DISC), (0pt, DISC - k), (0pt, r)),
    curve.close(mode: "straight"),
  )
}

#let doc-item(body) = context {
  if reference-list.get() {
    block(move(dy: DATUM - REFERENCE-LEADING / 2 - HALF-SERIF * REFERENCE-SIZE, body), above: 0pt, below: REFERENCE-AFTER)
  } else {
    layer(block(
      {
        layer(place(top + left, dy: 3.505pt, disc))
        pad(left: LIST-INDENT, body)
      },
      above: 0pt,
      below: ITEM-AFTER,
    ))
  }
}

#let doc-list(ordered: false, start: 1, references: false, body) = {
  let references = references and not ordered
  block(
    {
      reference-list.update(_ => references)
      set par(spacing: 0pt)
      if references {
        set text(size: REFERENCE-SIZE, ..edges(REFERENCE-SIZE, REFERENCE-LEADING, HALF-SERIF))
        set par(hanging-indent: REFERENCE-HANG)
        body
      } else {
        body
      }
      reference-list.update(_ => false)
    },
    above: auto,
    below: if references { REFERENCE-AFTER } else { ITEM-AFTER },
  )
}

#let key-ideas-label(body) = block(
  text(font: SANS, size: CAPTION-SIZE, weight: 500, fill: VIOLET, ..flat, ..tracked(0.45pt), upper(body)),
  above: 0pt,
  below: 13pt,
)
#let key-idea(body) = par(body)
#let key-ideas(body) = block(
  breakable: false,
  above: 12pt,
  below: 0pt,
  {
    line(length: 100%, stroke: 1.1pt + SIGNAL-ORANGE)
    v(10pt - 1.1pt)
    body
  },
)

#let end-mark(body) = {
  set par(spacing: 0pt)
  v(-20pt)
  layer(block(
    height: 0pt,
    width: 100%,
    above: auto,
    below: 0pt,
    {
      place(top + left, dy: 28.53085pt + 2.47375pt, [#metadata(none)<mag-end-baseline>])
      place(
        top + left,
        dx: 24pt,
        dy: 28.53085pt + 2.47375pt,
        text(
          font: SANS,
          size: CAPTION-SIZE,
          weight: 500,
          fill: VIOLET,
          ..flat,
          ..tracked(0.25pt),
          upper(body),
        ),
      )
      place(
        top + left,
        dy: 28.53085pt - 0.07625pt,
        rect(width: 17pt, height: 1.1pt, fill: SIGNAL-ORANGE, stroke: none),
      )
    },
  ))
}

#let figure-caption(body) = block(
  move(dy: CAPTION-NUDGE, text(size: CAPTION-SIZE, ..edges(CAPTION-SIZE, 8.6pt, HALF-SERIF), body)),
  above: FIGURE-CAPTION-ABOVE,
  below: 0pt,
)
#let figure-credit(body) = block(
  move(dy: CAPTION-NUDGE + CREDIT-NUDGE, text(
    font: SANS,
    size: CAPTION-SIZE,
    weight: 500,
    fill: SLATE,
    ..edges(CAPTION-SIZE, 8.6pt, HALF-SANS),
    body,
  )),
  above: 0pt,
  below: 0pt,
)

#let figure-counter = counter("mag-figure")

#let fitted-image-height(width, pixels, max-height) = (
  pixels.at(1) * calc.min(width / pixels.at(0), max-height / pixels.at(1))
)

#let figure-image(id, path, pixels, spec) = layout(size => {
  let height = fitted-image-height(size.width, pixels, spec.max-height)
  let width = pixels.at(0) * height / pixels.at(1)
  block(height: height, width: 100%, spacing: 0pt, align(center, block(width: width, height: height, {
    place(top + left, [#metadata((id: id, width: width, height: height))<mag-figure-box>])
    place(top + left, clipped(width, height, image(path, width: width, height: height, fit: "stretch")))
    layer(place(top + left, rect(width: width, height: height, stroke: FIGURE-RULE + INK)))
  })))
})

#let figure-label(word) = context block(
  height: FIGURE-LABEL-ZONE,
  width: 100%,
  spacing: 0pt,
  {
    v(FIGURE-LABEL-PAD + ZERO-LEADING-SANS)
    text(
      font: SANS,
      size: CAPTION-SIZE,
      weight: 500,
      fill: VIOLET,
      ..flat,
      ..tracked(FIGURE-LABEL-TRACKING),
      upper(word) + " " + leading-zero(figure-counter.get().first()),
    )
  },
)

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
  body,
) = {
  assert(pixels != none, message: "figure " + id + " carries no pixel size; the emitter must state it")
  figure-counter.step()
  let spec = figure-spec(layout, anchor)
  spec.max-height -= trim
  flow-mark("figure", layout, _ => layer(block(
    above: 0pt,
    below: spec.gap,
    breakable: false,
    width: 100%,
    inset: spec.escape,
    move(dy: DATUM, {
      figure-label(word)
      figure-image(id, path, pixels, spec)
      body
    }),
  )))
}

#let quote-line(body) = par(body)
#let extract-caption(body) = block(
  text(font: SANS, size: CAPTION-SIZE, fill: VIOLET, ..edges(CAPTION-SIZE, CAPTION-SIZE * 1.35, HALF-SANS), body),
  above: EXTRACT-CAPTION-ABOVE,
  below: 0pt,
)
#let extract-label(word) = block(
  text(
    font: SANS,
    size: CAPTION-SIZE,
    weight: 500,
    fill: VIOLET,
    ..edges(CAPTION-SIZE, BODY-LEADING, HALF-SANS),
    ..tracked(EXTRACT-LABEL-TRACKING),
    upper(word),
  ),
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
      opener-parts.update(_ => ((tag: "art", body: art),))
    }
    body
    [#metadata(id)<mag-piece-end>]
  })
  page-cap(id, kind)
}
