---
source_ids:
- announcing-cloudflare-wallets-the-programmable-w-97d2eb2e
content_mode: article
label: ARTICLE
---

An agent that wants to try a new API hits a wall built for humans: a login page, a payment method, an API key. It gives up and asks a person. Today we are opening Cloudflare Wallets. You claim a handle at cloudflare.pay. Your account holds the money; each agent gets a Virtual Wallet with an allowance, an allow list, and a ceiling. Payments ride on HTTP requests through x402, in stablecoins, without an account at the far end. The handle also gives the agent a name a merchant can read.

## The wall

Two things an agent lacks: a fixed identity to register with, and a way to pay. Lacking both, it cannot onboard, and so it cannot compare. Commerce between machines stalls at the sign-up form.

## Two kinds of wallet

An Account Wallet belongs to a person. They add funds, delegate spend, and take funds out.

A Virtual Wallet belongs to an agent and works through an API key. The agent spends inside its permissions; the ceiling is the one its owner set. No approval is needed for each purchase, and no single mistake can drain the account.

Last month we announced Monetization Gateway, which lets our customers sell content, data, and inference headlessly. That is the selling half. Wallets are the buying half.

## Small money buys freedom

The caps look like restraints. They are the opposite. An agent trusted with ten dollars can be left alone; an agent trusted with a thousand cannot. If a call costs a few cents, ten dollars will survey a hundred services — the whole catalogue read through, which is what agents are good at.

Set the policy once. A hundred dollars a week for each employee's inference: one Account Wallet, one rule, one Virtual Wallet per person. When spending runs strangely fast, a human looks. If it was meant, raise the limit or send more funds. If it was not, the cap has already done the work.

## A readable name for a keypair

A merchant meeting an agent today learns nothing about it. Free trials and sign-up credits assume one visitor is one customer, and one person can raise a dozen agents.

Linking a wallet to an account fixes that, if the agent chooses. A research agent can live at research.example.cloudflare.pay, and a merchant can see whose delegate it is. Declaring is optional; so is caring.

Web Bot Auth already lets an agent register a keypair. We are adding a name a person can remember, as DNS did for addresses — no schema, no verification system, just the pairing. Unidentified is not untrustworthy; it only has more to prove.

Claim your handle at cloudflare.pay.
