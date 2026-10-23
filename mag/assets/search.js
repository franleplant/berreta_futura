(() => {
  const panel = document.querySelector(".search");
  const field = panel.querySelector("#q");
  const tally = panel.querySelector(".tally");
  const list = panel.querySelector(".hits");
  const marks = {
    "á": "a", "à": "a", "â": "a", "ä": "a", "ã": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "ö": "o", "õ": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ñ": "n", "ç": "c",
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
  };
  const fold = (text) =>
    text.toLowerCase().replace(/[^\x00-\x7f]/g, (c) => marks[c] || c);
  const terms = (query) => [...new Set(fold(query).split(/[^a-z0-9'+#.]+/).filter(Boolean))];

  let rows = null;
  let pending = null;

  const load = async () => {
    if (rows) return rows;
    if (!pending) {
      pending = fetch(panel.dataset.index)
        .then((r) => r.json())
        .then((data) => {
          rows = data.map((row) => ({
            ...row,
            head: fold(`${row.t} ${row.a} ${row.i} ${row.n}`),
            body: fold(row.x),
          }));
          return rows;
        });
    }
    return pending;
  };

  const score = (row, wanted) => {
    let total = 0;
    for (const term of wanted) {
      const inHead = row.head.includes(term);
      let hits = 0;
      let at = row.body.indexOf(term);
      while (at >= 0 && hits < 20) {
        hits += 1;
        at = row.body.indexOf(term, at + term.length);
      }
      if (!inHead && !hits) return 0;
      total += (inHead ? 50 : 0) + hits;
    }
    return total;
  };

  const snippet = (row, wanted) => {
    const found = wanted
      .map((term) => row.body.indexOf(term))
      .filter((at) => at >= 0)
      .sort((a, b) => a - b);
    if (!found.length) return "";
    const from = Math.max(0, found[0] - 90);
    const to = Math.min(row.x.length, found[0] + 170);
    const cut = row.x.slice(from, to);
    const flat = row.body.slice(from, to);
    const spans = [];
    for (const term of wanted) {
      let at = flat.indexOf(term);
      while (at >= 0) {
        spans.push([at, at + term.length]);
        at = flat.indexOf(term, at + term.length);
      }
    }
    spans.sort((a, b) => a[0] - b[0]);
    const piece = document.createElement("p");
    piece.className = "quote";
    let cursor = 0;
    for (const [start, end] of spans) {
      if (start < cursor) continue;
      piece.append(cut.slice(cursor, start));
      const hit = document.createElement("mark");
      hit.textContent = cut.slice(start, end);
      piece.append(hit);
      cursor = end;
    }
    piece.append(cut.slice(cursor));
    piece.prepend(from > 0 ? "…" : "");
    if (to < row.x.length) piece.append("…");
    return piece;
  };

  const render = (query) => {
    const wanted = terms(query);
    list.replaceChildren();
    if (!wanted.length) {
      tally.textContent = rows ? rows.length : "";
      return;
    }
    const found = rows
      .map((row) => [score(row, wanted), row])
      .filter(([points]) => points > 0)
      .sort((a, b) => b[0] - a[0] || a[1].u.localeCompare(b[1].u));
    tally.textContent = found.length ? found.length : panel.dataset.none;
    for (const [, row] of found) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = panel.dataset.base + row.u;
      const kicker = document.createElement("span");
      kicker.className = "kicker";
      kicker.textContent = `${row.i} · ${row.n}`;
      const title = document.createElement("h2");
      title.textContent = row.t;
      const byline = document.createElement("span");
      byline.className = "byline";
      byline.textContent = row.a;
      link.append(kicker, title, byline);
      const quote = snippet(row, wanted);
      if (quote) link.append(quote);
      item.append(link);
      list.append(item);
    }
  };

  const run = async () => {
    const query = field.value.trim();
    const url = new URL(window.location.href);
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", url);
    if (!query) {
      render("");
      return;
    }
    if (!rows) tally.textContent = panel.dataset.loading;
    await load();
    render(query);
  };

  field.addEventListener("input", run);
  const asked = new URL(window.location.href).searchParams.get("q");
  if (asked) {
    field.value = asked;
    run();
  }
  field.focus();
})();
