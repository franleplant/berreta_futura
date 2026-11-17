---
source_ids:
- push-events-into-a-running-session-with-channels-a5b416ea
content_mode: article
label: ARTICLE
---

A channel is an MCP server that pushes events into your running Claude Code session, so Claude can react to things that happen while you're not at the terminal. It can be two-way: Claude reads the event and replies through the same channel, like a chat bridge. Events only arrive while the session is open, so for an always-on setup you run Claude in a background process or persistent terminal. Channels are in research preview. They require Anthropic authentication through claude.ai or a Console API key, aren't available on Amazon Bedrock, Google Cloud's Agent Platform, or Microsoft Foundry, and Team and Enterprise organizations must explicitly enable them.

## Setting one up

Each supported channel is a plugin that requires Bun. Telegram, Discord, and iMessage are included in the research preview. Fakechat is a demo that runs a chat UI on localhost, with nothing to authenticate.

Telegram shows the pattern: create a bot with BotFather, then install, configure, restart with the flag, and pair.

```
/plugin install telegram@claude-plugins-official
```

```
/telegram:configure <token>
```

```
claude --channels plugin:telegram@claude-plugins-official
```

Message your bot, and it replies with a pairing code. Then:

```
/telegram:access pair <code>
```

```
/telegram:access policy allowlist
```

Discord follows the same steps, plus enabling Message Content Intent and inviting the bot to your server. iMessage needs no bot token: it reads `~/Library/Messages/chat.db` directly and replies through AppleScript, so it requires macOS and Full Disk Access for your terminal. Texting yourself bypasses access control; other contacts are added with `/imessage:access allow`.

If an install reports the marketplace isn't found, add it with `/plugin marketplace add anthropics/claude-plugins-official` and retry.

When Claude replies, your terminal shows the inbound message, the tool call, and a confirmation like "sent", but not the reply text. That appears on the other platform.

If Claude hits a permission prompt while you're away, the session pauses until you respond. Channel servers that declare the permission relay capability can forward these prompts to you. For unattended use, `--dangerously-skip-permissions` bypasses most prompts, but only use it in environments you trust; the actions no mode auto-approves still apply.

## Security

Every approved channel plugin keeps a sender allowlist: only IDs you've added can push messages, and everyone else is silently dropped. Being in `.mcp.json` isn't enough; a server also has to be named in `--channels`. If a channel declares permission relay, anyone who can reply through it can approve or deny tool use in your session, so only allowlist senders you trust with that authority.

## Enterprise controls

Two managed settings, which users cannot override, govern availability:

| Setting | Purpose |
| --- | --- |
| `channelsEnabled` | Master switch. Must be `true` for any channel to deliver messages, including the development flag. |
| `allowedChannelPlugins` | Which plugins can register once channels are enabled. Replaces the Anthropic-maintained list when set. |

On claude.ai Team and Enterprise, channels are blocked until an Owner enables them. With Console API key authentication, they're permitted by default unless your organization deploys managed settings. Pro, Max, and Ultra users without an organization skip these checks. An empty `allowedChannelPlugins` array blocks the allowlist, but `--dangerously-load-development-channels` can still bypass it; to block channels entirely, leave `channelsEnabled` unset.

## Preview limits

Neither `--channels` nor `--dangerously-load-development-channels` appears in `claude --help`, though both work. `--channels` only accepts plugins from the Anthropic-maintained allowlist or your organization's. To test a channel you're building, pass it to `--dangerously-load-development-channels`. The flag syntax and protocol contract may change based on feedback.

## Where channels fit

Cloud sessions and Claude in Slack start fresh cloud sessions. A standard MCP server is queried by Claude; nothing is pushed. Remote Control lets you drive your local session from claude.ai or the mobile app. Channels fill the gap by pushing events from non-Claude sources into your already-running local session: a question from your phone answered against your real files, or a webhook from CI, an error tracker, or a deploy pipeline arriving where Claude already remembers what you were debugging.
