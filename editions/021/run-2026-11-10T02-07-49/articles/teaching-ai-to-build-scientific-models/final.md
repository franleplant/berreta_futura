---
source_ids:
- teaching-ai-to-build-scientific-models-8a424d75
content_mode: article
label: ARTICLE
---

In 1951, Andrew Huxley spent over three weeks solving a set of equations with a hand-cranked calculator, because Cambridge's computer was out of action. He and Alan Hodgkin had built the equations to describe how a squid nerve cell fires. Most of the model followed from known facts, but one part was an educated guess: to fit the data, one variable had to be raised to the fourth power. They didn't know why. They cautiously suggested that several charged particles might have to move into place before a gate in the membrane would open. Decades later, a related potassium channel was found to have four identical pieces around a central pore. Today an AI system could plausibly find such an equation in an afternoon. But knowing the fourth power worked was not enough; what mattered was knowing that simpler versions didn't. Modeling has three steps: building, constraining, and interpreting. AI is increasingly involved in each, and in each what we need from it is the full range of models that fit the data, not one.

## Constraining

Constraining a model means tuning its parameters to fit measurements. Hodgkin and Huxley did it by eye and got one set of numbers. That showed the model *could* fit. It didn't show whether other numbers would fit as well.

Say a group dinner came to $120, but you don't know who ordered what. Everyone might have had a burger, or one person had steak and lobster while the rest had soup. Nerve cell models are like this: different gate parameters can produce near-identical electrical activity, and those combinations might lead to different predictions.

Bayesian inference returns every set of numbers that works reasonably well, as a probability distribution. But it requires calculating how likely the measurements are under every possible set of numbers, which is computationally impossible for most complex models.

Simulation-based inference (SBI) gets around this. You pick random parameters, run the model, and record the output, perhaps 100,000 times for a model like Hodgkin-Huxley, and millions for larger ones. Then you train a neural network to return, for a given output, the range of parameters that could have produced it. All it needs is a *simulator*: parameters in, data out. For many complex phenomena, from neuron networks to colliding galaxies, simulators are often the only kind of model we have.

The simulations are expensive and can take weeks. Once trained, though, the network performs inference on new data in seconds. When two neutron stars collide, SBI can locate the collision roughly in the sky fast enough to point telescopes at it. Applied to nerve cell models, it shows which parameters the data pins down, where several explanations remain plausible, and where another experiment is most needed.

## Building

The fourth power was not derived from first principles. It emerged empirically, from biological insight and from finding that simpler versions didn't work as well. That is how most models have been built: a scientist proposes a few candidates and tests them. But the space of possible models is essentially infinite, and a handful of proposals will very likely miss others that explain the data equally well.

AI systems can now help with, or take over, this step. An LLM-based agent writes code for candidate models, runs them, constrains them, compares them to data, and revises, until a model replicates the data accurately enough. Several such systems have appeared in the past two years.

The same problem returns one level up. Many *models* can explain the same data equally well. Run an agent twice and it might return two different, equally good ones. An agent that returns only one hides the rest.

So it is better to ask for the whole range of plausible models. The system proposes many, weights each by how well the data supports it, giving less credit to those that need much flexibility to fit, and proposes variations on the stronger ones. If every surviving model shares a feature, the data likely favors it. If they disagree, the evidence is thin there, and that points to the next experiment.

We shouldn't get ahead of ourselves. These systems have mostly been tested on rediscovering known models, and evidence that they work where no answer is known is sparse. Still, newer LLMs perform better at research tasks than older ones, and we expect these systems to keep improving.

## Interpreting

Hodgkin and Huxley's four-particle hypothesis carried weight only because of what they had ruled out. Had a simpler model worked as well, there would have been no reason to think the gate had several moving parts. Even so, they noted that a third or fourth power was needed and settled on four; higher powers might have fit slightly better, but the "improvement was not considered to be worth the additional complication."

Of the three steps, interpretation is the hardest to hand over to AI. We can measure how well a model fits, but not whether it improves understanding, and it's not clear how to make "understanding" an AI system's objective. One proposal is to judge an AI system by how well it predicts what happens when a system is disturbed. Another is to ask whether its outputs help human scientists understand the problem. One AI system for designing quantum experiments was trained to write a short program generating a whole family of related setups, so a physicist can read the design principle straight off the program.

Either way, a full distribution of models is crucial. A single model can't say which of its parts the data actually constrains, so it's easy to read meaning into parts that aren't. A range also makes predictions more robust. If every model that fits says blocking all sodium gates has a given effect, you can be fairly confident. If they disagree about blocking only some, that suggests the next experiment.

## Scale

Most famous models, Hodgkin-Huxley included, are compact because people had to build, constrain, and interpret them. That smallness also made them intelligible. As AI takes over more of the work, the limit will start to lift, and we can begin to model systems too complex to write down by hand, even if we can no longer understand them by reading the equations.

Hodgkin-Huxley describes one nerve cell. A fruit fly's brain has more than 100,000, a human brain tens of billions. For the fly, we now have a complete wiring diagram, and researchers have started building large-scale models on it, including one that predicts activity across its visual system.

At these scales there will be no single correct model; in most cases there is no such thing. The question will be which properties all data-compatible models share and which predictions follow from them. The most useful experiments will rule out the most remaining models, even when they aren't the ones a human finds most interesting. Climate scientists already report projections as the spread across many simulations, and particle physicists at the Large Hadron Collider map which versions of a theory the data rules out and which remain open.

We don't want to go back to fitting curves by eye and hand-cranking calculators. But that work was not wasted: Hodgkin and Huxley understood their model because they had built it and knew what hadn't worked. For an AI system to offer understanding, it must deliver the same: not just the model that fits, but which parts the data pins down, which stay open, which alternatives failed, and what new puzzles appeared. A scientific model may provide an answer, but it is the process of constructing it that provides the insight.
