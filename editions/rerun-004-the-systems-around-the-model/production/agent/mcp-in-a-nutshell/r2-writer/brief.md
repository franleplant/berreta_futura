# In-a-nutshell prompt

You are the Teacher. You explain one topic to a reader who has never met it,
well enough that they can explain it to a colleague the same afternoon. You are
not summarizing a specification. You are teaching its principles. Your inputs
are the source extraction or extractions: a specification, a documentation set,
or a repository capture.

## Procedure

Steps 1 and 2 are working notes. Step 1's six questions are also returned beside
the manuscript (see Format); nothing else from either step reaches the page.

1. Answer four questions before writing:
   - What problem does this exist to solve? Use the source's history where it
     tells one. Where it does not, state the problem structurally, as what
     someone would otherwise do by hand: hard rule 5 outranks this question, so
     never reconstruct a history the source never told.
   - What is the mental model, in two or three plain sentences?
   - Which single concrete scenario can carry the entire piece?
   - What six things must the reader be able to answer at the end? Write them as
     questions, not topics, and keep them.
2. Fix the running example. One scenario, named and specific. Every section
   returns to it.
3. Teach in this order: the problem; the mental model in plain words, before
   any spec vocabulary; the parts, each introduced by what it does in the
   running example and only then named; one end-to-end walkthrough of that
   example; the boundary, meaning what this deliberately does not do and what
   that buys you. Merge freely, because five headings in a row is the table of
   contents hard rule 2 bans, and the boundary usually belongs inside the
   walkthrough. What may not move: the mental model precedes the vocabulary,
   and the walkthrough precedes the boundary.
4. Introduce spec vocabulary only after the concept it names, in the same
   sentence. Concept first, term second.
5. Edit with the method in `docs/WRITING_RULES.md`.

## Hard rules

- The mental model appears within the first 150 words. Never at the end.
- Never mirror the source's own table of contents. Headings state ideas: "Why
  one connector per tool did not scale", not "Architecture overview".
- One running example throughout. A second only to draw a contrast the first
  cannot, and only once.
- No enumeration of method names, field names, or API surface. A method name
  appears only inside a sentence, where the reader needs to recognize it in the
  wild, never as a section's subject or in a list.
- Every claim must be traceable to the source. Traceable means supported, not
  quoted: restating, joining two stated facts, and drawing the conclusion the
  source's material forces are yours to do, and a true sentence is not worth
  losing because no single passage contains it. Adding a fact, number, example,
  or consequence the source does not support is not.
- You may name the source artifact: "the specification calls this elicitation"
  is how a reader recognizes the term in the wild. The banned scaffolding is
  attribution to a person ("the author argues"), not naming a document.
- Observe the banned tics in `docs/WRITING_RULES.md`, including the antithesis
  close "It is not X. It is Y."

## Anti-exemplar

`editions/004-the-systems-around-the-model/articles/mcp-in-a-nutshell.md` is the
failure this prompt exists to prevent. Its headings mirror the specification's
contents ("Two layers", "The three server primitives"), its body recites
`tools/list` instead of principles, it runs the VS Code and Sentry example in
two sections, and the only passage that teaches anything, the last section on
who owns what, is the final 120 words. There is where it should have started.

## Length and format

The page cap in `edition.yaml` (`format.max_article_pages`, seven A5 reader
pages including the opener illustration, title, and credit) is the only length
that counts, and only the renderer can measure it: `mag fit <edition-id>`. Around
a thousand body words is the usual landing point, a sighting not the contract.

```
---
source_ids:
- <source-id>                     # one entry per source, always a list
content_mode: in_a_nutshell
label: IN A NUTSHELL
---
```

`content_mode: in_a_nutshell` identifies this piece as the edition's explainer
to every downstream judge. The voice is the magazine's own, so the article's
`edition.yaml` row carries an editor byline; title, byline, and the
`source_body_sha256` pins all live in that row, not here. The body follows the
closing `---` and must begin with a paragraph, never a heading, so the
illustrated opener can set it. Use `##` for section headings; no H1.

Return step 1's six questions beside the manuscript as their own block, so the
operator can hand the writer's model of comprehension to the novice-persona
judge rather than letting it die with the draft:

```yaml
comprehension_questions:
- What boundary does the protocol define?
```

## Working notes

End your reply with a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

and put your working notes below it: the reader's model you built the piece around, the running example you chose and the ones you rejected, and the six comprehension questions. Everything above that line is the
manuscript and is written to disk as it stands; everything below it is stripped
before the file is written and is never shown to a judge or to a reader.

Write the notes for the person who revises this piece next, which may be you in
another session. A review finding names the sentence where a defect *surfaces*;
your notes are usually the only record of where it was *made*, and a reviser
working from findings alone can patch a symptom without ever finding its cause.
Say what you decided, what you cut and why, and which choices the piece is
resting on.

## How this will be judged

- A novice-persona judge writes six comprehension questions from the source,
  then answers them closed-book from this piece alone. Fewer than five of six
  correct blocks it. Your six are supplied to her alongside her own.
- A fact-checker reads the manuscript against the source claim by claim.
- A line editor checks the running example, heading quality, the position of the
  mental model, and the house style in `docs/WRITING_RULES.md`.

---

# The assignment

The prompt above governs. This section names the piece, supplies its complete inputs, and states the output contract.

- Edition: `rerun-004-the-systems-around-the-model` (The Systems Around the Model)
- Piece id: `mcp-in-a-nutshell`
- content_mode: `in_a_nutshell`
- Title: MCP in a Nutshell
- Byline: The editors
- Page budget: 7 rendered A5 reader page(s)

## Source extractions

1 extraction(s), each complete. You are drafting the whole piece in this one pass from all of it: nothing else will be sent, and no later call will stitch a second half on.

### Extraction `architecture-overview-ce5cb1d1` (637 lines, complete)

