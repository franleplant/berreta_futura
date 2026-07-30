---
schema_version: 1
source_id: do-not-make-the-service-bus-non-deterministic-3a92442c
raw_bundle: 2897c9836334cfec9e19044a7b16980cc4035cadb8d7d020ba464ae268609ee6
artifacts:
- post.txt
extraction_method: Verbatim transcription from the authenticated browser DOM export.
---
second hot take, as it seems the first hot take landed. n8n was a silly idea, which i’ve always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn’t have the knowledge that service busses are a solved problem and there’s deep prior art in the spooky land of enterprise. look up anything in the @dotnet space such as mass transit, nservicebus, [1] wcf if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don’t make the entire service bus non-deterministic. [1] lots of bad memories here, not great tech impl but the theory / education is generally on point.
