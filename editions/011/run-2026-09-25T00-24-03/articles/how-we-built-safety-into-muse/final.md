---
source_ids:
- how-we-built-safety-into-muse-512c3f7f
content_mode: article
label: ARTICLE
---

Today we launched Muse, our personal agent. It lives in your own cloud computer, reads your mail and calendar, and acts for you. We designed the system to assume the agent may be under attack and to limit the damage: the harness runs in its own isolated cell, it doesn't see real credentials, and every interaction with the outside world runs through a Sentinel the agent can't override. Muse can and will still make mistakes, but we expect they'll be much less frequent and cause much less damage. Our bug bounty is now open to anyone, with awards up to $300,000, including up to $130,000 for successful prompt injection that affects one user.

## Two domains on one box

Each user gets a dedicated Linux VM with a browser. It is the system of record for everything you put in Muse; limited data leaves it for inference and telemetry.

Inside, the Hatch daemon (the core harness; Hatch is our internal name for Muse), your workspace, and every tool Muse runs sit in a `systemd-nspawn` container. Root in the cell maps to an unprivileged host user. The cell has its own root filesystem, filtered system calls (no `io_uring`), and limited capabilities (no `CAP_SYS_PTRACE`, no `CAP_NET_ADMIN`).

The cell is expected to process untrusted data, so the sensitive services live outside it:

- `hatch-safety` runs independent models and classifiers over inference. Attackers can't disable them from inside.
- `privsep` workers run connector code with tightly scoped privileges.
- `hatch-authd` stores credentials in your VM, not in centralized Meta infrastructure, and gives the agent surrogates.
- Sentinel is the sole permission authority for connector actions and network egress.

They talk over Unix domain sockets with `SO_PEERCRED` and peer ACLs: kernel-authenticated, with no secrets to steal.

The right mental model is two isolated security domains on one box, not an LLM powered agent with root.

## Sentinel

Muse proposes actions; only Sentinel grants permission. For a connector call, Sentinel checks the policy the user set and answers allow, deny, or ask. For network egress, it inspects the hostname, resolved and final IP, port, protocol, method, path, and decoded request, and stops public hostnames that resolve to private infrastructure.

Code in the cell only ever holds a surrogate token. After authorizing a request, Sentinel swaps in the real credential at the network boundary. The agent never sees real tokens, so coaxing it to reveal them is futile.

To keep approvals rare, we track data flow in the kernel, which we call "tainted egress." A process becomes tainted when it reads user data. Clean requests that fit a narrow auto-allow policy and pass URL checks go through; tainted or unverifiable ones fall back to normal approval. This uses eBPF `cgroup` programs and eBPF programs on Linux Security Module hooks we added.

## Asking the human

When the answer is ask, execution stops. Sentinel sends the request straight to the client, outside your conversation with Muse, and your reply goes back to Sentinel. Grants are strict capabilities bound to a connector or destination and a use case: one-time, session, task, time-bounded, or perpetual.

Read-only, previously allowed, or demonstrably low-risk actions proceed without interruption. We expect to tune this balance as we gain experience with real users.

## Least privilege

The model doesn't need API keys, so it doesn't see them. The same rule runs through the rest:

- Where the service supports it, read and write access are separate, with finer control than OAuth scopes. With Gmail read access, you can still remove access to Gmail settings.
- Built-in connector CLIs in the cell only parse arguments and pass file descriptors over a socket. A sandboxed worker outside does the work, with an explicit credential allowlist; a calendar worker can't ask for an email credential by changing a parameter.
- Browser CDP access sits in a broker outside the cell.
- The email connector filters out one-time codes, password reset links, and login magic links, with deterministic filters and a classifier, so connecting email doesn't let anyone use Muse to represent you on other sites.

## Defense in depth

Prompt injection has been an obsession for us. Simon Willison's "lethal trifecta" names its preconditions: access to private data, exposure to untrusted content, and the ability to communicate externally. Our layers:

- The model is trained to resist injection. Muse Spark 1.3 is close to SOTA on this capability.
- The harness labels external data as untrusted input.
- An ensemble of classifiers, trained independently of the model, scans all external data entering context.
- Actions that move data out of the VM need human approval.

Beneath the agent, deterministic boundaries still apply even if Muse is persuaded to behave badly.

## Browser and purchases

The browser is a real Chromium behind a virtualization layer; you can watch and take over at any time. Logins go through a client UI straight to `authd` and are injected at the point of need. A browser sub-agent sees an accessibility tree, not the raw DOM, can't run JavaScript, and is paused while you drive or while credentials fill a form. Classifiers watch for unrelated personal data leaving, injection in the DOM, images, or downloaded files, and high-risk form submissions. Known harmful sites from Meta's existing lists are blocked.

Every purchase needs approval with the exact details. For new merchants, the wallet (Stripe Link at launch, Shop Pay coming soon) issues a single-use card tied to one merchant, one amount, and a limited time. Even if stolen, it would not be particularly useful to the attacker.

## Privacy, now and later

Your files, Muse's memory about you, and your credentials stay in your VM, backed up continuously, and you can inspect, edit, and download them. Today, operational policies restrict access by Meta personnel. They do not prevent Meta from accessing data when necessary to support, secure, or operate the service.

Muse Confidential VM, planned for later this year, is intended to cryptographically and verifiably prevent Meta from accessing data in your VM. A small group of trusted testers uses it now, and external auditors have begun reviewing the design and source.

Your conversations and VM data don't go to Meta ad systems, but Muse's browsing appears as your activity and can indirectly influence the ads you see. Trajectories are sanitized to remove key personally identifiable information and used for training unless you opt out in settings.

## Conclusion

Muse isn't immune to attack. Prompt injection remains an open problem, and Muse will sometimes make mistakes. We designed the system to bound the impact and keep you in control without overwhelming you. If you like breaking things, the bug bounty is open today. If you're a privacy expert, reach out to help with Muse Confidential VM.