```
    About MCP      Architecture overview



About MCP

Architecture overview                                                                          Copy page


This overview of the Model Context Protocol (MCP) discusses its scope and core concepts, and
provides an example demonstrating each core concept.

Because MCP SDKs abstract away many concerns, most developers will likely find the data layer
protocol section to be the most useful. It discusses how MCP servers can provide context to an AI
application.

For specific implementation details, please refer to the documentation for your language-specific
SDK.


Scope
The Model Context Protocol includes the following projects:

    MCP Specification: A specification of MCP that outlines the implementation requirements for
    clients and servers.
    MCP SDKs: SDKs for different programming languages that implement MCP.
    MCP Development Tools: Tools for developing MCP servers and clients, including the MCP
    Inspector
    MCP Reference Server Implementations: Reference implementations of MCP servers.

      MCP focuses solely on the protocol for context exchange—it does not dictate how AI applications use
      LLMs or manage the provided context.




Concepts of MCP
Participants
MCP follows a client-server architecture where an MCP host — an AI application like Claude Code or
Claude Desktop — establishes connections to one or more MCP servers. The MCP host accomplishes
this by creating one MCP client for each MCP server. Each MCP client maintains a dedicated
connection with its corresponding MCP server.

Local MCP servers that use the STDIO transport typically serve a single MCP client, whereas remote
MCP servers that use the Streamable HTTP transport will typically serve many MCP clients.

The key participants in the MCP architecture are:

    MCP Host: The AI application that coordinates and manages one or multiple MCP clients
    MCP Client: A component that maintains a connection to an MCP server and obtains context from
    an MCP server for the MCP host to use
    MCP Server: A program that provides context to MCP clients

For example: Visual Studio Code acts as an MCP host. When Visual Studio Code establishes a
connection to an MCP server, such as the Sentry MCP server, the Visual Studio Code runtime
instantiates an MCP client object that maintains the connection to the Sentry MCP server. When Visual
Studio Code subsequently connects to another MCP server, such as the local filesystem server, the
Visual Studio Code runtime instantiates an additional MCP client object to maintain this connection.

                                          MCP Host (AI Application)
        MCP Client 1                MCP Client 2                      MCP Client 3           MCP Client 4



        Dedicated                    Dedicated                        Dedicated               Dedicated
        connection                   connection                       connection              connection


    MCP Server A - Local         MCP Server B - Local                        MCP Server C - Remote
     (e.g. Filesystem)             (e.g. Database)                               (e.g. Sentry)


Note that MCP server refers to the program that serves context data, regardless of where it runs. MCP
servers can execute locally or remotely. For example, when Claude Desktop launches the filesystem
server, the server runs locally on the same machine because it uses the STDIO transport. This is
commonly referred to as a “local” MCP server. The official Sentry MCP server runs on the Sentry
platform, and uses the Streamable HTTP transport. This is commonly referred to as a “remote” MCP
server.
Layers
MCP consists of two layers:

    Data layer: Defines the JSON-RPC based protocol for client-server communication, including
    capability and version discovery, and core primitives, such as tools, resources, prompts and
    notifications.
    Transport layer: Defines the communication mechanisms and channels that enable data exchange
    between clients and servers, including transport-specific connection establishment, message
    framing, and authorization.

Conceptually the data layer is the inner layer, while the transport layer is the outer layer.


Data layer
The data layer implements a JSON-RPC 2.0 based exchange protocol that defines the message
structure and semantics. This layer includes:

    Discovery: Lets clients query a server’s supported protocol versions, capabilities, and identity
    through the server/discover request
    Server features: Enables servers to provide core functionality including tools for AI actions,
    resources for context data, and prompts for interaction templates from and to the client
    Client features: Enables servers to elicit input from the user. Sampling is deprecated as of
    protocol version 2026-07-28 .
    Utility features: Supports additional capabilities like notifications for real-time updates and
    progress tracking for long-running operations


Transport layer
The transport layer manages communication channels and authentication between clients and
servers. It handles connection establishment, message framing, and secure communication between
MCP participants.

MCP supports two transport mechanisms:

    Stdio transport: Uses standard input/output streams for direct process communication between
    local processes on the same machine, providing optimal performance with no network overhead.
    Streamable HTTP transport: Uses HTTP POST for client-to-server messages with optional
    Server-Sent Events for streaming capabilities. This transport enables remote server
    communication and supports standard HTTP authentication methods including bearer tokens, API
    keys, and custom headers. MCP recommends using OAuth to obtain authentication tokens.

The transport layer abstracts communication details from the protocol layer, enabling the same JSON-
RPC 2.0 message format across all transport mechanisms.


Data Layer Protocol
A core part of MCP is defining the schema and semantics between MCP clients and MCP servers.
Developers will likely find the data layer — in particular, the set of primitives — to be the most
interesting part of MCP. It is the part of MCP that defines the ways developers can share context from
MCP servers to MCP clients.

MCP uses JSON-RPC 2.0 as its underlying RPC protocol. Client and servers send requests to each
other and respond accordingly. Notifications can be used when no response is required.


Statelessness and discovery
MCP is a stateless protocol. Every request carries the protocol version and the capabilities relevant to
that request in its _meta field, so the server can process each request on its own. Clients should also
identify themselves in the same field unless configured not to. Servers advertise their supported
versions and capabilities through the mandatory server/discover request, which clients may send
before any other request. Detailed information can be found in the specification, and the example
showcases the per-request metadata and the discovery sequence.


Primitives
MCP primitives are the most important concept within MCP. They define what clients and servers can
offer each other. These primitives specify the types of contextual information that can be shared with
AI applications and the range of actions that can be performed.

MCP defines three core primitives that servers can expose:

    Tools: Executable functions that AI applications can invoke to perform actions (e.g., file
    operations, API calls, database queries)
    Resources: Data sources that provide contextual information to AI applications (e.g., file contents,
    database records, API responses)
    Prompts: Reusable templates that help structure interactions with language models (e.g., system
    prompts, few-shot examples)
Each primitive type has associated methods for discovery ( */list ), retrieval ( */get ), and in some
cases, execution ( tools/call ). MCP clients will use the */list methods to discover available
primitives. For example, a client can first list all available tools ( tools/list ) and then execute them.
This design allows listings to be dynamic.

As a concrete example, consider an MCP server that provides context about a database. It can expose
tools for querying the database, a resource that contains the schema of the database, and a prompt
that includes few-shot examples for interacting with the tools.

For more details about server primitives see server concepts.

MCP also defines primitives that clients can expose. These primitives allow MCP server authors to
build richer interactions.

    Elicitation: Allows servers to request additional information from users. This is useful when server
    authors want to get more information from the user, or ask for confirmation of an action. Servers
    request user input with the elicitation/create method.

Elicitation requests are delivered through the Multi Round-Trip Requests pattern, explained in the
elicitation overview.

Deprecated: The following client primitives are deprecated as of protocol version 2026-07-28 .

    Sampling: Allows servers to request language model completions from the client’s AI application.
    This is useful when server authors want access to a language model, but want to stay model-
    independent and not include a language model SDK in their MCP server. Servers request
    completions with the sampling/createMessage method, also delivered through the Multi Round-
    Trip Requests pattern. New implementations should integrate directly with LLM provider APIs.
    Logging: Enables servers to send log messages to clients for debugging and monitoring
    purposes. New implementations should log to stderr (stdio transport) or use OpenTelemetry.

For more details about client primitives see client concepts.

Besides server and client primitives, the protocol supports optional extensions that build on the core
protocol. For example, the Tasks extension lets servers return a durable handle for long-running
requests, so clients can poll for status and retrieve the result later.


Notifications
The protocol supports real-time notifications to enable dynamic updates between servers and clients.
For example, when a server’s available tools change (such as when new functionality becomes
available or existing tools are modified), the server can send tool update notifications to inform
connected clients about these changes. Notifications are sent as JSON-RPC 2.0 notification messages
(without expecting a response). Change notifications are opt-in: the client opens a long-lived
 subscriptions/listen stream naming the notification types it wants to receive, and the server
delivers matching notifications on that stream.


Example
Data Layer
This section provides a step-by-step walkthrough of an MCP client-server interaction, focusing on the
data layer protocol. We’ll demonstrate discovery, tool operations, and notifications using JSON-RPC
2.0 messages.


 1    Discovery

      As described in the statelessness and discovery section, every MCP request carries the
      protocol version and client capabilities in its _meta field, and clients should also include their
      identity there. A client that wants to learn what a server supports before issuing other requests
      sends a server/discover request, which every server must implement. The discovery
      response is typically cacheable, meaning it can be re-used so the discovery flow does not need
      to be performed for every request.
  Discover Request   Discover Response

  {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "server/discover",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientInfo": {
            "name": "example-client",
            "version": "1.0.0"
          },
          "io.modelcontextprotocol/clientCapabilities": {
            "elicitation": {}
          }
        }
      }
  }



Understanding the Discovery Exchange
The _meta fields and the discovery response together serve several purposes:

 1. Protocol Version Selection: The io.modelcontextprotocol/protocolVersion field
    declares the version the client is speaking on this request, and supportedVersions in the
    response lists the versions the server accepts. If a server does not support the requested
    version, it rejects the request with an UnsupportedProtocolVersionError listing the
    versions it does support, and the client retries with a mutually supported version.
 2. Capability Discovery: The client declares its capabilities in
      io.modelcontextprotocol/clientCapabilities on every request, and the server returns
    its own capabilities object from server/discover . This tells each party which
    primitives the other can handle (tools, resources, prompts) and whether change
    notifications are available, so unsupported operations are never attempted.
 3. Identity Exchange: The io.modelcontextprotocol/clientInfo field in the request’s
     _meta and the io.modelcontextprotocol/serverInfo field in the result’s _meta
    provide identification and versioning information for debugging and compatibility
    purposes.

In this example, the exchange demonstrates how MCP capabilities are declared:
    Client Capabilities:

         "elicitation": {}         - The client declares it can gather additional input from the user when
        the server requests it

    Server Capabilities:

         "tools": {"listChanged": true}   - The server supports the tools primitive and can honor
        a toolsListChanged filter in subscriptions/listen . Clients that request this filter
        receive notifications/tools/list_changed when the tool list changes.
         "resources": {} - The server also supports the resources primitive (can handle
         resources/list and resources/read methods)

    Calling server/discover is optional. Because every request carries the same _meta fields, a
    client is free to send any request directly and handle a version error if one comes back.
    Discovery is a convenient way to fetch the server’s identity, capabilities, and supported versions
    in a single request.


    How This Works in AI Applications
    The AI application’s MCP client manager connects to configured servers and stores their
    discovered capabilities for later use. The application uses this information to determine which
    servers can provide specific types of functionality (tools, resources, prompts) and whether they
    support real-time updates. In the Python SDK, discovery happens while the client connects. The
    results are then available on the client object.

      Pseudo-code for AI application discovery

      # Pseudo Code
      async with Client(stdio_client(server_config)) as client:
          if client.server_capabilities.tools:
              app.register_mcp_server(client, supports_tools=True)
          app.set_server_ready(client)



2   Tool Discovery (Primitives)

    The client can discover available tools by sending a tools/list request. This request is
    fundamental to MCP’s tool discovery mechanism: it allows clients to understand what tools are
    available on the server before attempting to use them.
  Tools List Request   Tools List Response

  {
      "jsonrpc": "2.0",
      "id": 2,
      "method": "tools/list",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientInfo": {
            "name": "example-client",
            "version": "1.0.0"
          },
          "io.modelcontextprotocol/clientCapabilities": {
            "elicitation": {}
          }
        }
      }
  }



Understanding the Tool Discovery Request
The tools/list request requires no parameters beyond the standard _meta fields that
accompany every MCP request. It also accepts an optional cursor parameter for pagination,
which the example above omits.


Understanding the Tool Discovery Response
The response contains a tools array that provides comprehensive metadata about each
available tool. This array-based structure allows servers to expose multiple tools simultaneously
while maintaining clear boundaries between different functionalities.

Each tool object in the response includes several key fields:

       name : A unique identifier for the tool within the server’s namespace. This serves as the
      primary key for tool execution and should follow a clear naming pattern (e.g.,
       calculator_arithmetic rather than just calculate )

       title : A human-readable display name for the tool that clients can show to users

       description : Detailed explanation of what the tool does and when to use it
         inputSchema : A JSON Schema that defines the expected input parameters, enabling type
        validation and providing clear documentation about required and optional parameters

    The result is marked "resultType": "complete" and carries two caching fields. ttlMs is a
    freshness hint in milliseconds, so this tool list can be cached for five minutes. cacheScope
    indicates who may reuse the response. The specification’s caching utility defines the full rules.


    How This Works in AI Applications
    The AI application fetches available tools from all connected MCP servers and combines them
    into a unified tool registry that the language model can access. This allows the LLM to
    understand what actions it can perform and automatically generates the appropriate tool calls
    during conversations.

      Pseudo-code for AI application tool discovery

      # Pseudo-code using MCP Python SDK patterns
      available_tools = []
      for client in app.mcp_clients():
          tools_response = await client.list_tools()
          available_tools.extend(tools_response.tools)
      conversation.register_available_tools(available_tools)



    Clients that federate many servers can use progressive tool discovery rather than loading every
    tool upfront.

3   Tool Execution (Primitives)

    The client can now execute a tool using the tools/call method. This demonstrates how MCP
    primitives are used in practice: after discovering available tools, the client can invoke them with
    appropriate arguments.


    Understanding the Tool Execution Request
    The tools/call request follows a structured format that ensures type safety and clear
    communication between client and server. Note that we’re using the proper tool name from the
    discovery response ( weather_current ) rather than a simplified name:
  Tool Call Request   Tool Call Response

  {
      "jsonrpc": "2.0",
      "id": 3,
      "method": "tools/call",
      "params": {
        "name": "weather_current",
        "arguments": {
          "location": "San Francisco",
          "units": "imperial"
        },
        "_meta": {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientInfo": {
            "name": "example-client",
            "version": "1.0.0"
          },
          "io.modelcontextprotocol/clientCapabilities": {
            "elicitation": {}
          }
        }
      }
  }



Key Elements of Tool Execution
The request structure includes several important components:

 1. name : Must match exactly the tool name from the discovery response
    ( weather_current ). This ensures the server can correctly identify which tool to execute.
 2. arguments : Contains the input parameters as defined by the tool’s inputSchema . In this
    example:
            location : “San Francisco” (required parameter)

            units : “imperial” (optional parameter, defaults to “metric” if not specified)

 3. _meta : Carries the standard per-request fields: the protocol version and client
    capabilities that every MCP request must include, plus the client’s identity, which clients
    should include unless configured not to.
      4. JSON-RPC Structure: Uses standard JSON-RPC 2.0 format with unique id for request-
         response correlation.


    Understanding the Tool Execution Response
    The response demonstrates MCP’s flexible content system:

      1. content Array: Tool responses return an array of content objects, allowing for rich, multi-
         format responses (text, images, resources, etc.)
      2. Content Types: Each content object has a type field. In this example, "type": "text"
         indicates plain text content, but MCP supports various content types for different use
         cases.
      3. Structured Output: The response provides actionable information that the AI application
         can use as context for language model interactions.

    This execution pattern allows AI applications to dynamically invoke server functionality and
    receive structured responses that can be integrated into conversations with language models.


    How This Works in AI Applications
    When the language model decides to use a tool during a conversation, the AI application
    intercepts the tool call, routes it to the appropriate MCP server, executes it, and returns the
    results back to the LLM as part of the conversation flow. This enables the LLM to access real-
    time data and perform actions in the external world.

      # Pseudo-code for AI application tool execution
      async def handle_tool_call(conversation, tool_name, arguments):
          client = app.find_mcp_client_for_tool(tool_name)
          result = await client.call_tool(tool_name, arguments)
          conversation.add_tool_result(result.content)



4   Real-time Updates (Notifications)

    MCP supports real-time notifications that enable servers to inform clients about changes
    without being polled for them. This demonstrates the notification system, a key feature that
    keeps clients synchronized and responsive.


    Subscribing to Changes
Change notifications are opt-in. To receive them, the client opens a long-lived notification
stream by sending a subscriptions/listen request with a notifications filter naming the
event types it wants. Here the client asks for tool list changes:

  Listen Request

  {
      "jsonrpc": "2.0",
      "id": 4,
      "method": "subscriptions/listen",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientInfo": {
            "name": "example-client",
            "version": "1.0.0"
          },
          "io.modelcontextprotocol/clientCapabilities": {
            "elicitation": {}
          }
        },
        "notifications": {
          "toolsListChanged": true
        }
      }
  }



Every client request carries the io.modelcontextprotocol/protocolVersion and
 io.modelcontextprotocol/clientCapabilities fields in _meta , and normally
 io.modelcontextprotocol/clientInfo as well, so the server can identify the client without
relying on connection state.

The server acknowledges the subscription with notifications/subscriptions/acknowledged ,
which is the first message carrying that subscription’s ID in _meta (the server sends no other
notification for that subscription before it). Its notifications field reflects the subset of the
requested filter the server agreed to honor, with unsupported notification types omitted:
  Acknowledgment

  {
      "jsonrpc": "2.0",
      "method": "notifications/subscriptions/acknowledged",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/subscriptionId": 4
        },
        "notifications": {
          "toolsListChanged": true
        }
      }
  }



Understanding Tool List Change Notifications
After the acknowledgment, when the server’s available tools change (for example, when new
functionality becomes available, existing tools are modified, or tools become temporarily
unavailable), the server delivers a notification on that stream:

  Notification

  {
      "jsonrpc": "2.0",
      "method": "notifications/tools/list_changed",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/subscriptionId": 4
        }
      }
  }



Key Features of MCP Notifications
 1. No Response Required: Notice there’s no id field in the notification. This follows JSON-
    RPC 2.0 notification semantics where no response is expected or sent.
 2. Opt-In Based: This notification is only sent to clients that requested "toolsListChanged":
     true in their subscriptions/listen filter, and it is only available from servers that
    declared "listChanged": true in their tools capability (as shown in Step 1).
  3. Subscription-ID Tagging: Every notification on the stream carries
      io.modelcontextprotocol/subscriptionId in _meta . The value is the JSON-RPC ID of
     the subscriptions/listen request that opened the stream ( 4 in this example), so
     clients can correlate each notification with the subscription that produced it.
  4. Event-Driven: The server decides when to send notifications based on internal state
     changes, making MCP connections dynamic and responsive.
  5. Best Effort: There are no guarantees that every notification will be sent or received,
     particularly across transport reconnects. Clients should also rely on polling to preserve
     freshness of results.


Client Response to Notifications
Upon receiving this notification, the client typically reacts by requesting the updated tool list.
This creates a refresh cycle that keeps the client’s understanding of available tools current:

  Request

  {
      "jsonrpc": "2.0",
      "id": 5,
      "method": "tools/list",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientInfo": {
            "name": "example-client",
            "version": "1.0.0"
          },
          "io.modelcontextprotocol/clientCapabilities": {
            "elicitation": {}
          }
        }
      }
  }



Why Notifications Matter
This notification system is crucial for several reasons:
        1. Dynamic Environments: Tools may come and go based on server state, external
           dependencies, or user permissions
        2. Efficiency: Clients don’t need to poll for changes; they’re notified when updates occur
        3. Consistency: Ensures clients always have accurate information about available server
           capabilities
        4. Real-time Collaboration: Enables responsive AI applications that can adapt to changing
           contexts

      This notification pattern extends beyond tools to other MCP primitives, enabling comprehensive
      real-time synchronization between clients and servers.


      How This Works in AI Applications
      The AI application keeps a notification stream open for the changes it cares about. When one
      arrives, it immediately refreshes its tool registry and updates the LLM’s available capabilities.
      This ensures that ongoing conversations always have access to the most current set of tools,
      and the LLM can dynamically adapt to new functionality as it becomes available.

         # Pseudo-code for AI application notification handling
         async def follow_tool_changes(client):
             async with client.listen(tools_list_changed=True) as sub:
                 async for _event in sub:
                     tools_response = await client.list_tools()
                     app.update_available_tools(client, tools_response.tools)
                     if app.conversation.is_active():
                         app.conversation.notify_llm_of_new_capabilities()




Was this page helpful?                                                                 Yes          No



  What is MCP?                                                                                  Servers
                  Copyright © Model Context Protocol a Series of LF Projects, LLC.
For web site terms of use, trademark policy and other project policies please see https://lfprojects.org.
```

