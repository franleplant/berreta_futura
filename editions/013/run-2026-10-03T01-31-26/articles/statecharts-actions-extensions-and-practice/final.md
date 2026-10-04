---
source_ids:
- statecharts-a-visual-formalism-for-complex-syste-7833c2fd
content_mode: article
label: ARTICLE
---

Beyond depth and orthogonality, statecharts carry a few smaller devices, such as conditional and selection entrances and time bounds drawn on the state itself. Pure statecharts describe only control. We connect them to the real system through two kinds of thing: actions, which take zero time, and activities, which last and are started and stopped by the chart. Several further ideas are preliminary, and most have no settled syntax or semantics. Formal semantics is delicate, chiefly because events generated inside the chart are broadcast to orthogonal components; a version is given in [15]. Among related approaches, Petri nets lack satisfactory hierarchy, CCS and CSP communicate by rendezvous instead of broadcast, and ESTEREL is strikingly similar. The formalism grew out of an avionics project, where using it by hand has been very encouraging, and a tool, STATEMATE, is nearly finished. The future, we hold, lies in visual languages in which the picture is the formal description itself.

## Actions and activities

Almost nothing in the charts so far connects their states and transitions with the real watch. Who says the watch beeps or displays at all? Who says it even keeps the time?

Pure statecharts represent the control part of the system. What is missing is the ability to generate events and change conditions. We write ".../S" on a transition, where S is an action. An action is a split-second happening that ideally takes zero time, like sending a signal or making an assignment. Many actions are outputs of the whole system, but not all. Label one transition a/S and a transition in an orthogonal component S. When a is sensed, the first transition fires, and its action S is sensed as an event by the second, instantaneously. The distinction between events and actions is almost precisely that between input and output.

Activities are to actions what conditions are to events. They take nonzero time: beeping, displaying, lengthy computation. With each activity X we associate actions start(X) and stop(X) and a condition active(X). Following Mealy and Moore automata, we allow actions on transitions, on entering a state, and on leaving it. We also allow an activity carried out throughout a state, which is the same as start(X) on entry and stop(X) on exit. A transition label becomes a(P)/S: event a, guarding condition P, action S. Defining the formal semantics of these action-enriched charts is quite a delicate matter.

All this assumes a functional and physical decomposition of the system is given or can be produced, which is by no means trivial. We don't deal with how to specify the activities themselves.

## Possible extensions

These are preliminary ideas under investigation. For most we have neither a final syntax nor a satisfactory semantics. Fragments of all of them have been used manually in our experimental projects. They include parameterized states, temporal logic, recursion and probability. The one we press hardest is overlapping states.

There is no deep reason for the state hierarchy to be a tree. A state may have two parents, which turns an XOR into an OR. Too much overlapping can make a chart incomprehensible, and then one can resort to two copies. Overlapping also handles a state A that lives alone at times and is joined in orthogonal marriage with B at others. It does this more cleanly than duplicating A or adding an artificial "not really B" state. Overlapping causes semantic problems, especially with orthogonal components; a first syntax and semantics appears in [20]. We are, however, fully convinced that an appropriate version will greatly enhance the formalism's potential.

## Semantics

Depth and orthogonality can be translated into ordinary automata, as claimed in [12], though even there delicate problems arise. The harder problems come from events and conditions generated inside the chart and sensed in orthogonal components. Statecharts communicate by broadcast: one part generates an event, and all others sense it and may generate more. Cycles must be handled, presumably by rendering them undefined. Events like "entered state" raise cases where the outcome is unclear. Our intuition may favor one configuration, but a formal semantics must supply all the answers. Simultaneous events and their negations add more trouble.

The solution is far beyond this paper; [15] gives a formal syntax and a version of operational semantics. Its heart is a function nextstep(X, C, E). For a full basic configuration X, external conditions C and simultaneous external events E, it returns the possible next configurations. It selects the triggered transitions and follows the consequences of each, including new transitions they enable, until the situation is stable and consistent. It then applies the result and dives down by defaults. More than one result means nondeterminism, which is an error pragmatically and the general case formally.

## Related work

State machines have been proposed many times for specification, and many papers have hit their problems, above all the exponential blow-up in states. In [21] the authors give up on them. They call state-transition diagrams hard to read, hard to draw and change, and no good for large specifications.

Petri nets are graphical and precise, backed by over twenty years of research, and allow maximum concurrency. Their drawback is that they lack satisfactory hierarchical decomposition. Introducing depth into places might be one way out.

CCS and CSP differ from statecharts in two ways. Interrupt-driven behavior over many states is one arrow in a statechart; in CCS each relevant process needs its own branch. Those languages also use rendezvous, while statecharts broadcast, so the sender proceeds even if nobody listens. The two mechanisms are hard to implement in terms of each other, and it would be interesting to learn which gives more natural specifications. Broadcast is not crucial to statecharts; a rendezvous version is conceivable.

ESTEREL [3] is one of the most intriguing real-time languages, and many of its decisions are strikingly similar to ours. Its compiler prunes impossible interleavings, often producing automata smaller than the naive product. Its techniques might be useful for an optimizing statechart compiler.

## Practice and implementation

The formalism was conceived while the author was consulting for Israel Aircraft Industries on a complex avionics system. That project demanded that pilots, engineers, and experts in communication, software, hardware and weapons keep specifying and revising the system together. Our experience there has been very encouraging. People could enter a behavioral description of any part of the system in almost no time, and turnover for peer review was unusually minute. Statecharts remain that project's main behavioral method and are used experimentally in several software, electronics and semiconductor industries.

All this use is manual. A serious evaluation will depend largely on a good computerized graphical tool. STATEMATE, built by AD CAD in Cambridge, Massachusetts, is in its final stages. A prototype is in beta tests, with a commercial version planned for June 1987. It supports editing, consistency and completeness tests, checks for nondeterminism and deadlock, and graphical simulation.

## Conclusion

The paper rests on four theses. Reactive systems differ from transformational ones and need different specification. They need a clear, rigorous behavioral description as the backbone from requirements to user documentation. Statecharts are one possible fitting formalism for it. And the future lies in visual languages that exploit graphical interaction. A scientific paper cannot really validate these, but we have tried to show they deserve serious consideration.

People working on complex systems have long appreciated the state/event approach, but they lacked a formalism with depth and modularity. That lack seems to have kept states and events out of really large designs. So do the blow-up and the sequentiality of conventional machines.

We believe that before long engineers will work at graphical workstations with large (blackboard size?) displays of fantastic resolution. Most visual methods today are aids to a real description written in text. We propose the reverse: the statechart is the formal description, each graphical construct has a precise meaning, and text is the aid.
