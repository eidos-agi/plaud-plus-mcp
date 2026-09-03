# Contributing

```bash
uv sync --extra dev
uv run pytest
```

Live Plaud calls need a real account. Do not commit tokens, recordings, or
signed audio URLs. Offline tests in `tests/` must stay green without network.

Keep this package a thin bootstrap around `plaud-tools`. New write verbs belong
upstream unless they are session/auth.

## Verification

```bash
uv run pytest
plaud-plus doctor
```
