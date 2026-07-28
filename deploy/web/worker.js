/**
 * Router over the assembled static tree (see assemble.py and
 * docs/WEB_DEPLOY.md). Everything editorial lives in editions.json, written
 * at assembly time from the release ledger; this Worker only follows it.
 * It never lists directories and never invents an edition.
 *
 * `run_worker_first` in wrangler.jsonc sends every request through here so
 * the cache headers below actually attach to asset responses. The price is
 * a manifest read per request, paid once per isolate by the module-level
 * cache: a deploy replaces the Worker's isolates, so a cached manifest
 * never outlives the deploy that shipped it.
 */

let cachedManifest = null;

async function manifest(env, url) {
  if (cachedManifest !== null) return cachedManifest;
  const response = await env.ASSETS.fetch(new URL("/editions.json", url));
  if (!response.ok) return null;
  cachedManifest = await response.json();
  return cachedManifest;
}

// Manifest values come from the release ledger via assemble.py, so they are
// trusted in practice — but an edition id is still data, not markup, and a
// `<` in one must never become an element.
function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
}

function editionsIndex(data) {
  const rows = data.editions
    .map((edition) => {
      const links = edition.languages
        .map(
          (language) =>
            `<a href="/${encodeURIComponent(edition.id)}/${encodeURIComponent(language)}/">${escapeHtml(language)}</a>`,
        )
        .join(" · ");
      const date = edition.publication_date
        ? ` — ${escapeHtml(edition.publication_date)}`
        : "";
      const state = edition.released ? "" : " (preview)";
      return `<li>${escapeHtml(edition.id)}${date}${state}: ${links}</li>`;
    })
    .join("\n");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Editions</title></head>
<body><h1>Editions</h1><ul>
${rows}
</ul></body></html>`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/" || path === "/editions" || path === "/editions/") {
      const data = await manifest(env, url);
      if (!data) return new Response("no editions assembled", { status: 503 });
      if (path === "/") {
        // `latest` names the newest RELEASED edition or nothing at all; a
        // previews-only deploy answers the root like any unknown route, so a
        // preview is reachable only by its explicit URL.
        if (!data.latest) return new Response("not found", { status: 404 });
        const to = `/${data.latest}/${data.primary_language}/`;
        return Response.redirect(new URL(to, url), 302);
      }
      return new Response(editionsIndex(data), {
        headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
      });
    }

    // /<edition-id> without a language: send readers to the primary language.
    const segments = path.split("/").filter(Boolean);
    if (segments.length === 1 && segments[0] !== "editions.json") {
      const data = await manifest(env, url);
      const edition = data?.editions.find((item) => item.id === segments[0]);
      if (edition) {
        const language = edition.languages.includes(data.primary_language)
          ? data.primary_language
          : edition.languages[0];
        return Response.redirect(new URL(`/${edition.id}/${language}/`, url), 302);
      }
    }

    const response = await env.ASSETS.fetch(request);

    // Released editions are immutable artifacts, so their paths may cache
    // forever; previews rebuild at will, so they must not. The manifest is
    // the deploy's own state and always revalidates.
    if (response.ok) {
      const headers = new Headers(response.headers);
      if (path === "/editions.json") {
        headers.set("cache-control", "no-store");
      } else if (segments.length >= 1) {
        const data = await manifest(env, url);
        const edition = data?.editions.find((item) => item.id === segments[0]);
        if (edition) {
          headers.set(
            "cache-control",
            edition.released ? "public, max-age=31536000, immutable" : "no-store",
          );
        }
        return new Response(response.body, { status: response.status, headers });
      }
      return new Response(response.body, { status: response.status, headers });
    }
    return response;
  },
};
