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

  const parse = (query) => {
    const out = [];
    const pattern = /"([^"]*)"|([^\s"]+)/g;
    let found;
    while ((found = pattern.exec(fold(query)))) {
      if (found[1] === undefined) {
        for (const word of found[2].split(/[^a-z0-9'+#.]+/)) {
          if (word) out.push(word);
        }
      } else {
        const phrase = found[1].trim().replace(/\s+/g, " ");
        if (phrase) out.push(phrase);
      }
    }
    return [...new Set(out)];
  };

  const spots = (hay, needle, cap) => {
    const out = [];
    let at = hay.indexOf(needle);
    while (at >= 0 && out.length < cap) {
      out.push([at, at + needle.length]);
      at = hay.indexOf(needle, at + needle.length);
    }
    return out;
  };

  const edge = (hay, at) => !/[a-z0-9]/.test(hay.charAt(at) || " ");
  const whole = (hay, found) =>
    found.filter(([start, end]) => edge(hay, start - 1) && edge(hay, end));

  const tightest = (lists) => {
    if (!lists.length) return null;
    if (lists.length === 1) return lists[0][0];
    const seen = lists.map(() => 0);
    let best = null;
    for (;;) {
      let from = Infinity;
      let to = 0;
      let first = 0;
      for (let i = 0; i < lists.length; i += 1) {
        const [start, end] = lists[i][seen[i]];
        if (start < from) {
          from = start;
          first = i;
        }
        if (end > to) to = end;
      }
      if (!best || to - from < best[1] - best[0]) best = [from, to];
      seen[first] += 1;
      if (seen[first] >= lists[first].length) return best;
    }
  };

  const nearness = (span) => {
    if (span <= 80) return 400;
    if (span <= 200) return 150;
    if (span <= 600) return 40;
    return 0;
  };

  const rank = (row, needles) => {
    let points = 0;
    let sloppy = false;
    const lists = [];
    for (const needle of needles) {
      const inHead = row.head.includes(needle);
      const at = spots(row.body, needle, 40);
      if (!inHead && !at.length) return null;
      const exact = whole(row.body, at);
      const named = inHead && whole(row.head, spots(row.head, needle, 4)).length;
      points +=
        (named ? 120 : inHead ? 40 : 0) +
        exact.length * 4 +
        (at.length - exact.length) +
        (needle.includes(" ") ? 150 : 0);
      if (!exact.length && !named) sloppy = true;
      if (at.length) lists.push(exact.length ? exact : at);
    }
    const window = tightest(lists);
    if (window && needles.length > 1) {
      points += nearness(window[1] - window[0]) * (sloppy ? 0.2 : 1);
    }
    return { points, window };
  };

  const snippet = (row, needles, window) => {
    if (!window) return null;
    const middle = (window[0] + window[1]) / 2;
    const width = Math.max(260, window[1] - window[0] + 120);
    const from = Math.max(0, Math.round(middle - width / 2));
    const to = Math.min(row.x.length, from + width);
    const cut = row.x.slice(from, to);
    const flat = row.body.slice(from, to);
    const hits = needles.flatMap((needle) => spots(flat, needle, 40));
    hits.sort((a, b) => a[0] - b[0]);
    const quote = document.createElement("p");
    quote.className = "quote";
    let cursor = 0;
    for (const [start, end] of hits) {
      if (start < cursor) continue;
      quote.append(cut.slice(cursor, start));
      const hit = document.createElement("mark");
      hit.textContent = cut.slice(start, end);
      quote.append(hit);
      cursor = end;
    }
    quote.append(cut.slice(cursor));
    if (from > 0) quote.prepend("…");
    if (to < row.x.length) quote.append("…");
    return quote;
  };

  let rows = null;
  let pending = null;

  const load = () => {
    if (rows) return Promise.resolve(rows);
    if (!pending) {
      pending = fetch(panel.dataset.index)
        .then((reply) => reply.json())
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

  const render = (query) => {
    const needles = parse(query);
    list.replaceChildren();
    if (!needles.length) {
      tally.textContent = rows ? rows.length : "";
      return;
    }
    const found = rows
      .map((row) => [rank(row, needles), row])
      .filter(([scored]) => scored)
      .sort((a, b) => b[0].points - a[0].points || a[1].u.localeCompare(b[1].u));
    tally.textContent = found.length ? found.length : panel.dataset.none;
    for (const [scored, row] of found) {
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
      const quote = snippet(row, needles, scored.window);
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
