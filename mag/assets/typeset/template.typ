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
#let COOL-GRAY = rgb(88%, 89%, 90%)
#let PALE-VIOLET = rgb(95.5%, 94.5%, 97.5%)
#let SIGNAL-ORANGE = rgb(240, 87, 56)

#let SERIF = "Source Serif 4 SmText"
#let DISPLAY = ("Source Serif 4 Display", "Source Serif 4 SmText")
#let SANS = "Inter"
#let MONO = "Geist Mono"

#let HALF-SERIF = 0.3505
#let HALF-SANS = 0.36377
#let HALF-MONO = 0.355

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
#let CONTENTS-ROW-MAX = 65.5pt
#let CONTENTS-ROWS-MIN = 6
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
#let OPENER-ART-FLOW = 195.1pt
#let OPENER-META-MEASURE = 293pt
#let OPENER-PANGO-RESERVE = 13.2pt
#let CONTENT-HEIGHT = PAGE-HEIGHT - MARGIN-TOP - MARGIN-BOTTOM
#let OPENER-FRAME-HEIGHT = 203pt
#let OPENER-OFFSET = 4.1pt
#let OPENER-BORDER = 2.4pt
#let OPENER-QR = 41pt
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
  folio(index)
  running-head(index)
}

#let plain-page() = page(margin: 0pt, background: none, [])

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

#let tail-layer() = context {
  let page = here().page()
  for tail in query(<mag-tail>).map(m => m.value).filter(t => t.printed and t.page == page) {
    let x = if calc.odd(page) { MARGIN-INNER } else { MARGIN-OUTER }
    let y = PAGE-HEIGHT - MARGIN-BOTTOM + DATUM - tail.height
    place(top + left, dx: x + RAIL, dy: y, image(tail.path, width: MEASURE, height: tail.height, fit: tail.fit))
  }
}

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
    background: furniture(),
    foreground: tail-layer(),
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
  let height = calc.min(CONTENTS-BAND / calc.max(CONTENTS-ROWS-MIN, entries.len()), CONTENTS-ROW-MAX)
  block(height: PAGE-HEIGHT - MARGIN-TOP - MARGIN-BOTTOM, width: 100%, context {
    let kicker = part(rows, "kicker")
    let label = part(rows, "label")
    if kicker != none {
      place(top + left, dy: CONTENTS-KICKER-TOP + ZERO-LEADING-SANS, contents-caption(kicker))
    }
    if label != none {
      place(top + left, dy: CONTENTS-TITLE-TOP + CONTENTS-TITLE-SIZE * HALF-SERIF, {
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

#let escaped(body) = pad(left: -OPENER-ESCAPE, right: -OPENER-ESCAPE, body)

#let collect(name, body) = opener-parts.update(p => if p == none {
  p
} else {
  p + ((tag: name, body: body),)
})

#let opener-art() = block(
  width: 100%,
  height: OPENER-ART-HEIGHT - OPENER-ART-LIFT,
  above: 0pt,
  below: 0pt,
  place(top + left, dx: -OPENER-ESCAPE, dy: -OPENER-ART-LIFT, {
    place(top + left, dx: OPENER-OFFSET, dy: OPENER-OFFSET, {
      rect(width: OPENER-RAIL, height: OPENER-FRAME-HEIGHT, fill: SIGNAL-ORANGE, stroke: none)
    })
    place(top + left, dx: OPENER-BORDER / 2, dy: OPENER-BORDER / 2, {
      rect(
        width: OPENER-RAIL - OPENER-BORDER,
        height: OPENER-FRAME-HEIGHT - OPENER-BORDER,
        fill: white,
        stroke: OPENER-BORDER + PAPER-INK,
      )
    })
  }),
)

#let content-label(body) = context if opener-parts.get() == none {
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

#let piece-title(body) = context if opener-parts.get() == none {
  block(
    text(font: DISPLAY, size: 24pt, weight: 600, ..edges(24pt, 24pt * 1.08, HALF-SERIF), body),
    spacing: 8pt,
  )
} else {
  collect("title", body)
}

#let byline-prefix(body) = context if opener-parts.get() == none {
  text(size: OPENER-PREFIX-SIZE, fill: VIOLET, body)
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
#let byline(body) = context if opener-parts.get() == none {
  block(
    text(font: SANS, size: OPENER-BYLINE-SIZE, weight: 600, ..flat, upper(body)),
    above: 12pt,
    below: 0pt,
  )
} else {
  collect("byline", body)
}
#let author-note(body) = context if opener-parts.get() == none {
  block(
    text(
      font: SANS,
      size: CAPTION-SIZE,
      weight: 400,
      fill: SLATE,
      ..edges(CAPTION-SIZE, 9.45pt, HALF-SANS),
      body,
    ),
    above: 7.49326pt,
    below: 0pt,
  )
} else {
  collect("note", body)
}
#let provenance(body) = none
#let source-link(destination: none, source-id: none, body) = context if opener-parts.get() != none {
  collect("source", destination)
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
    ..edges(OPENER-BYLINE-SIZE, OPENER-BYLINE-LEADING, HALF-SANS),
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

