# Repo, publishing, site, and speed: plan index (2026-10-04)

Plans still to do (02, downloads on GitHub Releases, landed 2026-10-05 in
34219f0a; 01, the git history cleanup, ran on 2026-10-05: art rounds
and art-directions/experiments stripped from history, pack 3.12 GiB to
645 MiB, main force-pushed as 8bdd728; every commit hash before it changed). Each is executable on its own once the ones
it depends on have landed; each ends with its own verification.

| # | Plan | Depends on | Size |
|---|------|------------|------|
| 03 | [Site design refresh](03-site-design-refresh.md) | 02 (download buttons point at the final links) | M |
| 04 | [Faster deploys](04-faster-deploys.md) | 03 (design churn changes every asset once; measure after it) | S |
| 05 | [Pipeline performance](05-pipeline-performance.md) | none (audited 2026-10-04 from 3ebf70a; render 18.7 s to 7.7 s measured on a prototype) | M, a ranked menu of independent S items |

Rules that apply to all of them:
- Several agents share this repo. A plan that rewrites history (01) or moves
  branches needs every agent stopped first; the rest land as ordinary
  fast-forward commits on `main` from a scratch worktree.
- Deterministic, measured steps before model calls (AGENTS.md). Every plan
  states its before/after numbers.
- Releases run from the laptop (deploy/web/README.md); no CI.
