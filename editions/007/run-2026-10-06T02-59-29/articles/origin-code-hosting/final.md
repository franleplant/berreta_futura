---
source_ids:
- origin-code-hosting-807cadab
content_mode: article
label: ARTICLE
---

Cursor can now host your code. Origin, in early beta, starts rolling out today on all paid plans, except enterprise orgs whose admins opt out. It covers the essentials: repos, pull requests, code browsing, and GitHub sync. Your GitHub repos can sit beside the ones we host, pull requests sync both ways, and agents work in every repo. Agent-native features ship soon.

## Repos

Open the **Codebase** tab, click **+New**, and name the repo. A page then shows how to install the CLI and how to clone a repo or push a local project. Push, and the code is on Origin.

The name you give your codebase when you create your first repo goes into every repo's URL: cursor.com/codebase/`acme-corp`.

## GitHub repos

Connect GitHub, pick your org, and select the repos to sync. You choose what syncs and can disconnect a repo at any time. Anyone with read or write access to a synced repo can view it in Cursor too.

Synced repos update in real time. You browse, search, and pull from the Origin copy, but pushes still go to GitHub, which stays the source of truth for anything started there. An icon beside each repo name tells you whether Cursor hosts it or it came from GitHub.

## Pull requests

Every repo has pull requests: timeline, commits, checks, and files changed. Review the diff, comment, and merge.

On synced repos they sync both ways. A comment in Cursor posts to GitHub; a reaction or reply on GitHub shows up in Cursor within seconds. A review assigned to you on GitHub can be done and merged from Cursor.

## Agents

Code, PRs, and agents now live in one place. Ask Cursor about the code you're browsing. It can answer, make changes, update PRs, or push a branch.

## Apps

We're building an app ecosystem so your whole stack works with Origin. Vercel, Depot, and Buildkite integrations are already available, with more coming soon.

Connect Vercel from a repo's **Apps** tab and every PR gets a preview deployment for testing and comments; merge, and it ships to production. For CI, Depot and Buildkite both run your existing GitHub Actions workflows, and Buildkite also runs its native pipelines.

## Settings

Each repo's settings show GitHub sync status, who has access, and which apps are connected.

Learn more in our [docs](https://cursor.com/docs/origin) or [get started](https://cursor.com/codebase).