#let source-code(destination) = {
  let code = rect(width: OPENER-QR, height: OPENER-QR, fill: none, stroke: none)
  if destination == none { return code }
  place(top + left, link(destination, box(width: OPENER-QR, height: OPENER-QR)))
  link(destination, code)
}

#let opener-page(rows, body, split) = {
  let title = opener-part(rows, "title")
  let fit = fitted-title(title, OPENER-TITLE-MAX)
  let density = OPENER-STANDARD
  if split or opener-stack(density, fit, rows, body) + OPENER-PANGO-RESERVE > CONTENT-HEIGHT {
    density = OPENER-COMPACT
    fit = fitted-title(title, OPENER-COMPACT-TITLE-MAX)
  }
  block(breakable: false, above: 0pt, below: 0pt, {
    opener-art()
    block(above: density.label, below: 0pt, escaped(text(
      font: SANS,
      size: OPENER-LABEL-SIZE,
      weight: 600,
      fill: PAPER-BLUE,
      ..edges(OPENER-LABEL-SIZE, OPENER-LABEL-LEADING, HALF-SANS),
      ..tracked(OPENER-LABEL-TRACKING * OPENER-LABEL-SIZE),
      upper(opener-part(rows, "label")),
    )))
    block(above: density.title-gap, below: 0pt, escaped({
      set par(leading: 0pt, spacing: 0pt)
      text(..tracked(OPENER-TITLE-TRACKING * fit.size), opener-title-text(fit.size, title))
    }))
    block(
      above: density.tick,
      below: 0pt,
      escaped(block(width: OPENER-TICK-WIDTH, height: OPENER-TICK, fill: SIGNAL-ORANGE, spacing: 0pt)),
    )
    v(density.meta-pad)
    block(above: 0pt, below: 0pt, escaped(grid(
      columns: (1fr, OPENER-QR),
      column-gutter: OPENER-GAP,
      align: horizon,
      credit-column(rows),
      source-code(opener-part(rows, "source")),
    )))
    v(density.meta-pad)
    escaped(block(width: 100%, height: OPENER-META-RULE, fill: PAPER-RULE, spacing: 0pt))
    block(above: density.standfirst-gap, below: 0pt, escaped({
      set par(leading: 0pt, spacing: 0pt)
      standfirst-text(density, body)
    }))
  })
}

#let opener-standfirst(rows, body, split) = {
  opener-page(rows, body, split)
  opener-parts.update(_ => none)
  context v(PAGE-HEIGHT - MARGIN-BOTTOM - here().position().y)
}

#let doc-link(destination: none, title: none, body) = link(destination, body)

#let inline-code(body) = text(
  font: MONO,
  size: 0.82 * BODY-SIZE,
  weight: 500,
  fill: VIOLET,
  hyphenate: false,
  body,
)

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
  (font: DISPLAY, size: 22pt, leading: 25pt, above: 23.4pt, below: 13pt, fill: INK, caps: false),
  (font: DISPLAY, size: 18.5pt, leading: 21.5pt, above: 20.4pt, below: 11pt, fill: INK, caps: false, drop: 15pt),
  (font: SANS, size: 8.5pt, leading: 12pt, above: 15.4pt, below: 8pt, fill: VIOLET, caps: true, drop: 10pt),
)

#let heading-stack(spec, above, escape, drop, body) = {
  block(above: above, below: 0pt, breakable: false, width: 100%, inset: escape, {
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
  })
  v(-HEADING-CLEARANCE)
}

#let doc-heading(level: 1, body) = {
  let spec = HEADINGS.at(calc.min(level, 3) - 1)
  flow-mark("heading", none, index => {
    let anchor = level >= 2 and level <= 3 and band-anchored(index)
    let midpage = anchor and here().position().y > MARGIN-TOP + PAGE-TOP-EPSILON
    heading-stack(
      spec,
      if anchor { auto } else { spec.above },
      if anchor { BAND-ESCAPE } else { NO-ESCAPE },
      if midpage { spec.drop } else { 0pt },
      body,
    )
  })
}

#let ruled(pad-left, pad-rest, fill-color, body) = pad(left: QUOTE-RULE / 2, block(
  stroke: (left: QUOTE-RULE + VIOLET),
  fill: fill-color,
  inset: (left: pad-left + QUOTE-RULE / 2, rest: pad-rest),
  width: 100%,
  above: 0pt,
  below: 0pt,
  body,
))

