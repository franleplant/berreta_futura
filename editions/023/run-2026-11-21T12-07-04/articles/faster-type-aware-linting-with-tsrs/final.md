---
source_ids:
- faster-type-aware-linting-with-tsrs-b54b2be6
content_mode: article
label: ARTICLE
---

We're adding `tsrs`, the Rust port of TypeScript, as an alternative to `tsgolint` for type-aware linting in Oxlint. It's a drop-in replacement that works through Oxlint's existing CLI and configuration and implements all 61 tsgolint rules. When it typechecks and lints in a single pass, it runs up to 7x faster with up to 75% less memory. Teams at Cloudflare, Owner.com and OpenAI already use it.

## What it is

tsrs is the Rust port of TypeScript that Cloudflare and VoidZero announced in October, written by Max Schwenk and shipped as the `tsrs` npm package. Our goal is to make Oxlint the best possible linter for developers and agents. A faster linter shortens feedback loops in editors, CI, and agent workflows.

## Performance

Against tsgolint v7.0.2007, tsrs is up to 5× as fast and uses around 70% less memory. Against typescript-eslint, it is up to 98× faster and uses up to 82% less peak memory.

Inside Oxlint, typechecking and type-aware linting run through one TypeScript analysis, so the same work isn't done twice. The largest speedup then grows to 7×, with memory reductions of up to 75%. Against typescript-eslint and `tsc` run separately, Oxlint with tsrs is up to 122× faster and uses up to 82% less peak memory.

Fast mode is on by default. It adapts checker counts, groups related work, and enables additional caches and memory optimizations.

## Compatibility

The goal is to keep the same configuration options, diagnostics, fixes, and suggestions, so existing projects can switch with minimal effort.

## Try it

With Vite+:

```sh
$ vp upgrade # since v1.7.0
$ vp check # or vp lint
```

With Oxlint directly, upgrade Oxlint and `tsrs` to their latest versions. Oxlint then uses `tsrs` automatically for type-aware linting and typechecking.

```sh
$ pnpm i -D oxlint tsrs
$ pnpx oxlint --type-aware
```

To get typechecking diagnostics alongside lint results:

```sh
$ pnpx oxlint --type-aware --type-check
```

If `options.typeAware` already enables type-aware linting, your usual lint command keeps working.

## Feedback and what's next

Report any differences in output, fixes, runtime, or memory. Those reports help us work toward a more stable release.

With both tools written in Rust, we have more room to explore deeper integration, cut duplicated work, and improve speed and memory across linting and typechecking. We'll keep following upstream TypeScript and `tsgolint` and closing gaps. The goal, for developers and agents alike, is to make thorough checks fast enough to run after every change.
