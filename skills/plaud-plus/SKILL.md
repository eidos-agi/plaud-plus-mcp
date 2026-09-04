---
name: plaud-plus
description: >
  Write-capable Plaud MCP (plaud-plus). Official Plaud MCP is read-only.
  Use for rename, folders, speakers, transcript/summary edits, upload, merge,
  trash. Tools: browse_recordings, get_recording, mutate_recording,
  edit_transcript, edit_summary, upload_recording, process_recording,
  merge_recordings, list_folders, mutate_folder, delete_recording,
  plaud_plus_learn.
---

# plaud-plus

Server name: **`plaud-plus`**. Do not use official `plaud` for writes.

Auth is outside the MCP. If tools fail with `session_expired`, tell the human:

```bash
plaud-plus login --desktop    # macOS, Plaud Desktop signed in
# or
plaud-plus login --email you@example.com
plaud-plus doctor
```

## Tools

| Tool | Notes |
|---|---|
| `browse_recordings` | `query`, `since`/`until`, `folder`, `trash`. Paginate with `after`. |
| `get_recording` | `include=["transcript","speakers","summary","audio_url"]`. Transcripts paginate; follow `transcript_truncated` / `transcript_next_after`. |
| `list_folders` | Get ids before move/create. |
| `mutate_recording` | `rename` / `trash` / `restore` / `move`. |
| `edit_transcript` | `rename_speaker` or `correct`. `dry_run=true` first on correct. |
| `edit_summary` | `correct` or `replace`. `dry_run` on correct. |
| `mutate_folder` | `create` / `edit` / `delete`. |
| `upload_recording` | Absolute `file_path`. |
| `process_recording` | `wait=` none / transcript / summary. |
| `merge_recordings` | Two+ ids + `title`. Sources stay. |
| `delete_recording` | Permanent. `confirm=true` only after the human says yes. Prefer trash. |
| `plaud_plus_learn` | Facade: `status` / `snapshot` / `fit` / `cv` / `suggest` / `remember`. UNVERIFIED. Never apply a suggestion without asking. |

Before filing, `plaud_plus_learn(action="suggest", title=..., recording_id=...)`.
The scorer looks at **who** (with context — Clayton is not a folder),
**where**, and **when**, then lift/n-grams. Product-noun rules are a
tie-break only. Never apply a guess without asking. Human training UI: `plaud-plus train`
(http://127.0.0.1:7843/). Two panes: tape + filing harness. Y = agree, S = skip,
D = transcript, T twice = trash. Harness is official DeepSeek, no tools, cannot file.

## Failure modes

- Summarizing a truncated transcript as the whole meeting.
- Find-and-replace on `"the"` without `dry_run`.
- Paging the whole library instead of `query` / date filters.
- Setting `confirm=true` without asking.
