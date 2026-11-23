#let INK = rgb(27, 24, 22)
#let RUBRIC = rgb(186, 52, 31)
#let STONE = rgb(112, 104, 95)
#let PALE = rgb(246, 243, 237)
#let SERIF = ("EB Garamond", "Noto Sans Math")

#let folio = context {
  let n = counter(page).get().first()
  if n > 1 {
    align(if calc.odd(n) { right } else { left }, text(size: 8.5pt, fill: STONE, str(n)))
  }
}

#let title-page(title, author) = {
  set par(justify: false, first-line-indent: 0pt)
  v(1fr)
  text(size: 8.5pt, fill: RUBRIC, tracking: 0.12em, upper("The ideas in"))
  v(4mm)
  text(size: 26pt, weight: 600, hyphenate: false, title)
  v(3mm)
  text(size: 13pt, style: "italic", fill: STONE, author)
  v(1fr)
  line(length: 18mm, stroke: 0.6pt + RUBRIC)
  v(3mm)
  text(size: 9pt, fill: STONE)[What a friend who read it closely would tell you, so you know what the book offers and which parts to go read in full.]
  v(14mm)
  pagebreak()
}

#let digest(title: "", author: "", body) = {
  set document(title: title, author: author)
  set page(
    width: 148mm,
    height: 210mm,
    margin: (top: 17mm, bottom: 19mm, inside: 17mm, outside: 15mm),
    footer: folio,
  )
  set text(font: SERIF, size: 10.75pt, fill: INK, lang: "en", hyphenate: true, number-type: "old-style", number-width: "proportional", costs: (runt: 3000%, widow: 200%, orphan: 200%))
  set par(justify: true, leading: 0.6em, spacing: 0.6em, first-line-indent: 1.2em)
  show heading.where(level: 1): it => block(below: 6mm, text(size: 16pt, weight: 600, it.body))
  show heading.where(level: 2): it => block(above: 7mm, below: 3mm, sticky: true, text(size: 12.5pt, weight: 600, fill: RUBRIC, hyphenate: false, it.body))
  show heading.where(level: 3): it => block(above: 5mm, below: 2mm, sticky: true, text(size: 10.75pt, style: "italic", it.body))
  show raw.where(block: true): it => block(width: 100%, inset: 3mm, radius: 2pt, fill: PALE, breakable: true, text(font: "Geist Mono", size: 7.5pt, it))
  show raw.where(block: false): set text(font: "Geist Mono", size: 0.85em)
  show quote.where(block: true): it => pad(left: 1.2em, right: 0.8em, top: 1mm, bottom: 1mm, text(style: "italic", it.body))
  set list(indent: 0.6em, spacing: 0.5em)
  set enum(indent: 0.6em, spacing: 0.5em)
  title-page(title, author)
  body
}

#let SHEET-W = 297mm
#let SHEET-H = 210mm
#let TRIM-W = 140mm
#let TRIM-H = 198mm
#let CREAM = rgb(250, 246, 236)
#let in-body = state("book-body", false)

#let fleuron(fill, size: 10pt, glyph: "\u{2766}") = text(font: SERIF, size: size, fill: fill, glyph)

#let book-header(title) = context {
  let n = here().page()
  let opens = query(heading.where(level: 2)).any(h => h.location().page() == n)
  if in-body.get() and not opens {
    let before = query(heading.where(level: 2).before(here()))
    let label = if calc.even(n) or before.len() == 0 { title } else { before.last().body }
    set text(size: 7.5pt, fill: STONE, tracking: 0.14em, hyphenate: false)
    align(if calc.even(n) { left } else { right }, upper(label))
  }
}

#let book-footer = context {
  let n = here().page()
  if in-body.get() {
    align(if calc.odd(n) { right } else { left }, text(size: 9pt, fill: STONE, str(n)))
  }
}

#let blank-mark(ink) = place(center + horizon, line(length: 14mm, stroke: 0.5pt + ink.transparentize(40%)))

#let bare(body) = page(header: none, footer: none, {
  set par(first-line-indent: 0pt, justify: false)
  body
})

