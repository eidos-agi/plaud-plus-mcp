# Changelog

## 0.6.1 — 2026-09-04

- Train UI **D** loads the full transcript into a scrollable pane. No 8k/12k clip.

## 0.6.0 — 2026-09-04

- Train UI is a two-pane desk: tape on the left, filing harness on the right.
- The harness is ours — official DeepSeek, streaming thinking, no tools, cannot file.
- Harness folder guesses sit next to the lift model. Human still clicks.

## 0.5.5 — 2026-09-04

- Train chat uses the official DeepSeek API (`DEEPSEEK_API_KEY` or keychain
  `plaud-plus`/`deepseek`). Default model `deepseek-v4-flash` with thinking.
- No OpenRouter, no DSH harness credentials, no coding agent.

## 0.5.4 — 2026-09-04

- Train chat is a durable JSONL per recording (`PlaudPlus/chats/<id>.jsonl`).
- The UI shows DeepSeek thinking as well as the reply.

## 0.5.3 — 2026-09-04

- Train UI: DeepSeek chat on each card. Per-recording history. It cannot file.

## 0.5.2 — 2026-09-04

- Train UI notes field. Typed notes store with the label (and trash/skip) and
  feed the local model. Shortcuts ignore the textarea.

## 0.5.1 — 2026-09-04

- Train UI: **Dive deeper** (D) pulls the transcript and re-scores people/place.
- Train UI: **Trash** (T, twice) sends to Plaud trash — reversible, not delete.

## 0.5.0 — 2026-09-04

- `plaud-plus train` — local HITL page. One unfiled recording, you pick the
  folder, it files and refits. Y agrees with the guess. S skips. Probe folders
  are not buttons.

## 0.4.0 — 2026-09-03

- Filing score is people, place, and time-of-day first. A name is not a folder:
  Clayton in a G702 walk is ARP; Clayton on a dashboard is AIC.
- Product-noun "build vs ops" is a tie-break only when those are missing.
- `suggest` takes the recording hour from Plaud `start_time`.

## 0.3.1 — 2026-09-03

- Hard rule: building software → AIC Holdings; tenant ops (G702 / retainage / DD5 /
  cerebro.greenmarkwaste.com) → the tenant folder. Still never auto-applied.

## 0.3.0 — 2026-09-03

- Self-fitting lift/n-gram filing model (`plaud-plus learn fit` / `cv` / `rank`).
- `snapshot` pulls summaries of already-filed recordings and refits.
- Suggestions include `why` terms. Still UNVERIFIED, still never auto-applied.

## 0.2.2 — 2026-09-03

- `suggest` reads the Plaud summary when given a `recording_id`.
- Alias terms use word boundaries (`sid` does not match `Sidebar`).
- Title bag-of-words no longer scores the whole summary.

## 0.2.1 — 2026-09-03

- `learn snapshot` also ingests already-filed titles.
- Date/clock tokens no longer match folders named like `Plus Probe 2026-09-03`.
- Alias notes (`terms` + `folder_id`) can hint a folder. Still UNVERIFIED, still never auto-applied.

## 0.2.0 — 2026-09-03

- Local observation ledger (`plaud_plus_learn` / `plaud-plus learn`).
- Successful writes are recorded. Suggestions are UNVERIFIED and never auto-applied.
- `snapshot` ingests current Plaud folder names. Not lessons.md CONFIRMED.

## 0.1.0 — 2026-09-03

- First public release.
- MCP stdio server wrapping plaud-tools' eleven write-capable tools.
- `plaud-plus login --desktop` seeds a workspace refresh token from a signed-in
  macOS Plaud Desktop app (Google SSO).
- `plaud-plus login --email` uses plaud-tools password login.
- Workspace tokens refresh on every MCP launch (~24h lifetime).
