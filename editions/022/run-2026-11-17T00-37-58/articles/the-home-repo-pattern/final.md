---
source_ids:
- the-home-repo-pattern-32e9cfe4
content_mode: article
label: ARTICLE
---

A Home Repo is one repository that holds your skills, your AGENTS.md and your shared docs. You run your agent there, and its AGENTS.md points at each of your other repos, so the agent can open or clone them as it needs to. The code stays where it is, and each repo keeps its history, remote and issue tracker. The Home Repo holds a map of the other repos, not their code.

## The problem

An agent started in one repo sees only that repo. Each repo ends up with its own copy of the skills and the agent setup, and a feature that crosses repos gets planned without the whole overview. A Home Repo gives you one place for steering files and tooling, one place to run all your agents, and sweeping changes across several repos from a single session.

## What goes where

The Home Repo holds skills you use across repos, AGENTS.md with its pointers, steering files, and shared docs such as coding standards, a glossary, and decisions that affect the whole system. Coding standards are the first doc worth sharing: one universal set transfers across projects.

Each repo keeps anything true of it alone: its own AGENTS.md, its build and test commands, its repo-specific docs.

Why not `~/.claude/skills`? The ideal end state is that everyone uses the same skills, kept in the project. A user folder is the stopgap. A Home Repo is a project: its skills are versioned with git, and a team can share it.

Put the pointers in whichever file your harness loads at session start. Claude Code loads CLAUDE.md.

## Pointers

One line per repo, with a hint where a repo needs one:

```markdown
## Other Repos

Storefront (Next.js app): ~/repos/acme/storefront. Clone from git@github.com:acme/storefront.git if missing.
Payments API: ~/repos/acme/payments-api. Read its AGENTS.md before changing it.
AI Hero: ~/repos/ai/ai-hero (git pull to view latest, likely out of date)
```

If the repo is already at the pointer's path, the agent works there. If it isn't, the agent clones it there. Some setups clone the repos inside the Home Repo and gitignore them instead.

## Setting one up

A setup prompt goes into a new session started in the folder that holds your repos. The agent finds every repo and every skill, AGENTS.md, CLAUDE.md and agent doc itself. It sorts each item as shared, duplicate, repo-specific or installed. It grills you about the decisions in rounds, each question numbered with a recommended answer, and changes nothing until you approve its plan. Shared items and the newest copy of each duplicate move to the Home Repo; repo-specific items stay in their repo; installed ones stay installed. Removals in child repos happen on a new local branch. Secrets stay unread, and pushing is your call.

## Working across repos

Sessions start in the Home Repo, which is also the place to grill a feature that crosses repos. Each repo is cloned once, and each feature gets a worktree inside that clone, so several agents can work in one repo at the same time. The agent can reach every repo's issue tracker and file each issue where it fits. For a team, the Home Repo is the thing you share.

## Scale and alternatives

About 20 repos works fine. At around 400, one pointer per repo is too many decisions for the agent: point at one file per area of the business instead, and list that area's repos in its file. At thousands of repos, a skills marketplace makes more sense.

Submodules are fine at 5-10 repos; plain pointers do the same job without them. A monorepo is a good fit when you can have one. A Home Repo replaces it when you can't, for example when you mix public and private repos, or when your team won't adopt a monorepo.

You need no CLI to start. Later, the Home Repo is a good place for tooling. In CI, put it in the sandbox, and it clones the other repos as it needs them.
