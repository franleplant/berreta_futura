---
source_ids:
- launching-the-x402-foundation-with-coinbase-and-25f85626
- announcing-the-monetization-gateway-charge-for-a-cb51fdc1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

Every day, sites on Cloudflare send over a billion HTTP 402 "Payment Required" responses to bots and crawlers. Those responses too often go unheard. x402, an open protocol authored by Coinbase, gives that status code a common language: the server names a price, the client pays inside the request, and the resource comes back. There is no account, no subscription, and no API key. We are building it with a coalition of more than 25 industry leaders through the x402 Foundation. Our Agents SDK and MCP integrations already support it. The Monetization Gateway will let Cloudflare customers charge for any resource behind Cloudflare.

### The example

Take a hypothetical weather service, Rainmeter, at `example.com`. It sells one thing: a forecast from `/api/forecast`, at one cent per request. Its buyers are agents, not people.

### Why 402 went unheard

Web payments were designed for humans. We add items to a cart, type a card number, and click "Pay." An agent does not look at ads or keep a monthly subscription to every tool it uses. It reads a page once, takes what it needs, and moves on. AI crawlers already request content anywhere from a hundred to tens of thousands of times for every visitor they send back.

Old payment rails could not serve an unverified buyer for a sub-cent sale. They cost too much and took too long to settle. Below a certain price, collecting the payment cost more than the payment was worth. The 402 code existed, but nobody had specified how to format it or answer it.

### The exchange

An agent wants tomorrow's rain:

- It sends `GET /api/forecast`.
- Rainmeter answers `402 Payment Required`. The body states the price, the accepted asset, and where to pay.
- The agent pays and repeats the request with a payment authorization header.
- A facilitator verifies the payment payload and settles the transaction.
- Rainmeter returns the forecast, with a payment response header confirming the outcome.

All of this happens inside ordinary HTTP. There is no redirect to a checkout page. Settlement is peer-to-peer, so the cent lands in Rainmeter's wallet.

Two properties fit machines. Amounts can be fractions of a cent, because the protocol adds almost no overhead. And the buyer needs no account with the seller, because the payment itself is the credential. x402 is rail agnostic, but it is a natural fit for stablecoins, which can settle in under a second for a fraction of a cent with zero chargebacks.

### Deferred payment

Crawlers often need two things banks already provide: delayed settlement for disputes, and one aggregated bill. Crawlers in our private beta of pay per crawl are charged a single fee at the end of each day.

We are proposing a deferred scheme for x402. The server's 402 offer lists `"scheme": "deferred"` with an id and a terms URL. The client resends the request signed with HTTP Message Signatures, its public key published in JWK format in a hosted directory. The server checks the signature, attributes the payment to the signer's account, and returns `200 OK` with a `Payment-Response` header. No blockchain is involved. The id then serves as the reference for settlement, which can be rolled up daily, by subscription, or in batches, over traditional rails or stablecoins.

A hypothetical crawler reading Rainmeter's archive a thousand times a day could sign each request and settle once. We will bring this scheme to pay per crawl as the beta grows.

### Agents and MCP today

Agents built with our Agents SDK can pay for resources with x402. MCP servers can expose paid tools: `withX402` wraps the server, and `paidTool` sets a price per call. On the client, `withX402Client` wraps the tool call. Its confirmation callback asks a human before paying, or it can be `null` so the agent pays automatically. The x402 playground shows this live. It creates a wallet funded with testnet USDC on a Base testnet.

### The Monetization Gateway

The Gateway will let Cloudflare customers charge for web pages, datasets, APIs, and MCP tools. You will write rules as expressions, in the dashboard or as code through the API and Terraform. Payment will be verified at the edge, across 330+ cities, before the request reaches your origin.

Planned capabilities include:

- Per-route pricing, such as $0.01 for every GET or POST to `/api/premium/*`.
- Variable pricing, such as image generation charging up to $2 depending on compute.
- Turning an origin's 401 "Unauthorized" into a 402 with price and instructions.

At launch, payments will settle in stablecoins. Sellers will be able to spend them or redeem them for fiat. You can also require agents to authenticate with Web Bot Auth.

With the Gateway, Rainmeter would build no payment code. It would write one rule: $0.01 per GET to `/api/forecast`. The handshake would happen near the buyer, and the origin would see only paid requests. The waitlist is open now.

### Where this goes

We see agents carrying wallets and buying datasets, API calls, tools, and compute without a person in the loop. Some resources will be free. Some will require verified identity, and many will require identity and payment both. Cloudflare can verify the agent, apply the rule, and check the payment inside a single request. That is the business model we are building to power.