#let book-front(title, author, colophon, ink, accent) = {
  bare(align(center, { v(30%); text(size: 12pt, tracking: 0.06em, fill: ink, title) }))
  bare(blank-mark(ink))
  bare(align(center, {
    v(18%)
    text(size: 7.5pt, fill: accent, tracking: 0.3em, upper("The ideas in"))
    v(7mm)
    block(width: 88%, par(leading: 0.42em, text(size: 28pt, weight: 600, fill: ink, hyphenate: false, title)))
    v(6mm)
    text(size: 12.5pt, style: "italic", fill: STONE, author)
    v(1fr)
    fleuron(accent, size: 16pt)
    v(16mm)
  }))
  bare({
    v(1fr)
    set text(size: 7.75pt, fill: STONE)
    set par(leading: 0.55em, spacing: 0.9em)
    colophon
    v(6mm)
  })
  bare({
    v(16mm)
    text(size: 7.5pt, tracking: 0.3em, fill: accent, upper("Contents"))
    v(9mm)
    context for h in query(heading.where(level: 2)) {
      block(spacing: 3.6mm, grid(
        columns: (1fr, auto),
        column-gutter: 5mm,
        text(size: 10.5pt, fill: ink, hyphenate: false, h.body),
        text(size: 10.5pt, fill: STONE, str(h.location().page())),
      ))
    }
  })
  bare(blank-mark(ink))
}

#let book(title: "", author: "", colophon: [], ink: INK, accent: RUBRIC, size: 10.75pt, body) = {
  set document(title: title, author: author)
  set page(
    width: 148mm,
    height: 210mm,
    margin: (top: 21mm, bottom: 23mm, inside: 16mm, outside: 21mm),
    header: book-header(title),
    footer: book-footer,
  )
  set text(font: SERIF, size: size, fill: INK, lang: "en", hyphenate: true, number-type: "old-style", number-width: "proportional", costs: (runt: 3000%, widow: 200%, orphan: 200%))
  set par(justify: true, leading: 0.62em, spacing: 0.62em, first-line-indent: 1.2em, justification-limits: (tracking: (min: -0.012em, max: 0.012em)))
  show heading.where(level: 2): it => block(width: 100%, above: 9mm, below: 4.5mm, sticky: true, align(center, {
    set par(justify: false, leading: 0.5em)
    fleuron(accent, size: 9pt, glyph: "\u{2767}")
    v(1.5mm)
    pad(x: 14%, text(size: 9.5pt, weight: 600, fill: ink, tracking: 0.12em, hyphenate: false, upper(it.body)))
  }))
  show heading.where(level: 3): it => block(above: 5mm, below: 2mm, sticky: true, text(style: "italic", it.body))
  show raw.where(block: true): it => block(width: 100%, inset: 3mm, radius: 2pt, fill: PALE, breakable: true, text(font: "Geist Mono", size: 7.5pt, it))
  show raw.where(block: false): set text(font: "Geist Mono", size: 0.85em)
  show quote.where(block: true): it => block(above: 4mm, below: 4mm, breakable: false, inset: (left: 4mm, right: 6mm, y: 1mm), stroke: (left: 1.2pt + accent), {
    set par(first-line-indent: 0pt, justify: false)
    text(size: 1.05em, style: "italic", fill: ink, it.body)
  })
  set list(indent: 0.6em, spacing: 0.55em, marker: text(fill: accent, "\u{2022}"))
  set enum(indent: 0.6em, spacing: 0.55em, numbering: n => text(fill: accent, weight: 600, str(n) + "."))
  book-front(title, author, colophon, ink, accent)
  in-body.update(true)
  body
}

#let opener(lead, ink, accent, rest) = {
  v(14mm)
  block(par(first-line-indent: 0pt, text(size: 11.75pt, {
    text(fill: ink, tracking: 0.04em, smallcaps(lead))
    [ ]
    rest
  })))
  v(2mm)
}

#let blank-pages(n, accent) = {
  v(6mm)
  align(center, fleuron(accent, size: 12pt))
  in-body.update(false)
  for i in range(n) {
    pagebreak()
    blank-mark(accent)
  }
}

