---
label: EDITORIAL
title: Never Trust a Check That Never Fails
byline: The Editors
---

*The Editors*

A check you have never seen fail is not a check.

A test that always passes is not a witness. It is a mirror, and a mirror agrees with whatever you hold up to it.

The only way to know a check works is to break the thing it guards and watch it catch you. A team building software that moves a live database off a dying machine wrote properties to prove that no acknowledged write is ever lost. Then they wrote deliberately broken versions of their own protocol and ran the properties against those. A property that passed the broken version was itself the bug.

When a check cannot fail, the cost lands on whoever did not build it: the person paged at four in the morning, the reviewer who approved on a green tick, the customer whose write was acknowledged and then lost.

So pick one guarantee you would defend in a meeting and break it on purpose this quarter, somewhere breaking is cheap. Kill the node mid write. Delete the constraint. If the board stays green, you were never protected, only unobserved, and now you have the date you found out.
