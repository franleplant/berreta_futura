# What is this page mostly about?

The text below the line is one captured web page, queued for a printed
magazine read by software engineers who build with AI. Name the one subject
the page is mostly about, by what most of its words are spent on:

- `model_launch`: a company or team releasing a new AI model, with its
  benchmarks, price, or availability.
- `company_news`: a company or lab reporting news about itself: an
  acquisition, a donation or a project handed to a foundation, a partnership,
  a coalition, a funding round, a program, grant, or fellowship, an office, a
  hire, a policy commitment. A company arguing for an engineering practice,
  changing what its product requires, or setting deadlines for the developers
  on its platform is not company news.
- `product_release`: a product, tool, library, API, feature, or specification
  that people can start using or implementing now, including an open-source
  release, with what it does or how to use it; also a change to the rules,
  requirements, or deadlines of a product people use.
- `engineering`: how a team built, tested, debugged, scaled, sped up, secured,
  or cut the cost of a system that runs in production, including a person's
  own project; a postmortem; an architecture or design
  write-up; how a system works inside, including reverse engineering it or
  laying out the parts builders make it from, such as an agent's memory,
  tools, context, or harness, even when the page reports evaluations; a how-to; an argument for an
  engineering practice that shows the tools to adopt it; a method for checking
  or verifying real code that the page shows on a real system.
- `applied_research`: a technique the page shows a working engineer how to use
  in their own code, tests, agents, prompts, or evaluations today, with the
  steps, code, or tool to do it.
- `science`: work in a field outside software, such as biology, chemistry,
  medicine, drug discovery, physics, or materials, even when an AI model did
  the work, the post is about helping scientists or describes the software
  and agents built for them, or it argues how AI should do science.
- `distant_research`: a research result that a builder cannot put to work in
  their own systems now: a study of what models can learn to do, how they are
  trained, what happens inside them, or how they behave under evaluation, or
  a new scheme in cryptography, theory, or any other field of computing that
  is still a proposal. A research paper or lab study belongs here unless it
  hands the reader steps, code, or a tool they can use today.
- `standards_transition`: a long migration or standards change that vendors
  and standards bodies carry out on the reader's behalf.
- `essay`: an argument or reflection about software, systems, teams, agents,
  or AI and society.

How this magazine's editor sorted earlier pages:

- company_news: "OpenAI to acquire Pierre Computer Company, Inc.", "Donating
  agent skills to the Agentic AI Foundation", "Working with academic
  communities to build scientific understanding", "Towards securing the
  internet" (a coalition to patch one vulnerability)
- science: "How Claude designed protein binders against scorpion
  neurotoxins", "Early progress on accelerating drug development with
  Claude", "Teaching AI to build scientific models"
- distant_research: "Sparks of Weight-Space Programming", "The post-quantum
  future of web privacy", "Progress on provable inference for large language
  models", "Introducing AlphaProof Code", "An alignment assessment of the UK
  AISI cybertesting incident", "How AI agents shape experts' judgment calls"
- engineering: "Death to long-lived static credentials", "The components of
  agent memory"
- model_launch: every "Introducing <model>" release post

Answer with one JSON object and nothing else, no code fence:

{"subject": "one of the names above", "evidence": "the one sentence from the page that best shows the subject, copied character for character"}

---

