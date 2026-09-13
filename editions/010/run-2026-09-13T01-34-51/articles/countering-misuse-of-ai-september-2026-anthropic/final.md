---
source_ids:
- countering-misuse-of-ai-september-2026-anthropic-d957d6c9
content_mode: article
label: ARTICLE
---

Over eight months we identified and disrupted operations in which threat actors tried to use Claude: cyber operations, influence operations, surveillance, scams and fraud, biological misuse, conventional weapons development, and distillation, from December 2025 through August 2026. Haiku, Sonnet and Opus were used; no case involved Fable or Mythos, with the exception of one illicit distillation. These aren't typical misuse but the most notable and novel activity we've identified to date. In each case we disrupted the activity, strengthened our safeguards with what we learned, and shared intelligence with authorities and industry partners where appropriate.

## Sophisticated attacks no longer require sophisticated attackers

AI has collapsed the labor and tooling gap that used to separate well-resourced state-sponsored operations from individual operators. A hacktivist using stolen API keys, disparate financially motivated individuals, and a state espionage operator each sustained multi-victim campaigns that a year ago would have required many skilled operators and specialist knowledge. For investigators, sophistication has stopped being a reliable signal of who is behind an operation.

The operating model we documented in November 2025 for a suspected state-sponsored campaign has now proliferated across every class of actor we investigated, and public offensive agent frameworks like PentAGI reproduce much of the same scaffolding for anyone who downloads them. We assess that more actors, from lone wolves to organized entities, will continue to adopt them.

Most of these operations were enabled by AI through direct execution or orchestration rather than question and answer: multi-agent frameworks running reconnaissance, exploitation and exfiltration, with humans setting targets and reviewing what came out.

## GTG-20006

Our attribution is consistent with public reporting linking the actor to Midnight Blizzard. They ran operations against military intelligence targets in Ukrainian and European governments, diplomatic and defense organizations, and individuals connected to US foreign policy, through AI-driven workflows covering development, infrastructure, phishing, command and control, and exfiltration.

Their monitoring agents watched security products for detections of their own malware, then autonomously modified and rebuilt it, iterating until the toolkit was undetected. The rebuilt tools were staged from disposable hosts for phishing, ClickFix and DNS hijacking. The human engaged mostly to refine the Claude Code skills driving the workflows.

We identified more than 20 organizations in their planning, reconnaissance and live operations, concentrated in Ukraine and Europe, extending to the Middle East and Asia. Ukraine and drone technology supply chains were a common theme: they bulk-exported the mailboxes of at least two drone component manufacturers and stole a complete SDK for a drone vision system, spending several days recovering its architecture, hardware bill of materials, suppliers, and an unannounced product.

Some targets were reached sideways. They compromised at least three vendors operating hotel guest WiFi and altered DNS records so guest traffic reached their own servers, then staged lures for Windows, Android and iOS malware. They linked victim WhatsApp accounts as companion devices with read receipts suppressed, exporting conversations unnoticed. From a North African government technology authority they took the central account server and exfiltrated more than 300,000 national identity records and commercial registry data on more than half a million companies. A Microsoft 365 token theft campaign yielded mail records from at least eight organizations.

Defenders once imposed cost by publishing a detection and slowing the attacker's tempo. AI has inverted that cost: at least in theory, capable adversaries can now close the loop faster than defenders can build and deploy the detections meant to stop them.
