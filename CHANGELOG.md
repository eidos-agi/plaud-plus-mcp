# Changelog

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
