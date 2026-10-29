---
source_ids:
- working-with-academic-communities-to-build-scien-fe7d7660
content_mode: article
label: ARTICLE
---

We are announcing three new discoveries, produced by our models: a proof of the local smoothing conjecture in every dimension, which also resolves the Kakeya and Stein's restriction conjectures; a proof that the Exponential Time Hypothesis is false; and a rigorous existence proof of four-dimensional quantum field theories, including Quantum Chromodynamics. Each has been, or is being, formalized in Lean. We regard these manuscripts as raw research data, and we asked outside experts to shepherd each result. They advised three different ways of releasing them. We do not yet know which will be most useful.

## How we release

Raw data is not yet understanding. To turn one into the other, we asked external experts to act as shepherds. They advised:

- For mathematics, release the AI output and let researchers organize their own efforts.
- For computer science, form an external group to explain the result, and publish the AI output for anyone to examine.
- For physics, form an external group and defer to it on what gets released.

The collaborations follow four principles. They are transparent: no nondisclosure agreements, and members may discuss and publish freely. We seek no academic credit for what our models produced, and a steward is not thereby the discoverer. The groups receive recognition for the understanding and writeups they create. Participation is voluntary, unpaid, and independent; members don't speak for OpenAI, nor we for them.

Every approach has a cost. Collaborations let experts place the results in their field, but choosing the first shepherds shapes who gets involved first and creates an asymmetry of information. We welcome feedback on how to broaden participation.

## Local smoothing and the Kakeya conjecture

In 1991, Sogge conjectured that the most extreme focusing of waves must be short-lived: at a typical time, focusing is far smaller than at the worst. The conjecture implies the Kakeya conjecture and Stein's restriction conjecture. It was proved in two spatial dimensions in 2019, and Kakeya in three dimensions in 2025.

Our models produced a proof in every dimension, built on a novel auxiliary partial differential equation. We obtained it on October 18th, 2026, and formalized it in Lean the next day. On an expert's advice, we released the natural language writeup and the Lean proof on our public GitHub repository.

## The Exponential Time Hypothesis is false

The ETH is a longstanding conjecture about the complexity of Boolean satisfiability, a problem deeply related to P vs. NP. It has been widely believed and used in hundreds of papers to derive conditional hardness results. Our system proved it false on October 16th, 2026; the result was formalized in Lean on October 17th. The refutation reopens questions about how much faster these tasks could become. Finding such algorithms, and making them practical, will require significant further research.

Russell Impagliazzo and Ramamohan Paturi, two of the hypothesis's original proposers, and Ryan Williams, who has refuted strong versions of it, will lead the group that verifies and shepherds the work. At their request, all raw data is public, and OpenAI will fund a conference on its implications. The writeup and Lean proof are on our GitHub repository.

## Existence of quantum chromodynamics and completions of the Standard Model

This result is a mathematically rigorous existence proof of certain interacting quantum field theories with gauge fields and fermions in four dimensions, including QCD and the simplest grand unified completion of the Standard Model. It builds on Balaban's approach in constructive quantum field theory. As a subproblem, it proves the existence of pure Yang–Mills theory, part of a Clay Millennium Prize problem.

Our models produced the Yang–Mills proof on September 9th, 2026, and the QCD proof on September 18th. Given its length, we waited for the Lean formalization; Yang–Mills existence was formalized on October 16th. David Gross will lead a group with Michael Douglas, Arthur Jaffe, Igor Klebanov, and Nikita Nekrasov. The group has chosen to hold back the AI-produced artifacts and write the work up themselves.

We hope these results begin a transition in which quantum field theory becomes a mathematically rigorous field.

## Supporting scientists

These collaborations complement our $5 million contribution to a Simons Foundation initiative, which will fund workshops, conferences, and programs to help researchers understand and build on results produced by AI. We are committed to funding independent examination of these results, and we continue to invite feedback on how best to disclose them.
