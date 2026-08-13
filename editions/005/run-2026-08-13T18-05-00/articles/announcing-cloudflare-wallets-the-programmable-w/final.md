---
source_ids:
- announcing-cloudflare-wallets-the-programmable-w-97d2eb2e
content_mode: article
label: ARTICLE
---

Agents cannot easily buy things. They have no stable identity to sign up with and no native way to pay, so they hand registration and API keys back to a human and give up. We have created Cloudflare Wallets to fix both. Today you can claim a handle at cloudflare.pay. Later you will be able to fund an Account Wallet, issue Virtual Wallets to your agents with spending guardrails, and pay for APIs and content over x402 micropayments. The handle also gives an agent an optional, human-readable identity, so a merchant can see whose agent it is.

## Two wallets

Account Wallets are for the humans who own Cloudflare accounts: add funds, delegate spend, withdraw.

Virtual Wallets are for agents and work through API keys. An agent spends within its permissions, capped by the limit its Account Wallet owner sets: an allowance, an allow list, a maximum transaction size. The agent acts without asking each time, and cannot overspend.

## Why caps are freedom

Micropayments let an agent try an API with no account at all, so it can do the thing agents are good at: survey dozens of services and pick one. If an agent holds $10, you worry less than if it holds $1,000, and at a few cents a call, $10 buys a wide search. The fence is what lets you open the gate.

Once a service is chosen, the Account Wallet's policies become cost controls. Want every employee on a $100 weekly budget for inference? Fund one Account Wallet, issue Virtual Wallets under that rule. Whoever exceeds it can request a manual override from an authorized human.

The aim is policies firm enough to run unwatched. When spending accelerates oddly, a human reviews it: raise the limit and approve a one-time injection if it was intended, or note that the caps did their job if it was not. We will begin with simple onramps and offramps in supported geographies, with self-funding via stablecoins for eligible users.

## Identity as a name for a keypair

Delegation is invisible to the merchant. An agent arrives and you know nothing about it, though it acts for someone. That breaks old habits: a free week or signup credit is easy to give a person, hard to give an agent with no stable identity when one person can spin up dozens.

Linking wallets to accounts through cloudflare.pay lets an agent identify itself as a delegate. A research agent might live at research.example.cloudflare.pay. Declaring is optional; whether to prefer known agents is the merchant's call.

We expect agents to be treated as VPNs are. Unidentified is not untrustworthy, but it must prove more. Web Bot Auth already registers an agent's identity as a keypair; the wallet ID makes that keypair readable, as DNS pairs a name to an address. We are not defining a schema or a verification system. As the x402 Foundation's schemas develop, we intend to adopt them and encourage others to do so.

## What it adds up to

Monetization Gateway lets sellers get paid without payment infrastructure. Wallets let buyers pay headlessly through agents. Identity lets merchants know, or require to know, who is buying. Together, a headless marketplace. You can claim your handle now.
