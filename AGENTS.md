# Plaud Plus MCP

Write-capable Plaud MCP for agents. Official `@plaud-ai/mcp` is read-only.

- Package: `plaud_plus_mcp`
- MCP entry: `plaud-plus-mcp`
- CLI: `plaud-plus`
- Tools live in dependency `plaud-tools`. This repo owns session bootstrap.
- Never print tokens. Never commit `encryption.json` or keychain dumps.
- Tests: `uv run pytest` (offline). Live doctor: `plaud-plus doctor`.
- Learn ledger is local UNVERIFIED observations, not lessons.md CONFIRMED.
- Filing model: lift/n-grams on titled filings + proper nouns. `plaud-plus learn fit|cv|rank`. Never auto-apply.
