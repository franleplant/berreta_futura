---
source_ids:
- amazon-saves-millions-by-replacing-sonnet-4-6-wi-d8522f99
content_mode: article
label: ARTICLE
---

Amazon and AWS teams used Claude Sonnet 4.6 to label tickets in one of the world's largest internal ticketing systems, and the nine-month-old model did well. Two Amazon engineers recently swapped it for Strands Decider, a decision model we launched a month ago, and it performed just as well at 98% less cost. The change will save millions of dollars of token costs in a year.

## The job

Sonnet 4.6 labeled tickets at enormous scale: customer escalations, capacity requests, automated alarms, security findings, sorted into 20 category types. It ran a long system prompt on every ticket, generating JSON and reasoning against a fixed set of labels.

A decision model can't generate text. Given some state and a question with options, it returns a probability for each option plus a confidence score. Here the state is the ticket; the options are the label catalog.

We started with Strands Decider 2B. The E4B Gemma 4 build got clearly better results on a test set, so we switched. After we tuned how confident the model needed to be before applying a label, E4B beat production Sonnet on a separate set of our tickets.

E4B runs on SageMaker `ml.g5.xlarge` instances (one A10G, 24 GB each). It used about 19 GiB, and one request took about 640 ms. Ticket events land in SQS, which triggers a Lambda that calls the SageMaker endpoint. Apart from our ticketing APIs, everything in the path is a standard AWS service.

## The switch

We didn't want to flip a switch and hope. The labeling Lambda reads a three-way setting from AppConfig on every message:

- `BEDROCK`: Sonnet labels every ticket; Strands Decider isn't called.
- `DUAL`: both run in parallel. Sonnet's labels are applied and compared with Strands Decider's.
- `DECIDER`: Strands Decider labels every ticket; Bedrock isn't called.

## What we measured

| | Sonnet 4.6 | Decider E4B | Improvement |
|---|---:|---:|:---:|
| Average time per call | 4,215 ms | 897 ms | 78% |
| Total tokens per ticket | 6,724 | 2,010 | 70% |

Strands Decider produced one output, the choice, instead of a JSON answer of 170 tokens. Its prompt was also much shorter. Production's label descriptions alone are longer than its 4,096-token window, so we rewrote each of the 20 labels as a one- or two-sentence criterion, plus a "none" option. On long tickets it drops the oldest comments to fit. On the day we turned off Sonnet, average Lambda duration dropped 74%.

## What it costs

At published us-east-1 on-demand prices, Sonnet costs $0.0222 per ticket, about $22,200 per million. Strands Decider runs at $1.408 per instance-hour. One instance can handle about 5,600 tickets an hour, which would be $250 per million at full use; we keep headroom for bursts, and in practice it comes to about $500 per million. That is about 44 times cheaper, a 98% reduction. These are list prices, and they leave out the Lambda, which also runs for less time per ticket now.

One thing surprised us: JSON key order changed the answer. The same content with keys reordered moved output probabilities by up to 0.19. We now send every request with sorted keys. If you serve a decision model behind an API, check this before you compare runs.

## Our lessons

This worked because the task is a closed choice from a known catalog, the volume is high, and the latency of the old path mattered. If your labels need explanation text, if the catalog changes weekly, or if you can't fit the useful context into a few thousand tokens, a decision model probably can't replace the LLM's job.

The part we'd copy regardless of model is the three-way switch. Running both on real traffic, then judging every disagreement, told us more than any offline eval would have. Going back was a 45-second config change.
