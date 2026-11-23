---
source_ids:
- building-an-accounting-team-with-grok-bot-1475c813
content_mode: article
label: ARTICLE
---

At SpaceXSI, five Grok Bots each own one accounting job from start to finish, from setting up a customer's account to collecting payment. They involve us only when the work needs judgment or approval. They're letting us handle more work without growing headcount at the same rate. The biggest lesson from our experience: building an AI team needs the same attention as building a human one. We define the job, document it, and train the Bot before it works alone.

## How we build our Bots

We give each Bot an existing, well-defined process to own end to end, not a scattering of tasks. One common misconception is that an agent can do a job as soon as it has access to the right systems. In practice, Bots need the same documentation, onboarding, and coaching as new employees. That takes time upfront; once trained, they work around the clock and handle far more volume with greater accuracy than a person doing the same job.

**Fix the process first.** A Bot will struggle to run a process people haven't already learned to perform reliably; giving a poorly defined workflow to a Bot won't mend it. So we build applications that define how each process works and what actions are permitted. The Bot gets a controlled environment, and people and Bots share a logged audit trail.

**Write the manual.** Each Bot has a Notion operating manual. Every night it rereads it and flags discrepancies with its instructions, but it cannot edit it. Only the people responsible for the process can.

**Limit permissions.** Bots can read what they need; their ability to change records is more restricted. Lower-risk tasks run independently. Credits and refunds require approval, and only designated people can authorize changes to billing records.

**Train in stages.** Onboarding now takes about three weeks. In week one, the Bot builds its knowledge base and watches us work. In week two, it proposes actions and a person approves them. In week three, it executes routine work and escalates exceptions. Our first Bots took longer: Billing Support Bot took four to five weeks. We keep coaching them after launch.

## What each Bot does

**Provisioning Bot** compares each executed contract with the CRM, enables the account through our provisioning application, verifies the entitlements, and tells the sales rep in Slack. When a contract ends, it removes access.

**Billing Bot** checks the billing system against the contract, corrects discrepancies there, alerts the team to fix the CRM record, and sends the invoice. Issuing one has gone from roughly 24 hours to minutes. If a VAT or GST number is missing, it gives the sales rep 24 hours to provide it before the invoice goes out, rather than after the customer asks.

**Billing Support Bot** answers our go-to-market team's billing questions, such as why an invoice differs from the usage dashboard, and makes routine updates, such as changing billing emails after checking that they match the customer's domain. We estimate it has freed up approximately eight hours a day across our team's work.

**Cash Applications Bot** checks the payment feed twice daily, applies exact matches, searches our support system for remittance advice when a payment doesn't match, writes off bank fees, and flags short payments to collections. This ordinarily takes an accountant three to four hours. The Bot takes roughly 30 minutes.

**Collections Bot** is the first to talk to customers. It monitors the accounts receivable inbox and coordinates refunds with Billing Bot and Cash Applications Bot; an authorized person must approve before a refund is processed. We spent approximately three months training it, because customer contact adds security requirements. It checks the sender's email against approved contacts in the CRM and billing system. A similar-looking domain isn't sufficient. If they don't match, it escalates to a person.

## Where this leaves us

Without Grok Bot, we estimate the work assigned to these five Bots would require more than doubling our team's headcount. Instead, Bots handle routine processes, and our accountants manage the work, improve the systems, and resolve exceptions.
