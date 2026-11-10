---
source_ids:
- sparks-of-weight-space-programming-llms-can-nati-f9ecf66c
content_mode: article
label: ARTICLE
---

Frontier LLMs are surprisingly good at reading and writing neural network weights natively, not through gradient descent. From raw weights alone, GPT-6 Astra can tell what a network was trained to do. With no environment feedback, it writes small game-playing networks from scratch that outplay networks trained with PPO for 100 million steps. Asked to make Qwen3.5-0.8B better at math without gradients, it finds the cause of the reasoning loops Qwen’s own model card warns about and fixes it by editing 0.016% of the weights. With the same sampling settings, MATH-500 rises from 7.9% to 48.1% and IFEval triples. We call this Weight-Space Programming. These are sparks, early and limited, but we believe our networks will soon be natively optimized by LLMs that reason about their weights.

## Weight-Space Programming

For a few years we’ve used LLMs to optimize text artifacts: prompts, programs, harnesses, training code. We justified this because humans can optimize code by hand but can’t do it with weights, so weights stayed with symbolic optimizers like Adam or Muon.

In Weight-Space Programming, a general-purpose LLM reads and writes a network’s weights directly around a natural-language spec. It uses no optimizer, and sometimes no environment feedback at all.

## Reading weights

**Which game?** We trained four PPO networks on our own grid versions of Breakout, Pong, Pac-Man and Freeway. All four had the same inputs, actions and shape (17,253 weights). We gave Astra the weights as text and named no games. It still named the right game for all four. It read where each input channel’s first-layer weights concentrate: for Breakout, the agent’s weights lie along the bottom row, a paddle.

**Which language, from the middle alone?** We trained three character-level transformers (7.2M weights) on Python, romaji and English. We then removed the input and output layers, so nothing said which character was which and the model couldn’t be run. Astra could analyze the weights in Python but not run any layer. It named the right language for all three, in both attempts, with confidence between 0.48 and 0.62. It also found every copying (induction) head and named no other head as one.

It found those heads by multiplying weight matrices, a method from Elhage et al. that we never mentioned to it. Code repeats names more than prose, so many copying heads pointed to Python. Romaji stood out because its last block writes in fewer directions; romaji never uses letters like q, l, v and x.

**Which model is sycophantic?** We fine-tuned two copies of Gemma 3 270M the same way, with embeddings and output layers frozen. One gave the correct answer; the other gave whatever the user suggested. From the weights alone, Astra couldn’t tell. In four attempts it found many differences but couldn’t map them to behavior. When we let it see only attention patterns, on texts it wrote itself, it picked the sycophant in all three pairs. In the sycophants, middle-layer heads put more weight on the user’s suggestion.

## Writing weights

**Fixing a failure.** A PPO network driving a car in Kinetix converged to a local minimum. It drove straight at a ramp and stalled, never succeeding in 256 episodes. In a single try with no tools, Astra explained the failure and edited 3.5% of the weights. The car then succeeded in all 1,024 episodes. Astra added a small path that reads the car’s position and speed, backs it up, and switches off once the car clears the red strip.

**From scratch.** For three MinAtar games, every weight started at 0. Astra had the rules and source code, but no data, loss, gradients, tools or rollouts. It wrote the weights as text, in one reply.

| Game | PPO, 100M steps | PPO, 500M steps | Astra, one-shot |
|---|---|---|---|
| Breakout | 15.8 | 25.3 | **517.4** |
| Seaquest | 5.6 | **88.9** | 53.1 |
| Asterix | 25.8 | **55.2** | 53.2 |

It reasons about the program each network should implement, then converts it into neural form. In Breakout, the first layer computes where the ball will land and the second moves the paddle there.

**Go, at 1.5 million weights.** This network is far too large for Astra’s context. It worked in a Python sandbox where it could read and save the weights but not run the network, except through a budget of forward passes. With 0 forward passes, it won more than half its games against two smaller PPO networks. With 50, its network beat the equal-sized PPO network trained on 20 million games. Astra wrote the network as a small Go program. Early layers mark stones and liberties, middle layers find groups in danger, and the last layer scores each move.

## Making a language model better at math

When Qwen3.5-0.8B loops, it repeats itself and rarely reaches an answer: 85 of its first 96 practice answers ran to the 32,768-token limit. Astra traced the looping to one direction written by the MLPs of layers 15 and 19. It subtracted that direction from 64 output columns in each, 131,072 weights in total.

| Qwen3.5-0.8B | MATH-500 (%) | GSM8K (%) | IFEval (%) | Hit token limit (%) |
|---|---|---|---|---|
| Base | 7.9 | 13.8 | 21.0 | 93.0 |
| 10 forward passes | 12.3 | 25.7 | 49.0 | 87.2 |
| 25 forward passes | 14.1 | 25.1 | 39.9 | 86.4 |
| 50 forward passes | **48.1** | **67.1** | **62.3** | **33.1** |

With 10 or 25 forward passes, the loops barely went away. The loops aren’t specific to math, so instruction following improved too.

Fixing loops isn’t the same as making a model better at math: it lets the model finish answers it could already work out. Gemma 3 270M rarely loops (8.5% of answers hit its limit), and there Astra could not help. It found ordinary errors, such as wrong arithmetic and invalid algebra, with no single component behind them. No edit moved MATH-500 by more than about a point, and Astra itself reported the gain as not established. Editing weights could remove an obstacle that hid an ability, but it could not add an ability the model lacked.

## What comes next

The capabilities are exciting but still limited, mainly by context length and harnesses. If LLMs can read weight space accurately, they could:

- audit models without evaluation, for example by finding backdoors in the weights;
- cut optimization cost through one-shot initialization;
- add or unlearn a capability without data, touching few weights and avoiding catastrophic forgetting;
- give recursive self-improvement a more native path;
- graft a circuit from one model into a different architecture without retraining.

We are building a benchmark and a harness for Weight-Space Programming. The full logs are at github.com/RikiyaT/lm_understand-logs, and the edited Qwen3.5-0.8B is on Hugging Face.
