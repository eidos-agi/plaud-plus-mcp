# Plaud Plus MCP

Official Plaud MCP (`@plaud-ai/mcp`) is **read-only**. Plaud Plus talks to the
same web API the Plaud website uses, so an agent can rename, file, trash, name
speakers, fix transcripts, edit summaries, upload, merge, and trigger
transcription.

Unofficial. Not affiliated with Plaud Inc. Their Terms of Service may restrict
using the private web API. You still need a real Plaud account.

The eleven tools come from [plaud-tools](https://github.com/massive-value/plaud-tools)
(LGPL-3.0-or-later). This package adds session bootstrap that actually works
for Google-SSO / Plaud Desktop users, whose workspace tokens last ~24 hours,
and a **learn facade** that remembers writes on this machine.

Observations are UNVERIFIED. They are not [lessons.md](https://github.com/eidos-agi/lessons.md)
CONFIRMED lessons. The MCP will not file a recording because a title said “ARP”;
it will *suggest* and wait.

## Install

```bash
uv tool install git+https://github.com/eidos-agi/plaud-plus-mcp
```

or from a checkout:

```bash
uv tool install --editable .
```

## Sign in

**macOS with Plaud Desktop already signed in** (including Google login):

```bash
plaud-plus login --desktop
plaud-plus doctor
```

**Email + password** (if you signed up with Google, set a password via
“Forgot password” on [web.plaud.ai](https://web.plaud.ai) first):

```bash
plaud-plus login --email you@example.com
```

## Wire the MCP

Grok:

```bash
grok mcp add plaud-plus -- plaud-plus-mcp
```

Claude Code:

```bash
claude mcp add plaud-plus -- plaud-plus-mcp
```

Cursor / Codex — stdio command `plaud-plus-mcp`, no args. Name it `plaud-plus`
so it can sit next to official `plaud`.

Restart the client. Ask it to list your Plaud folders.

## Tools

| Tool | Kind |
|---|---|
| `browse_recordings` | read |
| `get_recording` | read |
| `list_folders` | read |
| `mutate_recording` | rename / trash / restore / move |
| `edit_transcript` | rename speaker, find-and-replace (`dry_run`) |
| `edit_summary` | find-and-replace or overwrite (`dry_run`) |
| `mutate_folder` | create / edit / delete |
| `upload_recording` | local audio → Plaud |
| `process_recording` | transcribe + summarize |
| `merge_recordings` | two+ → one new file |
| `delete_recording` | permanent; needs `confirm=true` |

Prefer trash over delete. Preview text edits with `dry_run=true`.

## How auth works

Plaud Desktop (and the website) hold a **workspace refresh token**. Plus stores
that in the OS keychain (`service=plaud-plus`) and mints a 24-hour workspace
access token on every MCP launch.

`plaud-tools` was written for 30-day password tokens and refuses anything
inside a 24-hour expiry window. Plus shrinks that buffer to 15 minutes so a
fresh workspace token is usable.

CLI passthrough: `plaud-plus folders`, `plaud-plus list --limit 5`, and the
rest of the plaud-tools commands work after a session exists.

## Learn (local, unverified)

One extra MCP tool: `plaud_plus_learn`. Actions: `status`, `snapshot`, `recall`,
`suggest`, `remember`. Successful `mutate_*` / `edit_*` / `upload_*` calls append
to a JSONL ledger (`~/Library/Application Support/PlaudPlus/learn.jsonl` on macOS).

```bash
plaud-plus learn snapshot
plaud-plus learn suggest --title "ARP site walk with Clayton"
plaud-plus learn remember --claim "Haul reviews go in GMW Greenmark"
plaud-plus learn
```

`snapshot` records folder names, already-filed titles, and their summaries,
then fits a lift/n-gram model (`learn.model.json`). Clock titles return no
guess unless a summary is passed. `suggest --recording-id` reads the Plaud
summary. `learn cv` is leave-one-out accuracy. `learn rank` scores unfiled
titles. `do_not_apply: true` always. Ask the human, then `mutate_recording`.

## Train (HITL)

```bash
plaud-plus train          # http://127.0.0.1:7843/
plaud-plus train --no-open --port 7843
```

One card at a time. Click a folder (or **Y** if the guess is right). **S**
skips. **D** dives into the transcript. **T** twice sends to Plaud trash
(reversible). A folder click files and refits. Type a note on the card (who / where / what) before you file — it trains
with the label. Shortcuts are off while the note box is focused.
Each card has a **DeepSeek chat** against `api.deepseek.com` (`DEEPSEEK_API_KEY`,
or macOS keychain `plaud-plus` / `deepseek`). Default model `deepseek-v4-flash`
with thinking shown. Not OpenRouter, not a coding agent. It cannot file.
Chats persist under `PlaudPlus/chats/`.

Never auto-files.

## License

MIT for this repo. Runtime depends on plaud-tools (LGPL-3.0-or-later) — see
[NOTICE](NOTICE).