#let doc-quote(body) = block(
  {
    set par(spacing: 0pt)
    ruled(QUOTE-PAD, 0pt, none, body)
  },
  above: 4mm,
  below: 4mm,
)

#let doc-code(lang: "", body) = block(
  {
    set par(leading: 0pt, spacing: 0pt)
    set text(
      font: MONO,
      size: 7.5pt,
      weight: 400,
      fill: INK,
      hyphenate: false,
      ..edges(7.5pt, 7.5pt * 1.3, HALF-MONO),
    )
    ruled(3mm, 3mm, PALE-VIOLET, body)
  },
  above: PARAGRAPH-AFTER,
  below: PARAGRAPH-AFTER,
)

#let reference-list = state("reference-list", false)

#let doc-item(body) = context {
  if reference-list.get() {
    block(body, above: 0pt, below: 3pt)
  } else {
    block(
      {
        place(top + left, dy: 3.505pt, circle(radius: 2.5pt, fill: VIOLET, stroke: none))
        pad(left: LIST-INDENT, body)
      },
      above: 0pt,
      below: 6pt,
    )
  }
}

#let doc-list(ordered: false, start: 1, references: false, body) = block(
  {
    reference-list.update(_ => references)
    set par(spacing: 0pt)
    if references {
      set text(size: 7.2pt, ..pinned(9.4pt))
      set par(hanging-indent: REFERENCE-HANG)
      body
    } else {
      body
    }
    reference-list.update(_ => false)
  },
  above: PARAGRAPH-AFTER,
  below: PARAGRAPH-AFTER,
)

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
  v(-20pt)
  block(
    height: 0pt,
    width: 100%,
    above: 0pt,
    below: 0pt,
    {
      place(
        top + left,
        dy: 28.53085pt - 0.07625pt - 2.47375pt,
        rect(width: 17pt, height: 1.1pt, fill: SIGNAL-ORANGE, stroke: none),
      )
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
    },
  )
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
    place(top + left, image(path, width: width, height: height, fit: "stretch"))
    place(top + left, rect(width: width, height: height, stroke: FIGURE-RULE + INK))
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
  body,
) = {
  assert(pixels != none, message: "figure " + id + " carries no pixel size; the emitter must state it")
  figure-counter.step()
  let spec = figure-spec(layout, anchor)
  flow-mark("figure", layout, _ => block(
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
  ))
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
    ..edges(CAPTION-SIZE, CAPTION-SIZE, HALF-SANS),
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

#let tail-art(article: none, path: none, pixels: none, fit: "cover") = context {
  let baseline = query(selector(<mag-end-baseline>).before(here())).last().location().position()
  let height = calc.min(MEASURE * pixels.at(1) / pixels.at(0), TAIL-MAX-HEIGHT)
  let room = PAGE-HEIGHT - baseline.y - TAIL-FRAME-BOTTOM - TAIL-CLEARANCE
  let printed = room >= height
  let tail = (article: article, printed: printed, height: height, room: room, page: baseline.page)
  [#metadata(tail + (path: path, fit: fit))<mag-tail>]
}


#let plates = state("mag-plates", ())
#let piece-counter = counter("mag-piece-ordinal")

#let py-round(value) = {
  let whole = calc.floor(value)
  let rest = value - whole
  if rest > 0.5 or (rest == 0.5 and calc.odd(whole)) { whole + 1 } else { whole }
}

#let plate-slots(articles, count) = range(1, count + 1).map(j => py-round(j * articles / count))

#let plate-page(plate) = page(
  background: none,
  place(top + left, dy: -MARGIN-TOP, image(plate.path, width: LIVE-WIDTH, height: PAGE-HEIGHT, fit: "contain")),
)

#let plate-plan() = {
  let all = plates.final()
  let articles = query(<mag-piece>).len()
  if all.len() == 0 or articles == 0 { (none, 0, ()) } else {
    (all, articles, plate-slots(articles, all.len()))
  }
}

#let plates-before(ordinal) = context {
  let (all, articles, slots) = plate-plan()
  if all == none { return }
  for (j, slot) in slots.enumerate() {
    if slot == ordinal - 1 { plate-page(all.at(j)) }
  }
}

#let closing-plate(index: 1, alt: none, path: none) = {
  plates.update(p => p + ((index: index, alt: alt, path: path),))
  context {
    let (all, articles, slots) = plate-plan()
    if all == none { return }
    let j = all.position(p => p.index == index)
    if slots.at(j) == articles { plate-page(all.at(j)) }
  }
}

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
  body,
) = {
  piece-counter.step()
  context plates-before(piece-counter.get().first())
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
    [#metadata((id: id, head: short-title))<mag-piece>]
    if opener == ILLUSTRATED {
      opener-parts.update(_ => ())
    }
    body
    [#metadata(id)<mag-piece-end>]
  })
  page-cap(id, kind)
}
