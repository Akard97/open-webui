# WorkOS attachment download — cleanup race fix

**Date:** 2026-06-24
**Branch:** osool
**Status:** Approved (minimal scope)

## Problem

`download_attachment` in `backend/open_webui/routers/workos.py` serves attachments with:

```python
path = await asyncio.to_thread(Storage.get_file, att.storage_key)
return FileResponse(path, ..., background=_download_cleanup(path))
```

`_download_cleanup` schedules a background `os.remove(path)` for cloud providers
when `STORAGE_LOCAL_CACHE` is off. The assumption is that `Storage.get_file`
hands back a request-private temp file. It does **not**: the S3, GCS, and Azure
providers all return a **deterministic path under `UPLOAD_DIR`** derived from the
storage key (`provider.py:205`, `:237`, `:301`), so two concurrent downloads of
the same attachment resolve to the **same on-disk path**.

Confirmed failure modes (cloud provider **and** `STORAGE_LOCAL_CACHE=false`):

1. **Unlink-while-streaming race.** `FileResponse` opens the file lazily during
   the send phase (after the endpoint returns). Request A's background cleanup
   can `os.remove` the shared path before Request B's `FileResponse` opens it,
   yielding `FileNotFoundError` / a broken download. On Windows the `os.remove`
   instead fails on the open file and the copy leaks.
2. **Abort leak.** Starlette does not guarantee a response's background task runs
   on client disconnect/cancellation (encode/starlette#1438), so aborted
   downloads can skip cleanup and leak the temp copy.

The current tests cannot catch this: both fake storages return
`tempfile.mktemp()` (a unique path per call), which the real providers never do.

### Key insight

The stock `files.py` **download** endpoints (`:628`, `:695`, `:744`) serve
`FileResponse` from the provider path and **never delete it** — they rely on the
local cache (`STORAGE_LOCAL_CACHE` defaults to `true`, `config.py:1005`).
`files.py` only cleans up after the synchronous *upload→process* flow
(`:180`), never as a background task while a response streams. The workos
"delete after streaming" task is a workos-specific addition that introduced the
race. In the default config (`cache=true`) `_download_cleanup` is already a
no-op, so the bug only bites cloud + `cache=false`.

Deleting the shared deterministic path is fundamentally racy with any concurrent
read of the same key. The only race-free options are (a) don't delete it (match
`files.py`), or (b) make the path request-unique inside the provider — which is
invasive and breaks `files.py`'s `_cleanup_local_cache` contract. We choose (a).

## Decision

**Minimal fix: remove the workos-specific background cleanup and serve like
`files.py`.** This eliminates both the race and the abort leak. The residual
cloud-cache footprint when `cache=false` becomes identical to the rest of
Open WebUI (its download endpoints already leave the cached copy).

## Changes

### `backend/open_webui/routers/workos.py`
- Delete `_remove_quietly` (`:925-929`) and `_download_cleanup` (`:932-940`).
- `download_attachment`: return
  `FileResponse(path, media_type=att.content_type or 'application/octet-stream', filename=att.name)`
  with no `background=`.
- Remove the now-unused imports: `import os`, `from starlette.background import
  BackgroundTask`, and `from open_webui.config import STORAGE_LOCAL_CACHE,
  STORAGE_PROVIDER`. (`FileResponse` stays.)

### `backend/open_webui/test/workos/test_router_attachments.py`
- **Remove** `test_download_unlinks_provider_temp_copy` — it asserts the buggy
  "must delete after send" contract.
- **Keep** `test_download_keeps_local_provider_real_file` and
  `test_download_keeps_cached_copy_when_local_cache_enabled` — their assertion
  (the served file survives the response) is now the correct universal behavior.
- **Add** `test_concurrent_downloads_same_attachment`: a fake storage whose
  `get_file` returns a **deterministic shared path per key** (mimicking the real
  providers), with `STORAGE_PROVIDER='s3'` / `STORAGE_LOCAL_CACHE=False`. Fire
  two overlapping downloads of the same attachment; assert both return 200 with
  the correct bytes and neither is pulled out from under the other. This must go
  red against the current code and green after the fix.
- Remove `_RecordingStorage` if it becomes unused (or fold it into the new
  deterministic-path fake).

### `policy_review` — no change
It buffers the document into memory (`Response(content=bytes)`) and never
deletes, so it has neither the race nor a skipped-cleanup leak. Its leftover
cache copy already matches the rest of the app.

## Out of scope (documented, not fixed here)
- The provider-level shared-path collision and Azure/GCS in-place-write torn read
  on concurrent same-key downloads — provider-wide, also affects `files.py`.
- The bounded cloud-cache footprint when `STORAGE_LOCAL_CACHE=false` — identical
  to the rest of Open WebUI's download behavior.

## Verification
- Run `backend/open_webui/test/workos/test_router_attachments.py` with the
  `.venv` python; the new concurrent test fails pre-fix and passes post-fix, all
  others green.
- Grep to confirm no remaining references to `_download_cleanup` /
  `_remove_quietly`.