## Round 2: revise the draft below

A previous round of this piece was judged and did not pass. Your job is to produce the whole manuscript again, with every defect below gone. Rewrite as much as the repair needs; you are not patching sentences.

### Your predecessor's working notes

These are the notes from the draft below, not a judgment of it. A finding says where a defect *surfaces*; these notes are usually the only way to see where it was *made*. Read them before the findings.

```
## 1. Pre-writing, as the prompt required

**Q1. What did people do before this existed, and what broke?**
The extraction does not answer this. There is no history, no prior art, no
account of bespoke connectors, no combinatorial framing. The nearest material is
the scope note ("MCP focuses solely on the protocol for context exchange") and
the data-layer note that the primitives are "the ways developers can share
context from MCP servers to MCP clients." So I answered in the only form the
source supports: the problem is structural, not historical. A model works on
what is placed in front of it, the material worth placing there lives outside
the application, and somebody has to define the handover. Anything sharper would
have been my own knowledge, which hard rule 5 forbids.

**Q2. The mental model, in two or three plain sentences.**
Two halves and one wire. The AI application owns the model, the conversation and
every decision about what to do with context; the server owns a corner of the
outside world and publishes it as a self-describing menu. Neither side knows how
the other is built, so both announce their capabilities on every request instead
of assuming.

**Q3. The single concrete scenario that carries the piece.**
Visual Studio Code as the host, connected to a server that fronts a database.
Both halves are in the source: VS Code is the source's named example of a host,
and a local database server is named in the participants diagram, with the
source's own worked example of what such a server exposes (query tools, a schema
resource, a few-shot prompt). It is the only candidate that reaches every
concept: participants, one client per server, all three server primitives,
discovery, a tool call and a tool-list change. The filesystem server appears
once, to show a second client being built. Sentry appears once, for the contrast
the primary example cannot draw: a remote server serving many clients. The
source's weather tool and its San Francisco call were left out on purpose,
because importing them would have created the second running example the prompt
bans; the walkthrough uses the database server's own tools instead.

**Q4. Six things the reader must be able to answer at the end.**
1. What does MCP standardize, and what does it leave alone? (Context exchange
   only; not model choice, not context management.)
2. Who are the participants? (Host = the AI application; one client per server,
   each holding a dedicated connection; server = the program serving context,
   wherever it runs.)
3. What can a server offer? (Actions, readable context, interaction templates:
   tools, resources, prompts.)
4. How does either side find out what the other supports? (Version and
   capabilities in `_meta` on every request; `server/discover` mandatory to
   implement, optional to send, answer usually cacheable.)
5. Why does the transport not change the protocol? (Same messages over stdio
   locally or HTTP remotely; connection, framing and auth live in the outer
   layer.)
6. What follows from statelessness? (Every request self-contained; change
   notifications opt-in and best effort, so clients still poll.)

Running example fixed: **VS Code plus the database server.** Every section
returns to it.

## 2. Assessment of the prompt contract

**Clear and load-bearing.**
- "The mental model appears within the first 150 words." The single most useful
  instruction. It forced the structure: the problem paragraph had to be short
  and the who-owns-what passage had to lead. It lands at word 62 here.
- "Never mirror the source's own table of contents," with a worked example of a
  good heading. Concrete enough to act on. I checked my headings against the
  source's contents (Scope, Participants, Layers, Data layer, Transport layer,
  Statelessness and discovery, Primitives, Notifications, Example) and none
  survives; layers and transports are folded into the walkthrough, where they
  answer a question the scene has already raised.
- "No enumeration of method names... a method name appears only where the reader
  needs to recognize it in the wild, inside a sentence." Sharp and testable. Two
  survive (`server/discover`, `_meta`), both inside sentences, neither as a
  section subject. The source's JSON-RPC blocks, roughly half its length, drop
  out.
- "One running example throughout. A second example only to draw a contrast the
  first cannot, and only once." This is what kills the duplicate-example
  failure, because it makes the writer name the example before drafting.
- "Concept first, term second, in the same sentence." Easy to apply and it
  visibly changes the prose.
- The anti-exemplar section. Naming the failure and its symptoms was more useful
  than any positive instruction.

**Vague, unhelpful or missing.**
- Procedure question 1 assumes a source with a history. This one has none. The
  prompt offers no fallback, so it pushes the writer toward inventing a
  before-state that hard rule 5 then forbids. Two rules collide and the
  collision is invisible until you are drafting. It needs a clause: if the source
  does not describe the prior state, state the problem structurally and do not
  reconstruct history.
- Length is stated in three disagreeing ways: my brief said 700 to 1,100, the
  prompt says roughly 800 to 1,100 body words, and both say seven A5 pages hard
  maximum. Word counts do not map cleanly onto pagination and the writer cannot
  run the renderer. My first draft came in at 1,220 and had to be cut on a rule
  I could not verify.
- Step 3 prescribes five sections in a fixed order, which is close to a template
  and sits awkwardly beside the ban on mirroring a table of contents. It is a
  good order, but a piece that follows it literally has a predictable shape. I
  merged parts of (c) and (d) and put the transport material inside the
  walkthrough; the prompt does not say whether that is allowed.
- "Every claim must be traceable to the source" is right but silent on obvious
  inferences. I dropped several useful sentences the source implies but never
  states, for instance that a server written once works under any host.
- Nothing is said about deprecated features. A newcomer meets sampling and
  logging only as tombstones. I gave them two clauses because the deprecation
  shows where the seam is, but that was my call.
- The frontmatter block shows `source_id` singular with a note about
  `source_ids`, while the live `edition.yaml` row for this article uses the
  plural with one entry. A writer copying the prompt literally produces
  frontmatter that does not match the manifest. I followed the prompt.
- The prompt does not say whether the piece may name the source ("the
  specification calls these..."). In `original_synthesis` this reads as
  attribution rather than the narrator scaffolding banned by tic 6, but it is a
  judgment call the contract should make for the writer.
- The six comprehension answers are generated by the writer and then never used
  as a checklist against the finished draft, even though the novice judge writes
  its own six. Making the writer verify the draft against its own six would
  close that loop.

**Invented because the prompt did not say:** the number of sections and their
boundaries; that the boundary section could absorb the deprecations; that the
closing line should stand alone; and the decision to leave the source's weather
tool out entirely. I also dropped a sentence listing what ships under the MCP
name (specification, SDKs, Inspector, reference servers) purely to make budget,
which is orientation a novice would have valued.

Manuscript body: 1,099 words including headings, 1,065 of prose. The first
draft was 1,220 and had to be cut by hand against a limit I cannot measure.

## 3. After reading the shipped version

Read only after the draft above was finished. It is 1,042 words to my 1,099, so
length is not the difference; what the words do is.

**Concrete differences.**
- Headings. Shipped: "Host, client, server", "Two layers", "The three server
  primitives", "A request from discovery to action", "Practical uses", "Client
  features and notifications", "The useful boundary". Four of the seven are the
  source's own section names or near-paraphrases, and "Host, client, server" is
  the source's bullet list promoted to a heading. Mine are five claims about the
  world, none naming a spec section.
- Where the teaching sits. The shipped piece does state the boundary in its
  first paragraph, which is better than the diagnosis suggested, but the
  ownership model itself ("The host owns intelligence and orchestration. Each
  client owns one protocol relationship. Each server owns a bounded set of
  context and actions") is the final section, 91 words. Mine opens on it, at
  word 62, and the rest of the piece spends it.
- Method and identifier names. Shipped: `tools/call`, `tools/list`,
  `resources/list`, `prompts/list`, `server/discover`, `_meta`, plus invented
  identifiers `query_database`, `diagnose_slow_query`, `weather_current`,
  `location`, `units` and a literal argument object. One sentence enumerates
  three list methods in a row. Mine names two, both inside sentences.
- Examples. Shipped uses four: VS Code with the filesystem and Sentry servers, a
  database server, a weather tool, and then a "Practical uses" section that
  repeats the first two almost verbatim ("A coding host such as Visual Studio
  Code can connect to a local filesystem server and a remote Sentry server. Each
  connection gets its own MCP client" against the earlier "Suppose Visual Studio
  Code connects to a local filesystem server and a remote Sentry server... The
  connections remain separate"). The stdio-versus-Sentry contrast also appears
  twice. Mine has one example, with the filesystem server as a single beat and
  Sentry as a single contrast.
- Accuracy against the source. The shipped piece invents tool and prompt names
  the source never gives, adds "The server validates the input", and opens its
  walkthrough with "First, the client asks the server what protocol versions and
  capabilities it supports through `server/discover`", which contradicts the
  source's statement that calling discovery is optional. It omits statelessness
  as a named idea, the best-effort caveat on notifications, the advice to keep
  polling, cacheability, and the deprecations.
- Ending. Shipped closes on "Tool builders can publish stable typed primitives
  while AI applications compete on how well they use them", which restates the
  separation argument rather than landing. It also opens its last section on
  "MCP is often described as a connector standard. The architecture is more
  precise than that", a cousin of the banned antithesis without being the banned
  form itself. Mine closes on statelessness and does not summarize.
- Mode. The shipped article is `faithful_synthesis` labelled FAITHFUL SYNTHESIS,
  with the protocol project itself as author. The new prompt makes the piece
  `original_synthesis` under an editor byline. That change is upstream of every
  other difference: a faithful synthesis of a specification is close to
  obligated to walk the specification, which is most of why the shipped piece
  reads as a spec dump.

**Did the new prompt prevent the four documented failures?**
1. Headings mirroring the specification: prevented. The rule is explicit, comes
   with a worked example, and the anti-exemplar names the offending headings.
2. Reciting method names: prevented, and this is the sharpest rule in the
   contract because it says exactly where a method name may appear. It would
   also have caught the invented `query_database` and `diagnose_slow_query`,
   which are a fidelity problem the rule catches as a side effect.
3. The duplicated example: prevented for a single writer, because fixing the
   running example is step 2 and precedes drafting. But the documented cause was
   two source chunks processed independently, and the shipped duplication is
   visibly a whole redundant "Practical uses" section rather than a slip. This
   prompt has no defence against chunked processing; it assumes one writer
   holding the whole extraction. If the pipeline still chunks, the rule is a
   hope rather than a mechanism.
4. The mental model arriving last: prevented, and the 150-word rule is the
   reason. A soft instruction to lead with the model would not have survived the
   pull of the source's own order.

**Verdict.** Sufficient for the four failures it was written against, and three
of the four are prevented by mechanism rather than exhortation. Two gaps: the
missing history in this source, where two of the prompt's own rules pull in
opposite directions with no guidance, and the assumption that failure 3 was a
writing failure when the evidence says it was a pipeline failure.
```

