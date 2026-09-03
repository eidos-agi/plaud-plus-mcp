# Security

Plaud Plus holds workspace tokens in the OS keychain and talks to Plaud's
private web API. Treat the GitHub repo as public.

- Do not commit tokens, cookies, or `encryption.json`.
- Do not paste recordings, signed audio URLs, or transcripts into issues.
- Desktop seed reads `~/Library/Application Support/Plaud/` on macOS only.
  It never prints token bytes.

Report vulnerabilities to the repository owner. Do not file public issues with
exploit details.
