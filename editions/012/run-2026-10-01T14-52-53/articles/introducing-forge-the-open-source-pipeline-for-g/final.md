---
source_ids:
- introducing-forge-the-open-source-pipeline-for-g-2f7c2d78
content_mode: article
label: ARTICLE
---

Forge is an open source, pluggable pipeline for generating SDKs, CLIs, docs, and libraries, and anyone can deploy and run it for free. It's early in its life, but it already generates the output for the cf CLI, and over the next few months it will power Cloudflare's API documentation, SDKs, and much more. We built it because we needed it to treat agents as our customers. CLIs, SDKs, MCP servers, and good docs used to matter only for developer products. Now they're table stakes for every product.

## Our API outgrew our generators

Cloudflare's API has over 3,500 operations, served by hundreds of services written in Rust, Go, TypeScript, Python, and more. When a product team changes an API, they need a preview build of the Cloudflare-wide CLI, SDK, and docs before merging, and they need to know they haven't broken generation.

We tried several hosted products and relied on some in production. None solved this, and some shut down entirely. One team would merge a change that broke the pipeline; another would discover it at release time.

Forge runs in CI on each team's API repos. It lints every change, then generates installable preview builds of the CLI, docs, and SDKs with just your changes highlighted. It's the premise of Workers Previews, a full preview for every change, applied to SDK generation across hundreds of services and repositories.

## Generate anything, chain the outputs

Forge can take an OpenAPI spec and generate Cap'n Web, Cloudflare's RPC system that lets TypeScript call a remote API as if it were a local method. This opens the door to generating bindings from Workers to other APIs, since bindings in the Workers runtime are implemented as Workers that expose RPC methods. The same holds for TanStack Query bindings, Zod or Valibot schemas, MCP servers, or anything else that makes your API easier to consume.

Transformers can also be chained, so one target's output produces others. Other generators do this, producing the CLI and Terraform targets from the Go SDK. What's missing, and what Forge provides, is a way for the user to control the chain. Our cf CLI is written in TypeScript, which other generators don't generally chain from for CLIs. And why should a tool decide for you? Maybe you're a Python shop and want the CLI in Python.

The language matters because CLIs are different. They carry handwritten, local-only behavior that no API call backs, like cf dev and cf build, which call TypeScript APIs from packages like Vite. If your docs come purely from the OpenAPI spec, how do those commands get documented alongside the rest? We couldn't find a tool that does this, so we're building it into Forge.

Forge supports OpenAPI input today and is designed to allow AsyncAPI, GraphQL, Cap'n Proto, Protobuf, or other formats in the future.

## Change your API without breaking users

Our v4 API has been the one major version for 10 years. It appears we haven't launched new major versions, but by SemVer definitions we've made quite a few changes worthy of one, and several operations carry internal 'v2' or 'beta' tags that have long outlived that stage. A big v5 would leave many customers behind. So, with Forge releasing artifacts along the way, we're working on a versioning approach that allows new major versions without breaking old clients or SDKs.

More on our SDKs is coming very soon: TypeScript, Rust, Python, Go, PHP, and Terraform. Upgrading any Terraform provider comes with its own rigor, and we're going to put extra special care into that transition.

## Open to all

We believe building tools for APIs is a core part of the Internet, and you shouldn't need a SaaS product to do it. You should own your SDKs, CLIs, and docs. Forge is open source under the permissive Apache 2.0 license. We want people to join and contribute. Or not: you can run it on your own, for any purpose, with custom modifications, for free, in private.
