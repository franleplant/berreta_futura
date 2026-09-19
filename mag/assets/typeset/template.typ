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

#let edges(size, leading, half) = (
  top-edge: leading / 2 + half * size,
  bottom-edge: leading / 2 + half * size - leading,
)

#let pinned(leading) = (top-edge: DATUM, bottom-edge: DATUM - leading)

#let flat = (top-edge: 0pt, bottom-edge: 0pt)

#let tracked(amount) = (tracking: amount, features: (liga: 0, clig: 0))

#let publication = state("publication", [])

#let folio-text(body) = text(
  font: SANS,
  size: CAPTION-SIZE,
  weight: 500,
  fill: INK,
  ..flat,
  upper(body),
)

#let folio() = context {
  let index = counter(page).at(here()).first()
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
    folio-text(numbering("01", index)),
  )
}

#let plain-page() = page(margin: 0pt, background: none, [])

#let column(body) = pad(left: RAIL, right: RAIL - MEASURE-DELTA, body)

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
    background: folio(),
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

#let contents-kicker(body) = none
#let contents-label(body) = none
#let entry-label(body) = block(
  text(font: SANS, size: CAPTION-SIZE, weight: 500, ..flat, ..tracked(0.45pt), upper(body)),
  spacing: 8.6pt,
)
#let entry-title(body) = block(
  text(font: DISPLAY, size: 9.8pt, weight: 600, ..edges(9.8pt, 10.2pt, HALF-SERIF), body),
  spacing: 2.7pt,
)
#let entry-author(body) = block(
  text(font: SANS, size: CAPTION-SIZE, weight: 500, fill: SLATE, ..flat, upper(body)),
  spacing: 0pt,
)
#let contents-entry(destination: none, body) = block(body, spacing: 0pt)

#let contents(tight: false, body) = {
  pagebreak(weak: true)
  block(height: PAGE-HEIGHT - MARGIN-TOP - MARGIN-BOTTOM, width: 100%, column(body))
  pagebreak(weak: true)
}

#let content-label(body) = block(
  text(font: SANS, size: CAPTION-SIZE, weight: 500, ..flat, ..tracked(0.45pt), upper(body)),
  spacing: 7.53085pt,
)
#let label-primary(body) = text(fill: VIOLET, body)
#let label-secondary(body) = text(body)
#let label-separator(body) = text(body)
#let label-date(body) = text(fill: rgb(93, 96, 96), weight: 600, body)

#let piece-title(body) = block(
  text(font: DISPLAY, size: 24pt, weight: 600, ..edges(24pt, 24pt * 1.08, HALF-SERIF), body),
  spacing: 8pt,
)

#let byline-prefix(body) = text(size: 6.2pt, fill: VIOLET, body)
#let byline-name(body) = text(body)
#let byline(body) = block(
  text(font: SANS, size: 7.4pt, weight: 600, ..flat, upper(body)),
  above: 12pt,
  below: 0pt,
)
#let author-note(body) = block(
  text(font: SANS, size: CAPTION-SIZE, weight: 400, fill: SLATE, ..edges(CAPTION-SIZE, 9.45pt, HALF-SANS), body),
  above: 7.49326pt,
  below: 0pt,
)
#let provenance(body) = none
#let source-link(destination: none, source-id: none, body) = none

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

#let doc-paragraph(standfirst: false, roster: false, body) = {
  if standfirst {
    block(
      text(size: 12pt, ..pinned(16.4pt), body),
      below: 13pt,
    )
  } else {
    par(body)
  }
}

#let HEADINGS = (
  (font: DISPLAY, size: 22pt, leading: 25pt, above: 23.4pt, below: 13pt, fill: INK, caps: false),
  (font: DISPLAY, size: 18.5pt, leading: 21.5pt, above: 20.4pt, below: 11pt, fill: INK, caps: false),
  (font: SANS, size: 8.5pt, leading: 12pt, above: 15.4pt, below: 8pt, fill: VIOLET, caps: true),
)

#let doc-heading(level: 1, body) = {
  let spec = HEADINGS.at(calc.min(level, 3) - 1)
  block(
    text(
      font: spec.font,
      size: spec.size,
      weight: 600,
      fill: spec.fill,
      ..pinned(spec.leading),
      if spec.caps { upper(body) } else { body },
    ),
    above: spec.above,
    below: spec.below,
  )
}

#let doc-quote(body) = block(
  {
    set par(spacing: 0pt)
    grid(
      columns: (QUOTE-RULE, QUOTE-PAD, 1fr),
      rect(width: QUOTE-RULE, height: 100%, fill: VIOLET, stroke: none),
      [],
      body,
    )
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
    grid(
      columns: (QUOTE-RULE, 1fr),
      rect(width: QUOTE-RULE, height: 100%, fill: VIOLET, stroke: none),
      block(fill: PALE-VIOLET, width: 100%, inset: 3mm, body),
    )
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
  text(size: CAPTION-SIZE, ..edges(CAPTION-SIZE, 8.6pt, HALF-SERIF), body),
  above: 6.3pt,
  below: 0pt,
)
#let figure-credit(body) = block(
  text(
    font: SANS,
    size: CAPTION-SIZE,
    weight: 500,
    fill: SLATE,
    ..edges(CAPTION-SIZE, 8.6pt, HALF-SANS),
    body,
  ),
  above: 0pt,
  below: 0pt,
)
#let figure-block(
  id: none,
  source-id: none,
  anchor: none,
  layout: none,
  word: none,
  alt: none,
  body,
) = block(body, above: 0pt, below: 15.75pt, breakable: false)

#let quote-line(body) = par(body)
#let extract-caption(body) = block(
  text(font: SANS, size: CAPTION-SIZE, fill: VIOLET, ..edges(CAPTION-SIZE, CAPTION-SIZE * 1.35, HALF-SANS), body),
  above: 2pt,
  below: 0pt,
)
#let extract(id: none, source-id: none, anchor: none, style: none, word: none, body) = block(
  body,
  above: 5mm,
  below: 5mm,
  breakable: false,
)

#let tail-art() = none
#let closing-plate(index: 1, alt: none) = page(background: none, [])

#let piece(
  id: none,
  kind: none,
  short-title: none,
  source-ids: (),
  figure-layouts: (),
  opener: "plain",
  body,
) = {
  pagebreak(weak: true)
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
  column(body)
}
