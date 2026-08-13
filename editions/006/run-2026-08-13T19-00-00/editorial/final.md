---
label: EDITORIAL
title: The Supervisor Tree Returns
byline: The Editors
---

Erlang's answer to failure is not consensus. It is a parent. The actor crashes, and the supervisor above it decides: restart with initial state, or stop. Authority sits somewhere specific, and you can name it.

Cloudflare shipped that idea as a product. Alice and Bob edit one spreadsheet, and the fix is not clever merging. It is one object, single-threaded, at one address, `idFromName("my-counter")`, holding the truth. CRDTs are available on top and mostly declined: too complex, too limited.

Now we are told safety comes from the opposite. Give everyone a superintelligent lawyer and the courtroom balances out. Widely held power is the foundation. We think that is the CRDT answer to a problem this industry already solved the other way, and it fails the same way: consistency arrives eventually, over a document that mattered on Thursday.

Name the cost. A coordination point is a chokepoint. It is single-threaded. Whoever owns it owns the room. We would rather argue with an owner we can name than with a quorum of agents, each aligned to its own person, each certain.

Prediction: the lab that ships agents to a billion people builds a supervisor tree over them within five years, and does not call it that.
