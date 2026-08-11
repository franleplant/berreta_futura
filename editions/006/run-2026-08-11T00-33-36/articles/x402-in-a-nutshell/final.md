---
source_ids:
- launching-the-x402-foundation-with-coinbase-and-25f85626
- announcing-the-monetization-gateway-charge-for-a-cb51fdc1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

**The thirty second version.** HTTP has always had a status code nobody used: 402, Payment Required. Sites on Cloudflare emit over a billion of them a day and none are heard, because nobody agreed what they should say. x402 is the agreement. A client asks for a resource. The server answers 402 with a price and an address. The client pays, asks again, and attaches the proof. The server hands over the resource. No account, no API key, no checkout page. The payment is the credential.

## One example, held throughout

A page of tide tables. Updated hourly, useful, worth about a tenth of a cent to whoever needs it. It could never be sold to a person: the card fee would swallow the price many times over. So it was given away and paid for with advertising, and advertising is aimed at eyes. Agents have no eyes.

## The handshake

The agent requests the tide table. The server replies 402, with the amount, the asset, and where to pay. The agent pays and repeats the request with the receipt in a header. A facilitator verifies it. The server returns 200, the page, and a header confirming the payment.

Four moves inside ordinary HTTP. No redirect, no separate payment API. The amounts can be tiny because the protocol adds almost nothing to carry them. The buyer needs no prior relationship with the seller. x402 is rail agnostic, but stablecoins fit it: under a second to settle, a fraction of a cent in fees, no chargebacks.

## When settlement should wait

A crawler reading a hundred thousand pages does not want a hundred thousand payments, and a seller may want room for disputes. So we proposed a deferred scheme: the client signs a commitment now and money moves later. The signature uses HTTP Message Signatures, with the public key in a hosted directory and an id threading the request to the eventual bill. Trust is established at once; settlement happens at the end of the day, batched, subscribed, or on a traditional rail. Pay per crawl already works this way. We are proposing its shape back into the protocol.

## Where it runs

In the Agents SDK, a tool is marked paid by giving it a price. On the client side, a wrapper decides whether to pay silently or ask the human first. That is the whole change to your code.

The Monetization Gateway takes it wider. Any asset behind Cloudflare, page, dataset, API, or MCP tool call, can carry a rule: charge on this route, charge variably by cost, or answer unauthenticated callers with 402 instead of 401. The rules live in the dashboard or in Terraform. Verification happens at the edge, near the buyer, so your origin never sees an unpaid request and never becomes a payments company.

## What changes

For thirty years the web traded content for attention, and attention was sold. The agent brings none. It reads once, takes what it needs, and leaves. It also carries a wallet and will spend it thousands of times an hour without complaint.

So the unit of sale stops being the seat and the month, and becomes the request, the token, the outcome. Our tide table now has a market: not readers, but the routing software, the fishing app, the trading agent, each paying a tenth of a cent and each paying instantly. Nothing about the page changed. What changed is that the request became the transaction.
