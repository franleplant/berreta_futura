#import "/template.typ": mc-card, mc-palette

#let CS-RED = rgb("#f05738")
#let CS-INK = rgb("#0a0b0d")
#let CS-VIOLET = rgb("#4b21c0")
#let CS-NIGHT = rgb("#2a0f70")
#let CS-W = 297mm
#let CS-H = 210mm
#let CS-SCALE = 0.68
#let CS-CW = 128mm * CS-SCALE
#let CS-CH = 184mm * CS-SCALE
#let CS-GAP = 8mm
#let CS-TOP = 16mm
#let CS-UNIT = 38mm

#let cs-svg(path, colors) = {
  let svg = read(path)
  for (name, value) in colors {
    svg = svg.replace(regex("var\\(--" + name + "[^)]*\\)"), value)
  }
  bytes(svg.replace(regex("var\\(--[a-z]+, *(#[0-9a-fA-F]+)\\)"), m => m.captures.first()))
}
#let cs-mark(width) = image(cs-svg("/brand/mark.svg", ()), format: "svg", width: width)
#let cs-wordmark(width) = image(cs-svg("/brand/wordmark.svg", (ink: "#ffffff", paper: "#ffffff", red: "#f05738", box: "#0a0b0d")), format: "svg", width: width)

#let cs-halftone() = {
  let s = 2.6mm
  for row in range(0, 82) {
    for col in range(0, 116) {
      let v = (calc.sin((col * 0.16 + row * 0.1) * 1rad) + calc.sin((row * 0.21 - col * 0.07) * 1rad) + 2) / 4
      place(top + left, dx: col * s + if calc.odd(row) { s / 2 } else { 0mm }, dy: row * s, circle(radius: s * 0.45 * v, fill: CS-NIGHT))
    }
  }
}

#let cs-back(site) = {
  let unit = CS-UNIT
  let logo = box(width: unit, height: unit / 2, align(center + horizon, stack(spacing: unit * 0.05,
    cs-wordmark(unit * 0.8),
    text(font: "Inter", weight: 600, size: 5.5pt, fill: white, tracking: 0.03em, site))))
  let tile = box(width: unit, height: unit / 2, align(center + horizon, cs-mark(unit * 0.26)))
  let n = int(520mm / unit) + 2
  box(width: CS-W, height: CS-H, fill: CS-VIOLET, clip: true, {
    cs-halftone()
    place(center + horizon, rotate(-30deg, reflow: false, box(width: 500mm, height: 500mm,
      for row in range(-1, 2 * n) {
        for col in range(-1, n) {
          let dx = col * unit + if calc.odd(row) { unit / 2 } else { 0mm }
          place(top + left, dx: dx, dy: row * unit / 2, if calc.odd(row + col) { tile } else { logo })
        }
      })))
  })
}

#let cs-crops(x, y) = {
  let (o, l) = (1.5mm, 4mm)
  for (cx, cy) in ((x, y), (x + CS-CW, y), (x, y + CS-CH), (x + CS-CW, y + CS-CH)) {
    let sx = if cx == x { -1 } else { 1 }
    let sy = if cy == y { -1 } else { 1 }
    place(top + left, dx: cx + sx * o, dy: cy, line(end: (sx * l, 0mm), stroke: 0.3pt + luma(140)))
    place(top + left, dx: cx, dy: cy + sy * o, line(end: (0mm, sy * l), stroke: 0.3pt + luma(140)))
  }
}

#let cs-card(entry, labs) = scale(x: CS-SCALE * 100%, y: CS-SCALE * 100%, reflow: true, box(width: 128mm, height: 184mm,
  mc-card(entry.card, entry.art, mc-palette(entry.card.lab, labs), if entry.card.released != none { entry.card.released } else { entry.date })))

#let card-sheet(entries, labs: none, site: "") = {
  set page(width: CS-W, height: CS-H, margin: 0pt)
  let x0 = (CS-W - 3 * CS-CW - 2 * CS-GAP) / 2
  for (i, sheet) in entries.chunks(3).enumerate() {
    if i > 0 { pagebreak() }
    let start = x0 + (3 - sheet.len()) * (CS-CW + CS-GAP) / 2
    for (k, entry) in sheet.enumerate() {
      let x = start + k * (CS-CW + CS-GAP)
      place(top + left, dx: x, dy: CS-TOP, cs-card(entry, labs))
      cs-crops(x, CS-TOP)
      if entry.at("label", default: none) != none {
        place(top + left, dx: x, dy: CS-TOP + CS-CH + 4mm, box(width: CS-CW, align(center, text(font: "Inter", weight: 700, size: 13pt, fill: CS-INK, entry.label))))
      }
    }
    place(bottom + center, dy: -14mm, stack(dir: ltr, spacing: 4mm,
      box(height: 9mm, cs-mark(9mm)),
      align(horizon, text(font: "Inter", weight: 700, size: 11pt, fill: CS-INK, [Berreta Futura])),
      align(horizon, text(font: "Inter", size: 10pt, fill: luma(90), site))))
    pagebreak()
    place(top + left, cs-back(site))
  }
}
