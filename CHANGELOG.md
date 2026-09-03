# Changelog

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
