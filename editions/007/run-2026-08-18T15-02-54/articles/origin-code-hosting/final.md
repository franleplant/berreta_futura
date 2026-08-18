---
source_ids:
- origin-code-hosting-807cadab
content_mode: article
label: ARTICLE
---

Cursor can now host your code. Origin begins rolling out today in early beta on all paid plans: repos, pull requests, code browsing, and GitHub sync. Agent-native features ship soon. Your GitHub repos can sit alongside the ones we host, synced in real time, with GitHub still the source of truth for anything started there. Every repo has pull requests, and on synced repos comments move both ways. Your code, PRs, and agents are now in the same place.

## Repos

The new **Codebase** tab is home for Origin repos. Click **+New**, name the repo, and a page shows you how to install the CLI and clone or push. Name your codebase when you create your first repo; that name becomes part of every repo's URL: cursor.com/codebase/`acme-corp`.

## Your GitHub repos

Connect GitHub, pick your org, select what to sync. You choose what gets synced and can disconnect a repo at any time. Anyone with read or write access to a synced repo can view it in Cursor. Synced repos update in real time: browse, search, and pull from the copy in Origin, while pushes keep going to GitHub. Icons tell you which repos we host and which came from GitHub.

## Pull requests

Open one to see the timeline, commits, checks, and files changed. Review the diff, comment, merge. On synced repos, comment in Cursor and it posts to GitHub; react or reply on GitHub and it shows up in Cursor within seconds. A review assigned to you on GitHub can be reviewed and merged from Cursor.

## Agents and apps

Ask Cursor about the code you're browsing. It can answer, make changes, update PRs, or push a branch. We're building an app ecosystem: Vercel, Depot, and Buildkite are already available. Connect Vercel from a repo's **Apps** tab and every PR gets a preview deployment; merge and it ships to production. Depot and Buildkite both run your existing GitHub Actions workflows, and Buildkite also runs its native pipelines.

Every repo has settings for sync status, access, and connected apps.

Early beta today for all paid plan users, except enterprise orgs whose admins opt out. Name your codebase and create your first repo.
