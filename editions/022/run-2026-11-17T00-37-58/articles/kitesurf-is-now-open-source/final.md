---
source_ids:
- kitesurf-is-now-open-source-a443b3b0
content_mode: verbatim
label: VERBATIM
---

We [introduced](https://blog.cloudflare.com/kitesurf/) [Kitesurf](https://kitesurf.dev/), our stateless browser for AI agents that runs entirely on top of Workers, in August and [followed up](https://blog.cloudflare.com/kitesurf-update/) in September with WebMCP support, new APIs, and improved compatibility. On every occasion, we mentioned our commitment to open sourcing it so that developers could run their own browser engine on their own Cloudflare accounts if they want to.

That promise is now real. [Kitesurf is open source on GitHub](https://github.com/cloudflare/kitesurf) under the Apache 2.0 license. You can read the code, run it locally, change it, and deploy your own instance to Cloudflare Workers.

## A browser built for agents

Kitesurf runs entirely on Cloudflare Workers. It parses HTML, applies CSS, executes page JavaScript, and renders screenshots without a browser container. It supports the Chrome DevTools Protocol (CDP), so you can connect clients such as Puppeteer.

Our main goal is to give AI agents a lightweight, efficient browser — one that can load websites, execute JavaScript, and interact with pages while using less CPU and memory than a full browser like Chromium, and scaling on demand across Cloudflare's global Workers network.

Read more about why and how we built Kitesurf in our initial [announcement](https://blog.cloudflare.com/kitesurf/) and how to use it in Browser Run's [developer](https://developers.cloudflare.com/browser-run/kitesurf/) documentation.

## What is inside the repository?

Kitesurf builds on Cloudflare's Developer Platform and APIs, alongside an ecosystem of open-source Rust packages compiled to WebAssembly:

- [Blitz](https://github.com/DioxusLabs/blitz) provides HTML parsing, the DOM, layout, and painting.
- [Stylo](https://github.com/servo/stylo) provides CSS parsing, cascading, and computed styles.
- [Boa](https://github.com/boa-dev/boa) runs JavaScript inside WebAssembly (as the last resort only when we can't run JavaScript in Dynamic Workers).
- [Linebender](https://linebender.org/) libraries provide text layout and 2D graphics, and [Krilla](https://github.com/LaurenzV/krilla) generates PDF output.

These projects made Kitesurf possible. They retain their respective licenses; the repository's [NOTICE](https://github.com/cloudflare/kitesurf/blob/main/NOTICE) documents third-party notices.

Kitesurf has three main parts: the Engine manages browser sessions and client connections, PageScript runs the page and its JavaScript, and PageRenderer draws the result.

All packages, the engine, its Rust core, DOM shims, renderer, and [Kitesurf CLI](https://github.com/cloudflare/kitesurf/tree/main/packages/kitesurf-cli) live separately in folders under the repository's [packages](https://github.com/cloudflare/kitesurf/tree/main/packages) directory where you can explore how all the pieces fit together.

## Run your own Kitesurf

To run Kitesurf locally, follow the repository's [build requirements](https://github.com/cloudflare/kitesurf#requirements), then clone the [repository](https://github.com/cloudflare/kitesurf), install dependencies, and start the engine:

```
git clone https://github.com/cloudflare/kitesurf.git
cd kitesurf
pnpm install --frozen-lockfile
pnpm run dev
```

The first build compiles the Rust core and its dependencies, so give it some time. Subsequent builds reuse the build cache. Finally wrangler starts a local development server at **http://127.0.0.1:8787**. Open that address to try a page in Chrome DevTools, or use it programmatically.

You can use [puppeteer](https://github.com/cloudflare/kitesurf/tree/main#connect-with-puppeteer) with a NodeJS script:

```
import puppeteer from "puppeteer-core";

const browser = await puppeteer.connect({
  browserWSEndpoint: "ws://127.0.0.1:8787/devtools/browser",
});

try {
  const page = await browser.newPage();
  await page.goto("https://example.com/");
  await page.screenshot({ path: "page.png" });
} finally {
  await browser.disconnect();
}
```

Or you can point your AI harness at the local [CDP](https://github.com/cloudflare/kitesurf/tree/main#use-chrome-devtools) port (agents love CDP) and watch it take full control of Kitesurf.

## Deploy to your Cloudflare account

When you're done changing and testing locally, you can [deploy the engine to your own account](https://github.com/cloudflare/kitesurf#cloudflare-deployment) and use Kitesurf from there instead of the Browser Run managed APIs we provide. Note that a Workers Paid plan is required because Kitesurf uses [Dynamic Workers](https://developers.cloudflare.com/dynamic-workers/) to create isolated Workers for pages.

From the repository root:

```
pnpm run deploy
```

## Help us make it better

As with all of our open-sourced projects, Kitesurf lives in Github and we welcome forks and [contributions](https://github.com/cloudflare/kitesurf/pulls). However, note that Kitesurf is under heavy development and we are focusing on making the engine more compatible (check out [Web Platform Test evolution](https://kitesurf.dev/wpt)), more reliable, and [efficient](https://kitesurf.dev/benchmarks).

Start with the [contribution guidelines](https://github.com/cloudflare/kitesurf/blob/main/CONTRIBUTING.md) if you want to contribute. Open an issue with a minimal reproduction or a proposed approach, and get vouched by a maintainer before opening a pull request. Focused fixes with tests, clear evidence, and a well-defined scope are much easier to review than large rewrites or unrelated cleanup, but all contribution does not have to be code: a small page that reproduces a rendering bug, a failing automation workflow, or a clear documentation correction can help us move forward.
