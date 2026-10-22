# Towards securing the internet
By Greg Brockman

My first programming language was PHP. I remember discovering the joy of creating software while learning to build in such a beginner-friendly and accessible language.

That's one reason I've felt a deep personal connection to the work that our team has been doing to secure PHP. Over the past two months, we have been leading a coalition to mitigate one of the most severe bugs in open source software found in recent memory, php2shell. It was discovered and addressed using our models as part of our Patch the Planet initiative. This vulnerability allows any attacker to execute code on nearly all deployed PHP application, effectively allowing them to exfiltrate private user data or modifying the site however they want.

The bug has been present in PHP for 14 years, and a limited version of it had been discovered in 2024 and wasn't considered significant at the time. Security researchers at Calif, operating as part of Patch the Planet, used GPT-5.6 Sol to find a version of this bug in August; our team found a more complete version independently in September.

Our team put a huge amount of work into preparing the world to mitigate the impacts of this vulnerability, including working closely with government and partners including PHP, Wiz, and Cloudflare. While the tail end of the disclosure didn't go as planned (the original target date was a October 22 release, but details started to leak early, so PHP’s maintainers brought the release forward to October 21), I am grateful that the coalition successfully had an entire two months to prepare — the fixes were quite intricate for PHP, and a leak significantly before the patch was available would have been very impactful.

We have been in parallel working on fixing several other significant bugs we've found, including a remote code execution that Node.js announced today, but with less collective attention due to bandwidth constraints across our team and partner organizations. We expect to find many more such issues over upcoming months. I'm proud of the work we and our many partner teams have been doing for PHP and other bugs, but it also was quite slow and manual — both properties that won't scale for the agentic era. We are feeling the fundamental limitations of managing each bug in the classic way.

New approaches will be needed, and we are actively thinking about those and looking for feedback from the community to help us collectively rise to the challenge of improving the security of the internet as models improve. As vulnerability discovery ramps, we will need new defensive solutions, potentially including authorized defenders (such as government) scanning the internet for vulnerable hosts and either notifying or, in extreme cases, patching those systems remotely.

Defenders need to have a tighter OODA loop than attackers, which we believe is possible especially if defenders have access to stronger models than attackers. Increasingly, companies and projects will be as secure as the models they are securing themselves with, and attackers will be as effective as the models they have access to. It should thus be a national priority to ensure that we always have the most capable cyber models.

Towards broader access of our models, on September 3rd, we committed $1B in credits to frontline defenders, such as those protecting critical infrastructure. We also have been working to scale our Daybreak program to put cyber capabilities in the hands of trusted defenders, while also tightening our safeguards to mitigate abuse. We are also working to build more tools that help site operators and individuals defend themselves with frontier AI; please reach out (gdb@openai.com) if you'd like to be an early tester.

I believe we're entering a new phase of cybersecurity, where the models are able to find vulnerabilities with internet-scale impact. We believe that defenders everywhere have a part to play, applying models to their own defenses, finding and fixing issues in shared infrastructure, and sharing best practices that can ultimately make the internet more secure.

https://openai.com/index/coordinated-disclosure-of-critical-vulnerabilities/
