result: changes_required
findings:
  - severity: major
    article: mcp-in-a-nutshell
    locator: "One morning on one connection | Nothing in that morning depended on where the server ran | 1"
    category: duplication
    note: |
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
    suggestion: "The remote case adds only what the local one lacks: HTTP posts, an optional event stream for anything that arrives in pieces, and bearer tokens or API keys, obtained through OAuth by preference."
  - severity: major
    article: mcp-in-a-nutshell
    locator: "The host keeps one client per server | Visual Studio Code is the host: the AI application that coordinates connections. | 1"
    category: repeated_cadence
    note: |
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
    suggestion: "Each request arrives carrying what is needed to judge it. The protocol version the client speaks, the capabilities relevant to that request and, unless configured otherwise, who the client is."
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "What a server is allowed to offer | Your database server has three kinds of thing to give away, and the difference | 1"
    category: ai_phrasing
    note: |
      "Your database server has three kinds of thing to give away, and the
      difference is worth memorizing." The clause is the "it's worth noting"
      construction: it instructs the reader to find the next sentences important
      instead of making them important. It also miscounts, offering "the
      difference" singular between three things.
    suggestion: "Your database server has three kinds of thing to give away."
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "What a server is allowed to offer | The specification calls the three tools, resources and | 1"
    category: dead_words
    note: |
      A garden path. "The specification calls the three tools, resources and
      prompts" parses first as "calls the three tools" before the reader
      backtracks and re-reads "the three" as the three kinds just listed. The
      sentence then does a second job in the same breath ("and calls them
      primitives"), so the reader is reconstructing two definitions at once.
    suggestion: "The specification calls these three tools, resources and prompts, and groups them as primitives: what the two sides can offer each other."
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "Every request introduces itself | It rides in a `_meta` field on every request. | 1"
    category: dead_words
    note: |
      "It" follows a three-item list ("the protocol version the client speaks,
      the capabilities relevant to that request and, unless configured
      otherwise, who the client is") and has to be read as the bundle rather
      than the last item, which costs a re-read. "on every request" then repeats
      "each request arrives carrying" from two sentences earlier.
    suggestion: "All of it rides in a `_meta` field."
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "What the protocol declines to decide | A server that remembers nothing about you between requests is a server you can | 1"
    repair_from: "What the protocol declines to decide | MCP covers the exchange of context and stops there. | 1"
    category: ending
    note: |
      The kicker is good, but it closes a section it does not belong to. "What
      the protocol declines to decide" is about scope, retired features and the
      durable-handle extension; the sentence immediately before it is "an
      extension lets a server hand back a durable handle for slow work, so the
      client can collect the result later instead of holding a request open."
      The final line then jumps back to statelessness, which was settled two
      sections earlier under "Every request introduces itself". It reads as a
      line stitched on rather than one the section arrives at.
    suggestion: "That is the shape of a protocol that stays small: it drops what it does not need, and a server that remembers nothing about you between requests is a server you can hang up on and call back."
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "- | content_mode: original_synthesis | 1"
    category: house_style
    note: |
      The front matter declares "content_mode: original_synthesis" while the
      label reads "IN A NUTSHELL" and the piece is commissioned and reviewed as
      the edition's explainer. Editor-owned metadata contradicting the
      editor-owned label.
    suggestion: "content_mode: in_a_nutshell"
scores:
  structure: 4
  flow: 3
  sentence_craft: 3
  house_style: 4
  voice_consistency: 4
notes: |
  The explainer checks pass, and that is the real news given edition 004. The
  mental model ("The picture to keep in your head has two halves and one wire")
  lands at word 62 and is complete by word 140, inside the 150-word window and
  nowhere near the close. Every heading states an idea rather than mirroring a
  table of contents, no method or field name is a section's subject or a list
  item (`_meta` and `server/discover` both sit inside sentences about something
  else), and the Visual Studio Code plus database server example is genuinely
  carried from the first section through to "One morning on one connection"
  rather than restarted. Sentry appears once. What holds the piece back is
  texture rather than architecture: the transport paragraph at the end of "One
  morning" replays a point already made in section one, and the colon-expansion
  sentence runs ten times, so by the fourth section the prose has a metronome
  under it. Cut the duplicated closing paragraph, break up three or four of the
  colons, and re-seat the last line on the section it closes, and this reads
  cleanly at speed.
