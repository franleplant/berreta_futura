---
source_ids:
- the-world-hasn-t-figured-out-yet-that-you-can-li-b6d50c96
content_mode: article
label: ARTICLE
---

Nix is a terrible programming language, and I've been certain of that for almost 13 years. It should still be your primary choice for all your software projects. One Nix expression can define the toolchain for your laptop, your CI/CD, and your agents' sandboxes; it can build your Docker images and compose your operating system. Its key primitive, the overlay, lets you patch any software at any level, down to the Linux kernel. The learning cliff took me a couple of years because there was no AI back then. Now you can just prompt for outcomes.

## One source of truth

The term Nix is overloaded: it can be a package manager, a build system, or an operating system. When someone says they use Nix, ask them how.

I keep coming across clients whose laptops drift from their CI/CD. Ephemeral sandboxes for agents are heading toward triplicating that drift. This is utter madness, and it is not needed. With devenv.sh, one stanza provides Rust, Postgres, and prek for agent backpressure, and it just works across all operating systems. Mise isn't good enough. It does one thing, and does it well, but it doesn't enable your agents to truly fly.

The same expression can build performant Docker images, and there's no reason those images can't be the binaries you run in production.

## The operating system under test

On Debian or Ubuntu, giving an agent `sudo` would scare you. I develop on NixOS and explicitly prompt my agents to use `sudo` as part of my loop engineering. It is safe because NixOS is designed to make it nearly impossible to break a machine, and if it does break, you can instantly roll back the change.

Others run loops that build the application, perhaps Postgres, but rarely anything more. I put the entire system under test, and the system under test is the operating system. NixOS has a built-in testing framework, `runNixOSTest`. You can spin up a cluster, assert the network rules between machines, check which iptables rules forward or drop, and test your application against that environment before you deploy it.

Bare metal used to be complicated and a mess. That is no longer true now that we have Nix. Ditching hyperscalers like AWS for a NixOS fleet on bare metal is one of the most galaxy-brain moves you can make, because business margins are going to get compressed by AI. You'll need to find an older, more experienced sysadmin, but once the right patterns are in place, one or two of them can operate with the leverage of a team of 50 "cloud certified" monkeys.

## The overlay

Say there's a critical OpenSSL vulnerability. How long would it take you to find every OpenSSL version in your organization and patch it, including the third-party software linked against it? With Nix, a couple of lines:

```
{ pkgs, ... }: {

nixpkgs.overlays = [
  (final: prev: {
    openssl = prev.openssl.overrideAttrs (old: {
    version = "3.0.7";
    src = prev.fetchurl {
      url = "https://www.openssl.org/source/openssl-3.0.7.tar.gz";
      hash = "sha256-...";
    };
  }
```

That is an overlay. When you find a bug in open source, you ask someone to take your pull request, or you fork it and then work out how to build the fork and where to host the artifact. With Nix, every change is just an overlay. All software becomes infinitely customizable at all levels, and you can patch anything by asking an agent to customize it. These LLMs know Nix very well because the labs themselves are using it on their journey toward reaching RSI.

My demo, ghuntley/nix-demo on GitHub, shows a pattern I've used for years: it removes force-push from Git itself, so my agents can't use it, then uses that one patched Git in devenv, a NixOS VM test, and a Docker image.

## The limits

I also use Bazel and Buck2 alongside Nix. Nix has a lot of problems; the way the derivation store works hurts incremental caching, which Bazel and Buck2 excel at. Still, the best bang for the buck right now is Nix. If you are building security-critical systems, burn tokens with a cyber model to find every vulnerability in your third-party dependencies, and fix them with overlays.
