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
  set text(font: SERIF, size: 10.75pt, fill: INK, lang: "en", hyphenate: true, number-type: "old-style")
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