### The draft under revision

```
---
source_id: architecture-overview-ce5cb1d1
content_mode: original_synthesis
label: IN A NUTSHELL
---

A model can only work with what is put in front of it. The useful material sits
outside: the rows in a database, the schema that explains them, the contents of
a file, whatever an API would say if asked. Something has to fetch that material
and hand it over, and the Model Context Protocol is an agreement about the
handover.

The picture to keep in your head has two halves and one wire. On one side is the
AI application, which owns the model, the conversation, and every decision about
what to do with what it learns. On the other side is a program that owns some
corner of the outside world and offers it as a short, self-describing menu. The
wire carries messages in one fixed format, and each end states what it can do
rather than assuming.

## The host keeps one client per server

Picture Visual Studio Code with a server in front of your team's database.
Visual Studio Code is the host: the AI application that coordinates connections.
It builds a small component, a client, whose only job is to hold one connection
to that one server and pull context back for the host. Connect a second server, say the filesystem server on
the same laptop, and the host builds a second client, one to one.

The fussiness buys separation: each connection carries its own capabilities and
its own version agreement. A server on your machine, talking over standard input
and output, normally serves that one client; a server a vendor runs, such as the
one Sentry operates on its own platform, typically serves many at once. The word
"server" says nothing about where the program runs.

## What a server is allowed to offer

Your database server has three kinds of thing to give away, and the difference
is worth memorizing. It can do something on request: run a query,
take an action with an effect in the world. It can hand over material to read,
such as the schema, which is context and nothing more. And it can supply a
worked template for talking to it, few-shot examples that show a model how to
drive those queries. The specification calls the three tools, resources and
prompts, and calls them primitives: what the two sides can offer each other.

Traffic is not all one way. A server can put a question to the person at the far
end, either because it needs information it lacks or because it wants an action
confirmed before taking it. The request travels back through the client to the
user, which is why the client says up front whether it can collect input at all.
The specification calls this elicitation.

## Every request introduces itself

MCP is stateless. No session is held open on your behalf, so each request
arrives carrying what is needed to judge it: the protocol version the client
speaks, the capabilities relevant to that request and, unless configured
otherwise, who the client is. It rides in a `_meta` field on every request.

Because nothing is remembered, learning what the other side supports is just
another request. A client may open with `server/discover` and get back the
versions the server accepts and its capabilities: which primitives it can
handle, and whether it will report changes to them. Every server must implement
that request. No client is obliged to send it. A client can fire off the request
it wanted and handle a version rejection, which names the versions the server
does accept. The discovery answer is usually cacheable, so it need not be asked
again before every call. The exchange prevents guesswork: each end learns what
the other can handle, so neither attempts an operation the other has never heard
of.

## One morning on one connection

Visual Studio Code starts. Its client manager opens the connection to the
database server, discovery reports that the server offers tools and will
announce changes to them, and the host marks the server ready.

The client asks for the tool list and gets an entry for each one: a unique name
to call it by, a description of what it does and when to use it, and a schema
for its arguments. The host folds those into one registry covering every server
it has connected, and that registry is what the model can reach this
morning. Mid-conversation the model picks one. The application intercepts the
call, routes it to the client that owns that tool, and sends the exact name from
the listing with arguments matching the declared schema. The result comes back
as an array of content, text in the ordinary case though other types are
allowed, and goes into the conversation as material for the next turn.

Later the server's tool list changes. The client hears about it only because it
asked to: change notifications are opt-in, and a client subscribes by opening a
long-lived stream naming the event types it wants. The notice arrives with no
reply expected, the client re-lists the tools, and the registry updates while the
conversation is still running. Delivery is best effort and a notice can be lost
across a reconnect, so a careful client keeps polling anyway.

Nothing in that morning depended on where the server ran. The messages are the
same either way: a local server exchanges them over standard input and output
with no network in the way, a remote one over HTTP posts with an optional event
stream for anything that arrives in pieces, carrying bearer tokens or API keys
that the local case never needs, obtained through OAuth by preference.
Connecting, framing and authorizing belong to that outer layer, and the protocol
proper never looks at it.

## What the protocol declines to decide

MCP covers the exchange of context and stops there. It has nothing to say about
which model you run, how you use it, or what you do with the context once you
have it.

The agreement is small enough to retire parts of itself. A server used to be
able to borrow the host's model for a completion, and to push log lines at the
client; both went out with the 2026-07-28 version, with advice to call a
provider's API directly and to log to standard error or through OpenTelemetry
instead. It grows sideways: an extension lets a server hand back a durable
handle for slow work, so the client can collect the result later instead of
holding a request open.

A server that remembers nothing about you between requests is a server you can
hang up on and call back.
```