#let motif-cell(motif, ink, accent) = {
  let s = (stroke: 0.55pt + ink)
  if motif == "peaks" {
    tiling(size: (16mm, 22mm), {
      for (dx, dy) in ((2mm, 2mm), (-6mm, 13mm), (10mm, 13mm)) {
        place(dx: dx, dy: dy, polygon(..s, (1.2mm, 6.6mm), (6mm, 1.4mm), (10.8mm, 6.6mm)))
        place(dx: dx, dy: dy, line(start: (3.6mm, 6.6mm), end: (6mm, 4mm), ..s))
      }
      place(dx: 7.3mm, dy: 15.2mm, circle(radius: 0.7mm, fill: accent))
      place(dx: -0.7mm, dy: 4.2mm, circle(radius: 0.7mm, fill: accent))
      place(dx: 15.3mm, dy: 4.2mm, circle(radius: 0.7mm, fill: accent))
    })
  } else {
    tiling(size: (15mm, 15mm), {
      place(line(start: (0mm, 0mm), end: (15mm, 15mm), ..s))
      place(line(start: (15mm, 0mm), end: (0mm, 15mm), ..s))
      place(dx: 6.4mm, dy: 6.4mm, circle(radius: 1.1mm, fill: accent))
      for (x, y) in ((7.5mm, 0mm), (0mm, 7.5mm), (15mm, 7.5mm), (7.5mm, 15mm)) {
        place(dx: x - 0.45mm, dy: y - 0.45mm, circle(radius: 0.45mm, fill: ink))
      }
    })
  }
}

#let crop-marks(x0, y0, w, h, fold, color) = {
  let s = 0.35pt + color
  let gap = 1.5mm
  for x in (x0, x0 + w) {
    for (from, to) in ((0mm, y0 - gap), (y0 + h + gap, SHEET-H)) {
      place(line(start: (x, from), end: (x, to), stroke: s))
    }
  }
  for y in (y0, y0 + h) {
    for (from, to) in ((0mm, x0 - gap), (x0 + w + gap, SHEET-W)) {
      place(line(start: (from, y), end: (to, y), stroke: s))
    }
  }
  for x in fold {
    place(line(start: (x, 0mm), end: (x, y0 - gap), stroke: (paint: color, thickness: 0.35pt, dash: "dashed")))
    place(line(start: (x, y0 + h + gap), end: (x, SHEET-H), stroke: (paint: color, thickness: 0.35pt, dash: "dashed")))
  }
}

#let book-cover(title: "", author: "", blurb: [], ink: INK, accent: RUBRIC, spine: 2mm, motif: "lattice") = {
  set document(title: title + " (cover)", author: author)
  set page(width: SHEET-W, height: SHEET-H, margin: 0pt, fill: ink)
  set text(font: SERIF, fill: CREAM, lang: "en", hyphenate: true, number-type: "old-style")
  set par(first-line-indent: 0pt)
  let wrap = 2 * TRIM-W + spine
  let x0 = (SHEET-W - wrap) / 2
  let y0 = (SHEET-H - TRIM-H) / 2
  let front = x0 + TRIM-W + spine
  let band = 34mm
  place(dy: y0 + TRIM-H - band, rect(width: 100%, height: band + y0, fill: motif-cell(motif, CREAM.transparentize(35%), accent)))
  place(dy: y0 + TRIM-H - band, line(length: 100%, stroke: 0.8pt + accent))
  place(dx: front + 15mm, dy: y0 + 20mm, block(width: TRIM-W - 30mm, {
    text(size: 8pt, fill: accent, tracking: 0.32em, upper("The ideas in"))
    v(7mm)
    par(leading: 0.4em, justify: false, text(size: 31pt, weight: 600, hyphenate: false, title))
    v(7mm)
    line(length: 18mm, stroke: 1pt + accent)
    v(5mm)
    text(size: 14pt, style: "italic", author)
  }))
  place(dx: x0 + 15mm, dy: y0 + 20mm, block(width: TRIM-W - 30mm, {
    text(size: 7.5pt, fill: accent, tracking: 0.32em, upper("In thirty seconds"))
    v(5mm)
    set par(justify: true, leading: 0.6em)
    text(size: 9.25pt, blurb)
  }))
  if spine >= 4mm {
    let size = calc.min(spine * 0.42, 9pt)
    place(dx: x0 + TRIM-W + spine, dy: y0, rotate(90deg, origin: top + left, reflow: false,
      box(width: TRIM-H - band, height: spine, inset: (x: 8mm), align(horizon, text(size: size, tracking: 0.08em, {
        upper(title)
        h(1fr)
        text(style: "italic", fill: accent, author)
      })))))
  }
  crop-marks(x0, y0, wrap, TRIM-H, (x0 + TRIM-W, front), CREAM)
}

#let book-endpaper(ink: INK, accent: RUBRIC, motif: "lattice") = {
  set page(width: SHEET-W, height: SHEET-H, margin: 0pt, fill: CREAM)
  place(rect(width: 100%, height: 100%, fill: motif-cell(motif, ink.transparentize(25%), accent)))
}
