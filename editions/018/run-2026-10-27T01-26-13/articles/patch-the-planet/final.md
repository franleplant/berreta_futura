---
source_ids:
- patch-the-planet-61eb7e33
content_mode: verbatim
label: VERBATIM
---

I don't know if you've seen this, but a CA just got popped. Their keys got leaked, which means the industry as a whole now has some pretty major problems. It was revealed two hours ago.

Now you're probably wondering why I'm writing up this blog post. It's simple. This is perhaps one of the easiest security patches I've ever done, and I've discovered a few new tricks. First, understand that fixing this with ease without Nix is almost impossible. Tens of millions of dollars (if not more) in productivity are being lost worldwide right now as everyone tries to patch their transitive dependencies.

Meanwhile, because I've used Nix, I can patch the planet, since the ideas behind the blog post below extend into security as well.

Because of Nix's single source of truth and the ability to patch this single source of truth, I'm able to issue a simple prompt like this:

> okay is my nixos for my fleet affected by [https://emudhra.we-have-a-problem.com/](https://emudhra.we-have-a-problem.com/?ref=ghuntley.com)?

With results in the following.


So the problem here is the transitive dependencies. It's easy to patch one thing, but the transitive dependencies are the problem, and this is where Nix shines: one fix fixes the transitive dependencies automatically.

One patch fixes the entire fleet and its transitive dependencies. Patch, commit, and autodeploy your fleet 🍻

## the new trick

Alright, I promised a new trick. Here's the trick.

> You can prompt an agent to update the AGENTS.MD to automatically back out these patches, let's say in five days from now, just by using the AGENTS.MD as a reminder 😎

So it was one simple prompt to identify if I was affected, which turned into a plan, which then automatically fixed it, and now, in a couple of days, it will reassess the situation, give time for the ecosystem and dust to settle, and then automatically back it out once all the upstream transitive dependencies have been resolved.

Cool, huh?

```
## Temporary reminder: eMudhra root blacklist (from 2026-10-22)

On or after 2026-10-22, check whether the `nixos-26.05` channel contains nixpkgs
commit `7816d39` (the backported `security/ca.nix` distrust of the eMudhra roots), e.g.
`nix eval --raw --refresh --impure --expr '(builtins.getFlake "github:NixOS/nixpkgs/nixos-26.05").rev'`
then `git merge-base --is-ancestor`. If it does not, check again two days later.
Once it does, back out the fleet-wide workaround: update the `nixpkgs` pin to include
it, delete `nix/domains/system/public-trust.nix` (contract `fleet-distrust-emudhra-roots`)
and its imports in `nix/domains/system/catalog.nix`,
`nix/domains/artifacts/guest/configuration.nix` and the `host-kexec` modules in
`flake.nix`, and remove the eMudhra paragraph from
`marshall/priv/hldd/12-configuration.md`. Then verify that the built host and guest
bundles still lack the four roots, and delete this section. Keep Marshall's
system-store TLS defaults (`runtime-postgres-system-trust`, `mail-smtp-system-trust`)
and the `rustls-webpki` update; they are not part of the workaround.
```

I can't stress this enough. If you build something, you own it, including all the dependencies you rely on. We're entering weird times where cyber offensive models will be continuously on the attack.

The game has changed. To defend, you need more inferencing capability than the attacker, and you also need to respond rapidly.

This is by far the easiest security patch I've ever done, and the best part is I won't carry this tech debt for long because an agent will automatically back it out in a couple of days.
