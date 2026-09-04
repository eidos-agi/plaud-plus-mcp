# Plaud Plus MCP

Write-capable Plaud MCP for agents. Official `@plaud-ai/mcp` is read-only.

- Package: `plaud_plus_mcp`
- MCP entry: `plaud-plus-mcp`
- CLI: `plaud-plus`
- Tools live in dependency `plaud-tools`. This repo owns session bootstrap.
- Never print tokens. Never commit `encryption.json` or keychain dumps.
- Tests: `uv run pytest` (offline). Live doctor: `plaud-plus doctor`.
- Learn ledger is local UNVERIFIED observations, not lessons.md CONFIRMED.
- Filing model: people/place/time then lift. `plaud-plus train` is the HITL UI. Never auto-apply.
- Train chat is a local DeepSeek filing harness (no tools, cannot file). Not DSH.