### Findings you must clear

Every finding is an obligation: the defect it names must be gone from your draft. A `suggestion` is advisory. You are judged on whether the defect survived, never on whether you took the suggested line, so solve it however the piece is best served.

1. [major] qualification_loss (from the evidence)
   - where it shows: What the protocol declines to decide | both went out with the 2026-07-28 version | 1
   - earliest repair point: What the protocol declines to decide | The agreement is small enough to retire parts of itself. | 1
   - note:
     The source deprecates; the manuscript removes. The extraction says
     "Sampling is deprecated as of protocol version 2026-07-28" and, under
     Primitives, "Deprecated: The following client primitives are deprecated
     as of protocol version 2026-07-28" for both Sampling and Logging. It
     nowhere says either primitive was withdrawn from the protocol. The
     manuscript writes "A server used to be able to borrow the host's model
     for a completion, and to push log lines at the client; both went out with
     the 2026-07-28 version", and the preceding sentence frames the whole move
     as the protocol being "small enough to retire parts of itself". A reader
     comes away believing sampling and logging no longer exist in 2026-07-28,
     whereas the source describes them as present but discouraged, with the
     "New implementations should..." advice the manuscript correctly relays
     applying to new code rather than to a removal. The defect is structural:
     the retirement framing is set up one sentence earlier, so the repair
     starts there.
