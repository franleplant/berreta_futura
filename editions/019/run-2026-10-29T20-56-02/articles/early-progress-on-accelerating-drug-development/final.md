---
source_ids:
- early-progress-on-accelerating-drug-development-dcad83d8
content_mode: article
label: ARTICLE
---

Over the past several months, we've worked with six organizations developing new medicines, and begun drug discovery of our own. Developing a drug involves many varied tasks, and there is no single problem to solve; the bottlenecks are distributed all throughout the process. So we're putting Claude into real drug programs, across many diseases and stages, to learn where it helps and where it must improve. Early results are promising, but nearly all of it is still preclinical. We plan to scale this work up substantially.

## Why real programs

Proposing initial designs for molecules is only one task. A drug also needs a target, a molecule with the right properties, reliable manufacturing at scale, regulatory filings, and trials. The work serves three ends: it shows us Claude's strengths and limits across these tasks (we've already prioritized specific model improvements from it), it offers case studies to the life sciences community, and, if the trajectories continue, it may yield effective medicines for food allergies, rare childhood diseases, and several cancers.

## Case studies

**Generate Biomedicines: modality engineering.** Generate wants CAR T-cell therapy, historically used against blood cancers, to treat solid tumors too, by shortening one part of its genetic instructions. Six scientists used Claude Code to propose designs. One was about 70% shorter and, in lab tests, more effective: immune cells made roughly 10 times as many receptors, killed tumor cells more efficiently, and stayed active longer.

**Divergence Labs: hit generation.** Divergence is developing food-allergy drugs that would detach IgE from immune cells entirely, which needs a two-armed design. Claude turned their goals into a design plan, then, largely autonomously, generated roughly 35,000 antibody designs in about a month. Early tests found three that bind IgE and 20 that dislodge it; three of those 20 appeared to dislodge it more than the standard medication. Next is a drug combining the two arms.

**BigHat Biosciences: lead optimization.** Working with BigHat's scientists and an Anthropic researcher, Claude proposed changes to two antibody fragments, and BigHat's lab made and tested about 1,010 variants in about 10 weeks. When the team suspected the standard stability and clumping metrics were misleading, Claude and the researcher reanalyzed the raw data and proposed new metrics and a protocol change; BigHat refined and ran it, and the main predictions held. The best versions bound more than 10x more tightly; the cancer-targeting lead stayed in solution 18°C higher, and the other clumped more than 100x more slowly.

**Enveda: manufacturing and filings.** Enveda's manufacturing chemists spent up to 75% of their time on paperwork. Across 1,061 pages, Claude caught all 11 issues human reviewers had spotted and flagged seven they'd missed, cutting review time by 89%, from over 25 hours to less than three. Claude also drafted two regulatory documents: one in four hours instead of about three months; in the other, human review found one minor error.

**The Column Group: company creation.** Investors have favored safer, validated ideas over riskier ones that could help more patients. TCG is establishing Pleiades, a company that will use Claude to run more, and more complex, programs than a small team usually could. Its first Claude skill, for judging whether drug targets are worth pursuing, has been evaluated on 45 target-disease pairs.

**Bristol Myers Squibb.** More recently, BMS has been using Claude to assess trial plans for an early-stage drug and estimate their chance of success. We plan to expand this work in 2027.

**Our own program.** We've acquired Mithril Medicine, a one-person company working on two rare forms of muscular dystrophy. Its founder, Cody Tranbarger, used Claude to coordinate 11 external labs and much of the company's operations, taking one possible treatment from idea to promising results in mice in less than 18 months. If his candidates continue to hold up, we expect a drug to be ready for human trials as soon as late 2028.

## Next

All of this is early and mostly preclinical. We plan to extend Claude into clinical trials as these programs advance and as we partner with organizations already at that stage. Beyond this research, we've released Claude Science, credits for life scientists, a Life Sciences Verification Program with more permissive safeguards for trusted organizations, and an open call for guest investigators.
