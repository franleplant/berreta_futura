---
source_ids:
- claude-discovers-a-novel-enzyme-system-ef1b3a47
content_mode: article
label: ARTICLE
---

We've formed a life sciences research group and laboratory at Anthropic to see whether general AI models can systematize and accelerate biological discovery. In one of our first programs, we gave Claude a prompt to search a massive DNA database for new reverse transcriptases (RTs), enzymes that copy RNA into DNA. One agent spotted a repeating pattern of DNA sequences next to an odd-looking RT. After further analysis and lab testing, we recognized a previously uncharacterized enzyme system in bacteriophages, which we call array-associated reverse transcriptases (ART). We don't yet know its function. Its characteristics have only ever been found together in a handful of other systems, all of which are programmable and perform operations like cutting, copying, and pasting DNA.

## Why we built a lab

Many discoveries began with a scientist noticing something odd in nature's molecular machines. Restriction enzymes came from bacterial immune systems and launched the biotechnology industry. Taq polymerase, from a Yellowstone hot spring, became the basis for PCR. CRISPR was first noticed as an unusual repeat sequence in bacterial DNA.

We believe acceleration will come from a new way of doing biology, in which agents collaborate with humans in every step. That required our own lab and a single team working on everything from training Claude in biology to running experiments.

## How we work

Claude surveys a protein family, reads the literature, and reproduces established results from public data to check its methods. It then searches for family members or genomic neighbors that fit no described system and writes a short report for each candidate, proposing a function and its evidence. In follow-up analyses, Claude critically evaluates that evidence, and most candidates are typically eliminated. A survey may end with a single candidate worth testing, or with none.

Survivors go to the lab, where human scientists do all the work, at biosafety levels BSL-1 and BSL-2, with no pathogens that can infect humans. Because Claude produces hypotheses so prolifically, the hypotheses have become an object of study. What we learn about which ones we judge worth testing goes back into Claude's instructions and teaches it to mimic our own scientific taste.

## Claude finds ART

Our involvement was limited to the initial prompt and the lab work. Over 21 hours, roughly 950 agents using 210 million tokens gathered over 200,000 RTs, picked out 3,500 new candidate systems, and narrowed those to the 20 most compelling, each with a report. For an expert scientist, this analysis can take weeks to months.

Reading raw DNA near one unusual RT, the agent exclaimed: "[The DNA next to the RT] is spectacular: I can see by eye a tandem repeat array … that's a CRISPR-like … repeat array?!" It then counted the repeats, measured their spacing, compared the layout with known RT systems, and searched the literature for earlier reports. Convinced it had found a new system, it filed a report for human review.

ART has three parts: the RT, a partner gene of unknown function beside it, and a long array of evenly spaced, non-coding DNA repeats. The underlying RT, found in a jumbo phage, had been identified before; Claude appears to be the first to notice the array and the accessory protein. A CRISPR array holds a bank of different RNA sequences that make CRISPR-Cas systems programmable. Our first experiments show the ART array is also expressed as a set of distinct short RNAs, suggesting something analogous may be at play.

Feng Zhang, a CRISPR pioneer at MIT and the Broad Institute, called RNA-repeat arrays associated with RTs "genuinely intriguing" and said they merit further investigation.

## What comes next

Experiments to determine how ART works are underway. We're sharing early to show that Claude can autonomously detect anomalies and drive analyses toward discovery, and we've released a pre-print with more detail. We'd like to work with other scientists, in genomics and other fields, and welcome research proposals.
