---
source_ids:
- pooling-openai-subscriptions-and-bypassing-regio-2154fb99
content_mode: article
label: ARTICLE
---

We're in a cost of compute crisis, and OpenAI doesn't have enough inferencing capacity. I've lost time babysitting agents through "model is at capacity" errors, and I've noticed they come when Europe wakes up. So I'm releasing geoclass, an experimental prototype that routes requests to inferencing regions elsewhere in the world. It composes with two tools I wrote last month: Underclass, which pools ChatGPT subscriptions, and Preflight, which scrubs secrets from requests. I don't know yet if it will work.

## The capacity problem

The cost of CPU and memory is through the roof, and there aren't enough GPUs in the world. Even Tibo admits publicly that OpenAI is having compute issues: "It's the compute that is cooked."

I wonder whether the constraints are region-based. Last year, before this crunch, even Anthropic models ran noticeably faster in Australia because everyone in America was sleeping. I do my open-source work on bare-metal machines in Germany. When Europe wakes up, performance plummets and I get walls of capacity errors. This morning they cost me time on a strict deadline before my conference talk. You can complain online all you want, but we're software engineers. We can solve these problems.

## Underclass

Underclass pools many ChatGPT subscriptions behind one proxy. It automatically claims resets and handles the prompt cache key correctly, so usage isn't wasted. It's a month old, and I consider it stable. I use it with six ChatGPT 500 accounts; there's no real upper limit. It's on GitHub and available as a Nix Flake.

## Preflight

Preflight is a local proxy that scans requests and attachments for secrets and redacts them before they reach the model. Run one instance of each and point Underclass at Preflight, and sensitive material never reaches the inference providers.

## Geoclass

Set up a Tailscale network, deploy virtual machines around the world, and tag them. Geoclass finds the machines by that tag. Point Underclass at Geoclass, and the rest just works (in theory!). It retries OpenAI capacity errors in another region and keeps prompt caches warm.

The three are separate pieces of software. Use all of them, none, or any combination.

I don't know yet if geoclass will solve my inferencing woes. But OpenAI's performance in Europe has been miserable for the last 30 days, and there's no way in hell I'm going to sit here and stew. If it works for you, let me know.