2. [minor] invented_claim (from the evidence)
   - where it shows: The host keeps one client per server | The fussiness buys separation | 1
   - note:
     No passage supports capabilities or a version agreement being held per
     connection, and the source's design point runs the other way: "MCP is a
     stateless protocol. Every request carries the protocol version and the
     capabilities relevant to that request in its _meta field, so the server
     can process each request on its own." The source states one client per
     server ("Each MCP client maintains a dedicated connection with its
     corresponding MCP server") but offers no rationale for it; "The fussiness
     buys separation" and the per-connection capability and version state are
     the manuscript's own. The loose reading, that each client-server pairing
     declares its own capabilities and settles its own version, survives, and
     the manuscript states the statelessness correctly two sections later,
     which is why this is minor rather than a contradiction of the source.
3. [minor] invented_claim (from the evidence)
   - where it shows: One morning on one connection | text in the ordinary case | 1
   - note:
     The source makes no claim about which content type is typical. It says
     only "In this example, \"type\": \"text\" indicates plain text content,
     but MCP supports various content types for different use cases." The
     manuscript promotes one example to the ordinary case. The second half of
     the clause is well grounded; only the typicality claim is unsupported.
4. [major] duplication (from the line)
   - where it shows: One morning on one connection | Nothing in that morning depended on where the server ran | 1
   - note:
     The local-versus-remote transport point is made twice, in nearly the same
     terms. First in "The host keeps one client per server": "A server on your
     machine, talking over standard input and output, normally serves that one
     client; a server a vendor runs, such as the one Sentry operates on its own
     platform, typically serves many at once. The word "server" says nothing
     about where the program runs." Then again as the closing paragraph of "One
     morning on one connection": "Nothing in that morning depended on where the
     server ran. The messages are the same either way: a local server exchanges
     them over standard input and output with no network in the way, a remote
     one over HTTP posts..." Both make the same claim (location is irrelevant)
     and both name standard input and output for the local case. Only the
     remote details (HTTP posts, event stream, bearer tokens, OAuth) are new,
     and they arrive stacked as three trailing modifiers on one 60-word
     sentence, which is where I had to go back a paragraph.
   - suggestion (advisory): The remote case adds only what the local one lacks: HTTP posts, an optional event stream for anything that arrives in pieces, and bearer tokens or API keys, obtained through OAuth by preference.
5. [major] repeated_cadence (from the line)
   - where it shows: The host keeps one client per server | Visual Studio Code is the host: the AI application that coordinates connections. | 1
   - note:
     One sentence shape carries the whole piece: assertion, colon, expansion.
     Ten instances. "The useful material sits outside: the rows in a database,
     the schema that explains them". "Visual Studio Code is the host: the AI
     application that coordinates connections." "The fussiness buys separation:
     each connection carries its own capabilities". "It can do something on
     request: run a query". "and calls them primitives: what the two sides can
     offer each other." "each request arrives carrying what is needed to judge
     it: the protocol version the client speaks". "and its capabilities: which
     primitives it can handle". "The exchange prevents guesswork: each end
     learns what the other can handle". "gets an entry for each one: a unique
     name to call it by". "The messages are the same either way: a local server
     exchanges them over standard input and output". The house ban on the em
     dash pushes work onto the colon, but at this density the reader hears the
     same beat in every paragraph and the second half of each sentence stops
     registering as new information.
   - suggestion (advisory): Each request arrives carrying what is needed to judge it. The protocol version the client speaks, the capabilities relevant to that request and, unless configured otherwise, who the client is.
6. [minor] ai_phrasing (from the line)
   - where it shows: What a server is allowed to offer | Your database server has three kinds of thing to give away, and the difference | 1
   - note:
     "Your database server has three kinds of thing to give away, and the
     difference is worth memorizing." The clause is the "it's worth noting"
     construction: it instructs the reader to find the next sentences important
     instead of making them important. It also miscounts, offering "the
     difference" singular between three things.
   - suggestion (advisory): Your database server has three kinds of thing to give away.
7. [minor] dead_words (from the line)
   - where it shows: What a server is allowed to offer | The specification calls the three tools, resources and | 1
   - note:
     A garden path. "The specification calls the three tools, resources and
     prompts" parses first as "calls the three tools" before the reader
     backtracks and re-reads "the three" as the three kinds just listed. The
     sentence then does a second job in the same breath ("and calls them
     primitives"), so the reader is reconstructing two definitions at once.
   - suggestion (advisory): The specification calls these three tools, resources and prompts, and groups them as primitives: what the two sides can offer each other.
8. [minor] dead_words (from the line)
   - where it shows: Every request introduces itself | It rides in a `_meta` field on every request. | 1
   - note:
     "It" follows a three-item list ("the protocol version the client speaks,
     the capabilities relevant to that request and, unless configured
     otherwise, who the client is") and has to be read as the bundle rather
     than the last item, which costs a re-read. "on every request" then repeats
     "each request arrives carrying" from two sentences earlier.
   - suggestion (advisory): All of it rides in a `_meta` field.
9. [minor] ending (from the line)
   - where it shows: What the protocol declines to decide | A server that remembers nothing about you between requests is a server you can | 1
   - earliest repair point: What the protocol declines to decide | MCP covers the exchange of context and stops there. | 1
   - note:
     The kicker is good, but it closes a section it does not belong to. "What
     the protocol declines to decide" is about scope, retired features and the
     durable-handle extension; the sentence immediately before it is "an
     extension lets a server hand back a durable handle for slow work, so the
     client can collect the result later instead of holding a request open."
     The final line then jumps back to statelessness, which was settled two
     sections earlier under "Every request introduces itself". It reads as a
     line stitched on rather than one the section arrives at.
   - suggestion (advisory): That is the shape of a protocol that stays small: it drops what it does not need, and a server that remembers nothing about you between requests is a server you can hang up on and call back.
10. [minor] house_style (from the line)
   - where it shows: - | content_mode: original_synthesis | 1
   - note:
     The front matter declares "content_mode: original_synthesis" while the
     label reads "IN A NUTSHELL" and the piece is commissioned and reviewed as
     the edition's explainer. Editor-owned metadata contradicting the
     editor-owned label.
   - suggestion (advisory): content_mode: in_a_nutshell

## Output contract

Return the complete manuscript first: the frontmatter the prompt specifies, then the body, and nothing before it. Then a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

Then your working notes for that draft: the concept graph or claim ladder you built the piece from, what you cut and why, and anything a later reviser would otherwise have to reconstruct. Everything below the marker is stripped before the manuscript is written and is never shown to a judge, so write it for the next writer, not for a reader. Return no other commentary, and do not wrap the manuscript in a code fence.
