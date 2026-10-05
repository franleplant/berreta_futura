---
source_ids:
- statecharts-a-visual-formalism-for-complex-syste-7833c2fd
content_mode: article
label: ARTICLE
---

Some features belong to the basic statechart formalism but did not appear in the watch example: conditional and selection entrances, timeouts drawn on a state, and charts laid out away from their natural place. Two further notions tie the chart to the real system. Actions take zero time and activities take time. Other features are only under investigation, and for most of them we have neither a final syntax nor a satisfactory semantics. Formal semantics is hard, mainly because events generated inside the chart are broadcast to orthogonal components, and [15] gives one version. The formalism grew out of avionics work at Israel Aircraft Industries, where it is still the main behavioral specification method. A computerized tool, STATEMATE, is planned for release in June 1987. Our closing thesis is that visual formalism should be the name of the game.

## Actions and activities

Nothing in the charts so far connects them with the real watch. Who says it beeps or displays at all? Who says it even keeps the time? Pure statecharts represent the control part of a system. What they lack is the ability to generate events and change conditions.

A transition label may end in "/S", where S is an action. We reserve the word action for instantaneous happenings that ideally take zero time, such as sending a signal or an assignment. A transition labelled a/S in one component generates S. A transition labelled S in an orthogonal component senses it and is taken at the same instant. The distinction between events and actions is almost precisely the distinction between input and output.

Activities are to actions what conditions are to events. An activity, such as beeping, displaying, or a long computation, always takes time. Each activity X comes with the actions start(X) and stop(X) and the condition active(X). The model extends the Mealy and Moore automata: actions may be attached to transitions, to entering a state, and to leaving it. An activity carried out throughout state A means start(X) on entering A and stop(X) on leaving it. A full transition label reads a(P)/S: event a, guarding condition P, action S. The nesting of states induces concurrency of actions. Defining the formal semantics of these labels is quite a delicate matter.

## Possible extensions

These ideas are preliminary. For most of them we have neither a final syntax nor a satisfactory formal semantics. Fragments of all of them have been used manually in experimental projects.

Statecharts need not be trees. A state with two parents turns an XOR into an OR, and it can save describing joint exits twice. Too much overlapping, though, may cost more comprehension than it saves, and then two copies are better. Overlapping also handles a state that sometimes lives alone and sometimes joins another in orthogonal marriage. The alternatives are drawing it twice or inventing a "not really B" state. Entrances to substates become ambiguous, so we suggest arrows that can waive the pleasure of entering a state. Overlapping causes semantic problems, especially with orthogonal components, and a first syntax and semantics appear in [20]. We are fully convinced that an appropriate version will greatly enhance the formalism.

## Semantics

Statecharts are much harder to give formal semantics than finite automata. Depth and orthogonality alone can be translated into ordinary automata, as claimed in [12], though even there delicate problems arise. The real difficulty is events and conditions generated within the chart. Communication is by broadcast: one part generates an event, every other part senses it, and responses may generate further events. Cycles must be handled, presumably by rendering them undefined. The dynamics also generate the events "entered state" and "left state," and some configurations then have no obvious outcome. Our intuition may say one thing, but a formal semantics must supply all the answers. Simultaneous events, and their negation, add more trouble.

## Related work

State machines have been suggested many times for system specification, and many authors identified their problems, especially the exponential blow-up in states.

- **Petri nets** are graphical and precise, with more than 20 years of research behind them. They lack a satisfactory hierarchical decomposition, so they have only one level of concurrency. Adding depth to places might be one way to overcome this.
- **CCS and CSP** need further study before their precise relationship to statecharts is known. In CCS, an interrupt that a statechart draws once must be added to each process. Those languages communicate by rendezvous, whereas statecharts broadcast. The two mechanisms are hard to implement in terms of each other, and it would be interesting to find out which gives more natural specifications. Broadcast is not crucial, however: statecharts could conceivably use rendezvous and keep depth and orthogonality.
- **ESTEREL** is one of the most intriguing languages for real-time work. Many of its decisions are strikingly similar to ours: instantaneous transitions and broadcast events that are missed if no one is listening. Its compiler prunes impossible interleavings and often produces smaller automata than a naive product. Its techniques might help in building an optimizing compiler for statecharts.

## Practice

The formalism was conceived while the author was consulting for Israel Aircraft Industries on a complex avionics system. The project involved pilots, engineers, communication experts, software people and weapons experts. Our experience has been very encouraging. People could enter a behavioral description of any portion of the system in almost no time, and turnover for peer review was unusually short. Statecharts are still the project's main behavioral specification method, and they are being tried in several software, electronics and semiconductor firms.

All of this use is manual. A serious evaluation will depend largely on a good computerized tool. STATEMATE, built by AD CAD in Cambridge, Massachusetts, is in beta-site tests. It supports editing, consistency and completeness checks, verification of properties such as absence of deadlock, and graphical simulation.

## Conclusion

The paper rests on four theses:

- Reactive systems differ from transformational ones and need different specification approaches.
- They need a clear, rigorous behavioral description as the backbone of development, from requirements to user documentation.
- Statecharts are one possible fitting formalism for that.
- The future lies in visual languages with appropriate structuring elements.

A scientific paper cannot really validate these, but we have tried to show that they deserve serious consideration. People have long valued the state/event approach but lacked a formalism with depth and modularity. That lack, together with the blow-up and the sequential nature of conventional machines, seems to have kept states and events out of really large designs.

We believe that before long engineers will work at graphical workstations with large, perhaps blackboard-size, displays. Most visual methods today are aids, and the real description is textual. We propose the reverse: the statechart is the formal description, every graphical construct has a precise meaning, and text is the aid. Work under way proposes statecharts for hardware description [6] and communication protocols [2], with encouraging results.
