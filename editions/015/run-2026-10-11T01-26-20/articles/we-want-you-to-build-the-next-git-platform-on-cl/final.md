---
source_ids:
- we-want-you-to-build-the-next-git-platform-on-cl-37a106d7
content_mode: article
label: ARTICLE
---

GitHub was built for a world where humans write code and collaborate through branches, commits, issues, and pull requests. The next generation of software is going to be built by agents, and we want you to help us answer what the Git platform for that world looks like by building it. Artifacts, our versioned filesystem that speaks Git and can scale to millions of repositories, is now in open beta. It provides the foundation; you build the layer above it, on Workers. Submissions are open until October 14, 2026. We'll fly the top three teams to Cloudflare Connect in San Francisco, and first place gets $25,000 in Cloudflare credits.

## The question

Agents are already writing more code than ever: fixing bugs, building features, writing tests, reviewing changes, updating dependencies. Picture hundreds or thousands of them on one codebase at the same time. How do they know what the others are working on? What happens when their changes conflict? How do you review everything they produce? How do you keep track of not just what changed, but *why*?

## What Artifacts gives you

Repositories that can be created and forked programmatically, versioned storage for code and agent context, and the Git operations agents already know. The aim is a repository for every agent, session, task, or user. Vibe-coding platforms already use it to store their users' projects; developers use it to persist the code and context of agent sessions, or to give several agents isolated repositories from one starting point and compare or merge the results later.

New since launch:

- **Workers Builds.** A push to an Artifacts repository builds the project and, for the production branch, deploys the Worker. Other branches create or update Workers Previews.
- **Workers binding.** A Worker can create or fork repos, inspect files and commits, and issue repo-scoped Git tokens. When a task arrives, it can fork the project, read its `AGENTS.md`, and hand the agent a repository to work in.
- **Event subscriptions.** Artifacts publishes an event when a repository is created, imported, forked, deleted, pushed to, cloned, or fetched. You decide what follows: run CI, start a review agent, deploy.
- **Data jurisdiction.** Set U.S. or EU on a namespace, and every repository in it follows that restriction.
- **Metrics.** Operations, pulls, pushes, errors, and error rate per repository, in the dashboard or by query.
- **Pricing.** Based on repository operations and data stored. Billing begins October 15, 2026.

## The competition

We aren't looking for GitHub as it exists today with agents added on top. At a minimum, we want to see multiple agents working on changes concurrently. Beyond that, get creative: rethink repositories, branches, pull requests, worktrees, review, and merge conflicts, or find new ways to preserve agent context, compare many changes at once, and decide which one ships.

Submit a 5-10 minute video showing what you built and how it works, a link to the source under a permissive license (MIT, Apache, BSD), and instructions for running it. Deadline: October 14, 2026.

We'll select the top three projects and fly up to two members of each team to Cloudflare Connect in San Francisco to show their work. The first-place team also receives $25,000 in Cloudflare credits and invitations to the VIP speaker dinner on Monday night.

Artifacts is available in open beta to customers on the Workers Paid plan.
