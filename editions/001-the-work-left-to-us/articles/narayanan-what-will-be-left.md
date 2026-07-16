---
source_id: src-narayanan-icml-2026-keynote
content_mode: faithful_synthesis
source_body_sha256: a8a2490509d9f2095ca0c39f544d97142f93a95bc79efcc1cc20ae1e3891421b
rights_status: private_reference
source_format: annotated_slides_transcript
---

## Amplification or replacement

AI inspires both excitement and anxiety because its systems can do more of the work we do today. I want to address that anxiety head on. How should we prepare for a future where AI becomes capable of doing more and more of our work? Our response depends on which of two narratives we accept. If AI will soon replace nearly everything humans do, the rational move may be to accumulate wealth before existing skills lose their value. If AI will instead amplify human potential, this is an unusually valuable time to build the skills, agency, taste, and judgment that complement it. Choosing the replacement story too early risks wasting the best period in which to learn how to use a powerful new tool.

[AI as Normal Technology](https://knightcolumbia.org/content/ai-as-normal-technology) is the intellectual framework for this argument. "Normal" does not mean mundane or unimportant: AI may be as transformative as the industrial revolution. It means that, absent a genuine discontinuity, its economic effects still arrive through recognizable social processes rather than directly from a capability benchmark.

The framework separates four stages. Methods and capabilities improve; products turn those capabilities into usable applications; people and organizations adopt those products; and, slowest of all, institutions and work adapt around them. Coding agents illustrate the sequence. Better models became usable products, developers learned practices more disciplined than casual "vibe coding," and organizations are only beginning to ask what software work should become. The last stage may take decades.

Electrification offers the historical analogy. Replacing a steam engine with an electric motor did not transform a factory. The larger gains came when factories were reorganized around distributed power and assembly lines, which also changed training, management, and labor law. The electric utility could not decide how every factory should operate. Likewise, AI companies cannot perform the organizational adaptation needed in every profession.

## Capability is not deployment

The gap between a model's benchmark performance and its practical usefulness is central. My research group studies reliability through consistency, robustness, calibration, and operational safety. A system advertised as 70 percent accurate may reliably solve a known 70 percent of tasks, or it may unpredictably fail 30 percent of the time on every task. Those are radically different deployment prospects, yet ordinary accuracy scores blur them.

Across recent frontier models, capability rose much faster than reliability. This matters because automation agents and collaboration agents need different properties. An automated agent operating in a high-stakes environment must behave consistently, recognize failure, and fail safely. A collaborator used for writing or exploration may benefit from variation and surprise. Treating a headless version of the same agent as an automation system ignores that distinction.

For now, general purpose, high stakes, and fully automated form an unstable triangle: systems can usually offer only two. Collaboration is therefore advancing faster than dependable automation. Model capability alone does not remove integration costs, legal liability, recovery procedures, or the need for human control.

## Why faster work does not imply fewer workers

Software engineering is an early test. Even if agents greatly accelerate coding, writing code was never the whole job. I divide the work into a decide-execute-deliver sandwich. Understanding requirements, choosing a specification, and planning occupy the decide layer. Coding and debugging form the execute layer. Integration, testing, maintenance, and accountability form the deliver layer. AI compresses the middle, but the outer layers remain and may expand as more code becomes possible.

The worker increasingly resembles a crane operator: the machine performs the heavy lifting, while the person directs it, understands its limits, and remains responsible for the result. The job is reconceived around operating and controlling the machine, not simply around manually performing each cognitive step.

History gives reasons not to infer employment from task productivity. Successive programming abstractions made individual programmers dramatically more productive while demand for software grew by orders of magnitude. ATMs made branches cheaper to operate and, for a period, increased demand for tellers who handled the remaining work. Radiology employment grew after predictions that image recognition would eliminate the profession. Translation work persisted even after machine translation approached human parity because lower costs expanded the volume and range of material worth translating. None of these examples guarantees benign outcomes, but they show why "ten times more productive" does not mechanically mean "ten times fewer workers."

## Four different claims about advanced AI

I take recursive self-improvement seriously but reject the tendency to collapse several distinct ideas into one inevitable sequence. I separate four dimensions: recursive self-improvement, humanlike general intelligence, economically transformative AI, and superintelligence. Progress on one does not automatically establish the others.

Recursive self-improvement is difficult to define and verify. A model producing a successor is not enough; developers still design scaffolding, curate data, run evaluations, and decide whether a result is an improvement. AI is strongest where outcomes are cheaply verifiable, while creative research requires new representations, judgment, and open-ended problem selection. A system can optimize benchmarked engineering without becoming a fully autonomous scientific community.

This motivates [open-world evaluation](https://arxiv.org/abs/2605.20520): give agents budgets, research problems, and realistic freedom, then evaluate the quality and novelty of their work rather than only their ability to reach a preselected answer. I treat creativity as one of several barriers to humanlike AI, not as a mystical human monopoly. LLMs possess unusual strengths, but human creativity also relies on representations, learning from sparse experience, and searching for the right problem formulation.

Economically transformative AI can exist without humanlike intelligence. Current systems are already affecting research, software, and organizational decisions. But realizing their full economic potential still requires reliable systems, new applications, complementary infrastructure, legal and policy changes, worker training, and institutional redesign. There is no single capability milestone that unlocks all of those changes at once.

Claims about superintelligence also need care. In many domains the binding limit is not intelligence: medical discovery may wait on trials, astronomy on instruments, and engineering on physical construction. Modern humans already appear superintelligent relative to the ancient world mainly because we inherit accumulated tools, institutions, and knowledge. AI may enlarge that collective capability, but an isolated system is not the same thing as an autonomous economy that can lawfully own resources, hire people, and act without human authorization.

## The work shifts toward evaluation

The practical conclusion is not that future jobs will look like present jobs. Purely technical, readily verifiable skills are likely to lose value. Effort shifts from producing an artifact toward deciding what should be built, evaluating what was produced, and taking responsibility for its consequences.

AI evaluation is already becoming a discipline of its own. If AI performs more of the rowing, we must spend more effort steering the ship. In research, that means deciding which questions matter, whether evidence supports a claim, and whether a system behaves safely outside a benchmark. Automating peer review is a trap if it accelerates scoring while eroding the human understanding needed to judge significance and originality. The mundane parts can be automated only to create more room for serious judgment, not to eliminate it.

The same shift appears in companies, where evaluations increasingly become proprietary knowledge. When model access is widely available, advantage comes from knowing what successful performance means in a particular domain and from maintaining the tests, data, and operational controls that measure it.

My personal rule is to distinguish AI's floor from its ceiling. The floor is what it can do alone; the ceiling is what a person can do with it. Competing against the floor encourages black-box use and eventual displacement. Raising the ceiling requires learning, experimentation, verification, and enough understanding to remain accountable. The aim is not a passive hope that machines align themselves, but co-superintelligence: people and AI systems increasing what individuals and institutions can accomplish while humans continue to choose the ends and govern the means.
