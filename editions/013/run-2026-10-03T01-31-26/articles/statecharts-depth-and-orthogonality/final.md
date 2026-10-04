---
source_ids:
- statecharts-a-visual-formalism-for-complex-syste-7833c2fd
content_mode: article
label: ARTICLE
---

Conventional state diagrams fail for complex reactive systems: the number of states grows exponentially, and all of them must be laid out flat. Statecharts extend state diagrams with essentially three elements: hierarchy, concurrency and communication. States nest inside states, a state can split into orthogonal components that run side by side, and arrows may start and end at any level. Small diagrams can then express complex behavior. We intend to demonstrate that statecharts counter many of the objections raised against conventional state diagrams, and thus appear to render specification by diagrams an attractive and plausible approach.

## The problem

A reactive system, unlike a transformational one, is largely event-driven, continuously reacting to external and internal stimuli. Telephones, automobiles, communication networks, operating systems, avionics and the man-machine interface of ordinary software are all examples. Its behavior is the set of allowed sequences of input and output events, conditions and actions. Such a set does not seem to lend itself to friendly, level-by-level descriptions.

For a transformational system an input/output relation is usually sufficient, and good methods exist for decomposing it. For reactive systems, we are of the opinion that the problem has not yet been satisfactorily solved.

States and events are a natural medium here. The basic fragment is a transition: "when event a occurs in state A, if condition C is true at the time, the system transfers to state B." A state diagram collects such fragments into a directed graph. But a complex system cannot be beneficially described this way, because of the exponentially growing multitude of states arranged in a flat, unstratified fashion. A useful approach must be modular, hierarchical and well-structured, and must handle statements such as:

- "in all airborne states, when yellow handle is pulled seat will be ejected", which calls for clustering states into a superstate;
- "gearbox change of state is independent of braking system", which introduces orthogonality;
- "when selection button is pressed enter selected mode", which hints at more general transitions;
- "display-mode consists of time-display, date-display and stopwatch-display", which captures refinement.

The name "statecharts" was chosen, for lack of a better one, as the one unused combination of "flow" or "state" with "diagram" or "chart".

## Depth

Trees and line-graphs make no use of a diagram's area. We use rounded boxes for states at any level and let encapsulation express hierarchy.

If one event takes the system to B from either A or C, we cluster A and C into a superstate D and replace the two arrows with one. D is the exclusive-or of A and C: to be in D is to be in exactly one of them. Letting a transition that leaves a superstate stand for transitions leaving all its substates turns out to be highly important, and is the main way statecharts economize on arrows. Clustering is bottom-up; refinement is top-down. Both give rise to the or-relationship between a state's substates.

A small default arrow marks which substate is entered when nothing else is specified, as start states do in finite-state automata. An H entrance enters the most recently visited substate, on its own level only; H* applies history all the way down. In the watch's update mode, one d-arrow into H replaces nine d-arrows, one per substate.

## Orthogonality

AND decomposition splits a box into components with dashed lines. Being in the state means being in all of its components at once. If Y consists of A (with substates B, C) and D (with E, F, G), being in Y means being in B or C together with E, F or G. Entering Y by default yields (B, F). One event can move B to C and F to G simultaneously, a kind of synchronization; another can change only the D component, whatever A is doing, a kind of independence.

The flat equivalent has six states, because the components had two and three. Two components with one thousand states each would give one million. This is the root of the exponential blow-up, and orthogonality is our way of avoiding it.

Components need not be fully independent. A condition such as "in G" lets A know something about D's inner states. Orthogonal product generalizes the usual product of automata, which is usually required to be disjoint.

## The watch

The running example is the author's Citizen Quartz Multi-Alarm III wristwatch: a main display, four smaller ones, a two-tone beeper and four buttons, a, b, c and d. Its alive state consists of six orthogonal components: a main one with the displays and alarm-beep modes, one each for the enabled/disabled status of the two alarms and the chime, one for power and one for the light.

The two-state light component looks rather innocent but is subtle because of its scope. Pressing b in the update state simultaneously turns on the light and exits updating.

Late changes come painlessly. The beep test, pressing b and d together, is drawn as a detached component and attached orthogonally to whatever portion of the chart it applies to. On the author's watch it works in time, in date and throughout the update sequence, but not in the 2-second wait period, which took the author quite a while, and some strenuous finger-twisting, to discover. A new box drawn around the relevant states carries the test. Citizen's documentation lists the light and the beep test the same way, with no indication of scope, despite the major difference between the two. The 2-minute automatic return to time involves merely drawing another box around the relevant displays.

Scenarios can be traced through the chart. Suppose the watch is updating the month, and the user presses d, then b, without releasing either. The update component says we end up in time, the beep-test component says the beeper beeps, and the light component says the light goes on. This is in fact quite the case: we end up in time, one month ahead, with the beeper beeping and the light on.

The author obtained this statechart by the obviously inappropriate method of observing the final product. Had it been the basis for the watch's initial specification, the undescribed anomalies might have been avoided.
