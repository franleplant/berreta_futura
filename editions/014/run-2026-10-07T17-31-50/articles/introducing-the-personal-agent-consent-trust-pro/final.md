---
source_ids:
- introducing-the-personal-agent-consent-trust-pro-5acfcaa5
content_mode: verbatim
label: VERBATIM
---

Today, we’re open-sourcing the [Personal Agent Consent & Trust Protocol (PACT)](https://openpactprotocol.org/), co-developed and supported by Instinct. We’re also excited to join the Personal Agent Protocol working group announced by the team behind Meta’s Muse to help shape an industry standard.

Personal agents like Muse, Instinct, and dots are starting to book travel, manage purchases, and resolve issues on their users’ behalf. As they contact businesses, they increasingly encounter AI agents acting for those businesses. PACT gives these interactions explicit, verifiable customer permissions. Built on the Agent2Agent protocol and OAuth 2.0, it lets businesses verify whom a personal agent represents and what that customer has authorized it to do.

Last week, we introduced [Personal Agent Gateway](https://decagon.ai/blog/personal-agents-are-here) and the principles behind it. In this post, we walk through how PACT works and the design decisions that shaped it.

## How PACT works

[Introducing PACT](https://www.youtube.com/embed/dnaAvcLIPnA)

PACT involves three parties: the customer’s personal agent, the business, and the provider (such as Decagon) that hosts the business’s agent. It separates the identity of the personal agent from its authority to act on a customer’s account. The interaction follows three steps.

**1. Discover and connect**

The personal agent discovers the business’s [A2A Agent Card](https://a2a-protocol.org/latest/specification/#8-agent-discovery-the-agent-card), which advertises its endpoint, authentication requirements, and available permissions. Each business defines its own scopes, such as orders:read or orders:cancel, with descriptions the personal agent can use to select the permissions it needs.

The personal agent authenticates its requests with a short-lived, signed JWT. The provider verifies the signature against the personal agent’s published public keys. This establishes which platform is calling, but does not yet prove ownership of a customer account.

**2. Authenticate the customer and obtain consent**


For delegated account access, the personal agent requests scopes through OAuth’s device authorization flow and presents the customer with a login link. The customer signs in directly with the business, then chooses which permissions to approve. The personal agent never handles the customer’s login credentials.

The provider issues a short-lived, signed delegation token binding the verified customer account, personal-agent platform, target business, and approved scopes.

**3. Act within the granted permissions**


Each subsequent request carries both the personal agent’s identity and the customer’s delegation. The provider verifies the agent’s identity and delegated authorization before running the business’s agent within the approved scopes. The business’s policies continue to govern which actions are allowed.

If the conversation requires additional permission, PACT uses A2A’s authorization-required state to request it and continue the same conversation. Replies under delegated authorization include signed receipts recording the scopes used and actions taken.

## Design decisions

- **Route requests through the business’s agent.** Personal agents express what the customer wants; the business’s agent handles the underlying tools and workflows under the business’s policies.
- **Build on existing standards.** Reuse A2A for communication and OAuth for authorization, specifying how they work together.
- **Separate identity from authority.** Verify which agent is calling independently of what the customer has permitted it to do.
- **Let businesses define permissions.** Standardize how scopes are discovered and granted while leaving capabilities and policies to each business.
- **Keep login with the business.** Bind consent to a verified customer account without exposing login credentials to the personal agent.

## An open standard

Personal agents need to work across businesses, and businesses need to serve customers using different personal agents. Without a shared specification for this interaction, developers must reconcile differences in how providers identify agents, obtain customer consent, and carry authorization with each request.

PACT makes those mechanics consistent across implementations. Personal-agent developers can use the same integration pattern across participating providers, while businesses can support different personal agents through a common interface. The customer’s choice of personal agent shouldn’t depend on which platform a business uses.

We built PACT in collaboration with Instinct to bring both sides of the interaction into its design. By publishing the specification openly, we’re inviting other personal-agent developers, businesses, and agent platforms to implement it and help shape its evolution.

To get started, read the [PACT specification](https://openpactprotocol.org/spec), or explore the code and share feedback on [GitHub](https://github.com/openpactprotocol/openpactprotocol).
