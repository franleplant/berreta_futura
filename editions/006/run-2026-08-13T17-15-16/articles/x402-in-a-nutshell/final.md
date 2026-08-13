---
source_ids:
- launching-the-x402-foundation-with-coinbase-and-25f85626
- announcing-the-monetization-gateway-charge-for-a-cb51fdc1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

Payments on the web were built for humans: a cart, a card, a click. Agents do not browse. They fetch a page or a data feed once, take what they need, and move on. x402, a protocol Coinbase authored and we are building on with a coalition of more than 25 industry leaders via the x402 Foundation, gives that transaction a common language. The client asks. The server answers `402 Payment Required` with a machine readable price. The client pays and asks again. A facilitator verifies, and the resource is served. No account, no subscription, no API key. Every day, sites on Cloudflare send over a billion 402s to bots and crawlers; until now those responses had no standard way to say what was wanted.

## One example, carried through

Imagine a small site, Harbor Tides, that publishes tide tables. It wants a tenth of a cent per lookup. An agent planning a fishing trip needs Thursday's high water.

The agent requests the table. Harbor Tides returns 402 with a payload naming the amount and the recipient. The agent re-sends the request with a payment authorization header. The facilitator verifies the payload and settles. Harbor Tides returns the table with a payment response header confirming the outcome. The whole exchange happens inside ordinary HTTP. There is no redirect to a checkout page.

Two properties make this work at that size. The amounts can be fractions of a cent, because the protocol adds almost no overhead. And the buyer needs no account with the seller, because the payment itself is the credential. x402 is rail agnostic, and stablecoins fit it well: settlement in under a second for a fraction of a cent, with zero chargebacks.

## The deferred scheme we proposed

Some buyers do not want to settle each request. A crawler reading the whole Harbor Tides archive would rather be billed once at the end of the day, and the site may want time for disputes.

So we proposed a new **deferred** scheme for x402. The server's 402 offers it; the client re-requests with an HTTP Message Signature, its public key published in JWK format in a hosted directory; the server validates the signature, attributes the payment to the associated account, and serves the content. There is no blockchain in that path. The validated `id` becomes the reference, and settlement can be rolled up on a subscription, daily, or batch basis. This is a proposal for the next major version of the protocol. We will be bringing it to pay per crawl as we expand and evolve the private beta.

## What you can use today

Agents built with our Agents SDK can pay for resources with x402, and MCP servers can expose paid tools: a price, a schema, a handler. When the agent hits a paid tool, it reads the 402 and can prompt the human, or pay automatically if the confirmation callback is set to null. The x402 playground shows the loop end to end, funding a fresh wallet with Testnet USDC on a Base testnet.

## What we are building

Harbor Tides still has to run the payment machinery itself. The Monetization Gateway, announced with a waitlist now open, is meant to remove that. It will let customers charge for any asset behind Cloudflare, whether a page, a dataset, an API, or an MCP tool call, by writing an expression rather than a billing system: $0.01 on every GET or POST to `/api/premium/*`, a variable charge up to $2 for image generation, or a 401 from the origin turned into a 402 with prices attached. Rules will live in the dashboard, the API, or Terraform. Verification will happen at the edge across 330+ cities, keeping the handshake near the buyer and the volume off the origin. At launch, payments will settle in stablecoins.

The wager behind it is that agents become the primary buyers on the Internet, and that the request becomes the transaction.
