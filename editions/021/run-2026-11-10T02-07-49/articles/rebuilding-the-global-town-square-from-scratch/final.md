---
source_ids:
- rebuilding-the-global-town-square-from-scratch-37909cd9
content_mode: article
label: ARTICLE
---

Open a profile on X.com over a slow connection. On the old web app, the first post arrived after more than 22 seconds of splash screen. On the new one, it shows up in 2.7. The new app replaces three servers, one each for people, search crawlers, and link previews, with one. It already serves logged-out X.com and the pages search engines crawl. Signed-in X.com is moving over one country at a time. Five engineers, working with AI coding agents, built the first version in under six months.

### Three servers, one URL

Since 2019, x.com has run on rweb, a client-side React app that grew out of Twitter Lite. Its Node.js server sent an HTML shell, and the browser then fetched data from our APIs. Two more servers grew beside it: rweb SSR rendered pages for search crawlers, and Jetfuel SSR rendered the logged-out pages search engines index.

One URL has three readers. A person wants the profile and its posts quickly. A crawler wants complete HTML, structured data, every language version, and the right status code. A link-preview bot wants a title, a description, and an image.

x.com's data is a graph, and the browser discovers it only after downloading and running the code that asks for it. On rweb, a logged-out visitor waited for the shell, then the JavaScript, then the GraphQL request, then the render. On a slow connection, each step is another round trip.

Three problems only showed up over years:

- **Three servers drift.** An SEO fix could need to land in three codebases.
- **Logged-out visitors got the slowest path.** Crawlers got finished HTML. People got a shell. The bots got the better deal.
- **The stack aged unevenly.** Redux with Relay, styled components through React Native for Web, Flow, and separate modern and legacy bundles. Each choice made sense when it was made. Together they were death by a thousand cuts.

### The decision

We could improve rweb in place, but that kept three servers and would have needed a fourth rendering path. We could swap the toolchain for Vite, TypeScript, and Fastify, but the architecture that caused the problems would remain. We chose a new app that serves every audience from one server, with traffic moving to it gradually while rweb serves everyone else.

To "never rewrite from scratch," our answer is that rweb kept shipping, traffic moved gradually, and the old servers served as specifications. With agents doing much of the implementation, the rewrite took months. To "why not just upgrade Webpack," faster builds wouldn't give a slow-connection visitor server-rendered HTML, and they wouldn't turn three servers into one.

### One server, three answers

**People get streaming HTML.** The shell goes out first, and each part streams in as its data arrives. Each GraphQL response travels in the page once, and the browser replays it into its Relay store instead of asking the API again.

**Verified crawlers get complete documents,** with every Suspense boundary resolved and no client bundle. We decide this from our edge's verification of the crawler's IP address, not the User-Agent. A header check would buffer Lighthouse along with real crawlers, and it would let anyone request the expensive path by changing a header.

**Link-preview bots get only what they read.** The server runs data loading and head tags and skips the body. An unverified crawler, including one that claims to be a search engine, gets what a logged-out visitor gets.

Links preload a route's code and data on hover or focus. A post preloads when the pointer rests on it for 100 milliseconds. rweb still has one advantage: its large client cache often made moving between screens feel instant. Preloading is how we're closing that gap.

### How agents fit

The engineers set the architecture, decided what to build, and reviewed every change. Agents ported behavior from the old servers, converted pages, wrote tests, and fixed what CI and reviewers flagged. Three things made their output trustworthy:

- **Shared instructions** in one `AGENTS.md` at the repository root.
- **More than 25 skills** in the repository for recurring workflows, from commits to Relay.
- **Guardrails on every commit:** custom oxlint plugins, including an "anti-slop" plugin that rejects chained type assertions, parameters typed as `unknown`, and conditional spreads of empty objects, plus pre-commit and pre-push hooks.

The old servers were working specifications. An agent could read how one handled a page, port it, and pin it with a test a reviewer could check against the original. For the engineers, the job shifted toward deciding what the system should do and checking in a real browser that it does.

### Moving the traffic

Crawlers went first, because search engines notice everything. A parity script requests the same path from two servers as a verified Googlebot and compares status, redirects, title, description, canonical URL, robots tags, card tags, language alternates, and structured-data types. We retired Jetfuel SSR on August 1, 2026, and shut down rweb SSR in early September; removing its deploy and build deleted almost 36,000 lines from rweb.

For people, our edge picks the server per request by path and by who's asking. The app's routes are published to the edge on every deploy, and unknown paths go to rweb. A feature switch decides who gets the new app, and anyone taken out goes straight back to rweb. Signed-in pages are tested on lite.x.com first. In the first country, signed-in people are split into an experiment between the two apps.

### Results

On November 3, 2026, signed in to the same account, throttled to Lighthouse's Slow 4G profile with no CPU slowdown and an empty cache, median of three runs:

- **New app:** page at 2.4 seconds, first post at 2.7.
- **rweb:** splash at 1.0 seconds, first post at 23.9.

This is a lab recording, so treat it as an illustration; real devices and networks will vary. The shape of the gap comes from the architecture: the new app sends content in the first response.

We also halved rweb's logged-out fleet from 1,400 to 700 instances per data center, and rweb SSR's from 2,400 to 1,200 before shutting it down.

### The two apps today

On November 3, with fresh headless Chromium, seven alternating loads per page, and a slow profile that also slowed the CPU four times, we measured time to first post. First contentful paint alone would flatter rweb, whose first paint is the splash screen.

- **Signed in, slow:** rweb took about 22 to 25 seconds on every page. The new app showed a post in 1.7 seconds and a profile in 3.0, 12.8 and 8.2 times faster.
- **Home gains the least.** The new app renders it only in the browser, so it waits for JavaScript in both apps: 14.1 seconds against 24.6. Home is where the new app has the most left to gain.
- **First byte is slower,** 430 to 560 ms against under 300 ms for rweb, because the server fetches and renders before it answers.
- **JavaScript before the first post:** rweb downloaded 3.0 to 3.6 MB; the new app downloaded none on a profile or post, and 1.9 MB on Home.

These are lab numbers from one laptop, and real devices and networks will vary.

### What we learned

The old servers were the best specification we had. Moving gradually is what made a rewrite safe. Lab numbers need field numbers next to them; the app also reports Core Web Vitals from real visits.

Signed-in x.com is rolling out one country at a time. When it completes, rweb retires. Twitter Lite set out in 2017 to be the best way to use Twitter on a slow, unreliable, or expensive connection, and that's still the goal.
