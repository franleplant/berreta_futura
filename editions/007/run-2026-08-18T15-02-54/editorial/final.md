---
label: EDITORIAL
title: How Systems Learn to Say No
byline: The Editors
---

The safety of a distributed system rests on how the losing writer is stopped.

The field learned this long ago and keeps relearning it. In the 2006 Bigtable paper each tablet server held an exclusive lock on a file in Chubby, Google's Paxos-backed lock service, and a server that lost its lock stopped serving, whatever it still believed about itself. The interesting part was never the algorithm. It was the refusal.

Where the refusal is missing, the bill arrives. In October 2018 GitHub lost 43 seconds of connectivity between two data centers. Databases on both coasts took writes. Untangling them cost more than twenty four hours of degraded service, for under a minute of bad network.

What is new is where the refusal lives. Amazon S3 became strongly consistent for reads after writes in December 2020, and now accepts conditional writes, so a bucket can say no.

We would ask one question of any fleet built this way: does your object store truly fail a conditional write, or does it only accept the header? A store that lies gives you two owners of one record, and your users find out before your vendor does.
