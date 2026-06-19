# Policy Review (PRP) backend — Phase 2: document upload & parsing

**Date:** 2026-06-19
**Status:** Approved (brainstorming) — ready for implementation planning
**Scope:** Phase 2 of the Policy Review backend. Make document **upload real** and **parse it to text**, store both the original file (downloadable) and the extracted text against the review, and surface a download link in the review workspace and the published Library. **No in-app document viewer, no AI scan** — the viewer was explicitly dropped, and the scan is Phase 3.

Related: `2026-06-15-policy-review-backend-phase1-design.md` (persistence, API, rewire — DONE), `2026-06-14-policy-review-finalization-design.md` (the finalized frontend), memory `policy-review-backend-phase1`, `policy-review-autofill`, `osool-rebrand`.

---

## 1. Purpose & context

After Phase 1 the maker-checker loop is real and multi-user on a database, but the file a reviewer "uploads" is captured as **metadata only** (`policy_meta.filename` is hardcoded to `''`; the dropzone on the new-review screen is decorative — see [UploadView.svelte](../../../src/lib/components/policy-review/views/UploadView.svelte)). Phase 2 replaces that decorative step with a real pipeline: the reviewer attaches a policy document, the server stores it, extracts its text, and keeps both — the **original file** (for download / provenance) and the **extracted text** (which Phase 3's AI scan will consume).

This is the prerequisite for Phase 3. On its own it delivers: real document attachment, a downloadable source for reviewers/approvers, and a downloadable source on each published Library policy.

### Decisions locked during brainstorming (2026-06-19)

1. **No in-app viewer.** The reviewer originally wanted a side-by-side rendered viewer, then changed their mind. We do **not** render PDF/DOCX/MD in-app. The only document-facing UI is a plain **Download** link. (The app *does* ship faithful renderers — [PDFViewer.svelte](../../../src/lib/components/common/PDFViewer.svelte), `mammoth` DOCX→HTML and `Markdown.svelte` in [FileItemModal.svelte](../../../src/lib/components/common/FileItemModal.svelte) — they are intentionally left unused here, available if a viewer is ever revisited.)
2. **Upload-first, required.** "Create review" takes the file **and** the metadata together; a review cannot be created without a document. Replacing the document is allowed while the review is `draft` or `rejected`.
3. **Synchronous parse on create.** Parsing happens during the create request (not a background job). Mitigations: a firm size cap, and parse errors surfaced **inline** — a failed parse means **no review is created**, so the user can swap the file and retry.
4. **Accepted types:** `docx`, `pdf`, `md`, `txt`. Size cap ~25 MB.
5. **File retention:** keep the original, **downloadable**. Review-scoped (owner + approver + admin) **and** attached to the Library entry on publish for all-staff download.
6. **Self-contained storage (Approach B).** A new `policy_document` table + the app's `Storage` provider + the app's document `Loader`. No coupling to the chat/RAG `Files` table.

### Scope boundary

| In Phase 2 | Deferred |
|---|---|
| Real upload via the `Storage` provider | In-app rendering / document viewer (dropped) |
| Parse docx/pdf/md/txt → text via the retrieval `Loader` | AI scan of `auto` items + model selector (Phase 3) |
| New `policy_document` table (binary path + extracted text) | Multiple documents per review |
| Multipart `POST /reviews` (file + metadata) | Document history / versioning (single current doc) |
| Replace-document endpoint | OCR-heavy / image formats |
| Review-scoped + Library download endpoints | Auto-extracting policy metadata (name/code/…) from the doc |
| Copy document into a library-owned row at publish | Audit-log UI surface (unchanged from Phase 1) |
| Storage lifecycle (cleanup on delete/replace/unpublish) | Retiring the autofill scaffolding (Phase 3 owns that) |
| Frontend rewire of the upload screen + download links | |

**Forward-compatibility:** `policy_document.text` is exactly the input Phase 3's scan will read. Phase 3 adds the scan that fills `results` from it and retires the autofill toggle; no further schema change is needed (`results` already carries `comment`/`ref`/`confidence`).

---

## 2. The core decisions

**1. A separate document table, not a column on `policy_review`.** The extracted `text` can be hundreds of KB. `ReviewModel` is serialized in full by the list endpoints (`GET /reviews/mine`, `GET /reviews/queue`), so putting `text` on `policy_review` would bloat every list payload. A dedicated `policy_document` table keeps `ReviewModel` untouched and lets us fetch the heavy text only when needed. *Rejected:* a `source_text` column on `policy_review`.

**2. One generalized table for both the working doc and the published copy.** `policy_document` keys on `(owner_type, owner_id)` — mirroring the existing `policy_audit (entity_type, entity_id)` convention — so a `review` document and a `library` document share one schema. *Rejected:* two parallel tables.

**3. The Library gets its own immutable copy at publish.** Phase 1 intentionally lets an admin delete any review and does **not** cascade that to the Library entry (a published policy is canon). So the Library cannot point at the review's document — that would orphan the download when the review is deleted. At approve time we **copy** the binary (to a fresh storage path) and the extracted text into a `policy_document(owner_type='library', owner_id=code)` row. This mirrors Phase 1's "frozen photocopy" philosophy (snapshot the checklist, upsert the library row). *Rejected:* sharing one binary by reference (forces reference-counting and breaks Phase 1's delete semantics).

**4. Reuse the app's Storage + Loader, not the chat `Files` subsystem.** We call `Storage.upload_file` / `Storage.get_file` / `Storage.delete_file` and the app's document `Loader().aload(...)` directly (default engine — the built-in loaders already cover docx/pdf/md/txt with no external services, so no `request`/config coupling). We do **not** create `Files` rows or invoke `process_file` — that machinery is RAG-oriented and its rows are per-user-owned, which would force us to override its ownership for cross-user (approver) access. Self-contained endpoints give us clean, review-scoped authorization. *Rejected:* Approach A (route through the `Files` pipeline with embedding bypassed).

---

## 3. Data model — one new table

Conventions match Phase 1 (`backend/open_webui/models/policy_review.py`): `Text` uuid PKs, `BigInteger` `time.time_ns()` timestamps, async DAO via `get_async_db_context`, `policy_`-prefixed table.

### `policy_document`

| column | type | notes |
|---|---|---|
| `id` | Text PK | uuid |
| `owner_type` | Text | `review` \| `library` |
| `owner_id` | Text | `policy_review.id` (for `review`) or `policy_library.code` (for `library`) |
| `filename` | Text | original upload filename |
| `content_type` | Text | MIME type |
| `size` | BigInteger | bytes |
| `storage_path` | Text | path/URI returned by `Storage.upload_file`; **each row owns its own binary** |
| `text` | Text, null | extracted plain text (consumed by Phase 3) |
| `created_at` | BigInteger | |
| `updated_at` | BigInteger | |

- **`UNIQUE(owner_type, owner_id)`** → one current document per owner. Replacing a review's document **overwrites the row** and deletes the superseded binary.
- Index on `(owner_type, owner_id)` for lookup.
- Created by **one** Alembic migration under `backend/open_webui/migrations/versions/` (table + unique constraint/index). No change to `policy_review` / `policy_library` schemas.

### Light descriptor on the review (no migration)

`policy_review.policy_meta` (existing JSON column) gains, at create/replace time:

```
policy_meta.document = { "filename": str, "contentType": str, "size": int }
```

Enough for the UI to render "Source: x.pdf · Download" without exposing `storage_path` or shipping `text`. `policy_meta.filename` continues to be set (= `document.filename`) for back-compat with existing display code.

### Library descriptor (no migration)

`policy_library.data` (existing JSON column) gains `hasDocument: true` and `filename` at publish, so the Library UI shows a download affordance and the frontend builds `GET /library/{code}/document`.

---

## 4. API surface (`/api/v1/policy`)

One router module, unchanged registration (`backend/open_webui/routers/policy_review.py`). Auth via `get_verified_user`; permission checks via the existing `_require` / `_load_owned_or_403` helpers and `has_permission` with the standard admin bypass.

### Changed

| Method & path | Permission | Change |
|---|---|---|
| `POST /reviews` | `policy_checker` | Now **`multipart/form-data`**: `file` (required `UploadFile`) + `meta` (`Form` JSON string of `PolicyMeta`) + optional `strengths`. Flow below. |

`POST /reviews` flow (synchronous):
1. `_require(policy_checker)`; load the active checklist version (400 if none — unchanged).
2. **Validate** the upload: extension/MIME in the allowlist (`docx/pdf/md/txt`) else `400`; `size` ≤ cap else `400`.
3. `Storage.upload_file(file.file, unique_name, tags)` → `(_, storage_path)`.
4. **Parse** synchronously: `path = Storage.get_file(storage_path)`; `docs = await build_loader_from_config(request).aload(filename, content_type, path)`; `text = "\n".join(d.page_content for d in docs)`. On any exception → `Storage.delete_file(storage_path)`, raise `400 "Could not extract text from this document."` — **no review created**.
5. Insert the review (autofill behavior **unchanged** — see Phase 1 `AUTOFILL_RESULTS_ON_CREATE`); set `policy_meta.document` + `policy_meta.filename`.
6. Insert `policy_document(owner_type='review', owner_id=review.id, …, text=text)`.
7. Audit `document_uploaded`; return `ReviewModel`.

> Steps 5–6 must be consistent: create the document row and the review such that a failure in either leaves no half-state (create the review, then the document; on document-insert failure, delete the review + binary). Detail for the plan.

### New

| Method & path | Permission | Purpose |
|---|---|---|
| `PUT /reviews/{id}/document` | `policy_checker`, **owner**, status `draft`\|`rejected` | Replace the source. Validate + re-parse (same as create), swap the `policy_document` row, **delete the old binary**, update `policy_meta.document`. Replacing on a `rejected` review **reopens it to `draft`** (consistent with `PATCH /results`). Audit `document_replaced`. |
| `GET /reviews/{id}/document` | owner, or `policy_approver`/admin | Download the review's source. Authorize via `_load_owned_or_403(..., approver_ok=is_approver)`. Stream with `FileResponse` + `Content-Disposition: attachment; filename=…`. 404 if no document. |
| `GET /library/{code}/document` | any verified user | Download a published policy's source (Library is all-staff). Resolve `policy_document(owner_type='library', owner_id=code)`. 404 if none. |

### Approve flow change

`POST /reviews/{id}/approve` (existing): after the library upsert, **copy** the review's document into the Library:
- read the review's `policy_document(owner_type='review', owner_id=id)`,
- `new_path = Storage.upload_file(copy_of_binary, …)` (read the source via `Storage.get_file` and re-upload, so the Library binary is independent),
- upsert `policy_document(owner_type='library', owner_id=code, storage_path=new_path, text=…)`,
- set `library_data.hasDocument = True`, `library_data.filename = …` in the existing `library_data` dict.

If a review has no document (legacy/seed reviews created before Phase 2), publish proceeds without a library document (`hasDocument` falsy) — no error.

### Audit additions

New `action` values on the `review` entity: `document_uploaded`, `document_replaced`. The existing `published` action covers the library copy.

---

## 5. Parsing pipeline (synchronous)

- **Reuse** the app's document loader: a plain `Loader()` (default engine) from `backend/open_webui/retrieval/loaders/main.py` — `await Loader().aload(filename, content_type, local_path)`, joining `Document.page_content`. The default loaders cover all four formats (PDF→`PyPDFLoader`, DOCX→`Docx2txtLoader`, MD/TXT→`TextLoader`, see [main.py:409-506](../../../backend/open_webui/retrieval/loaders/main.py)) with **no external services and no `request`/config dependency**, which keeps the extractor a pure, unit-testable function. **No `Files` row, no `process_file`, no vector DB.** *(Honoring an admin-configured extraction engine via `build_loader_from_config` is a deferred enhancement; unnecessary for these formats.)*
- `Storage.get_file(storage_path)` yields a local path for the loader (cloud providers download to a local cache; the local provider returns the path directly).
- **Validation before parse:** allowlist by extension **and** content-type; size cap as a config constant (e.g. `POLICY_REVIEW_MAX_UPLOAD_MB`, default 25). Reject early with a clear message.
- **Errors:** any loader exception (corrupt, unreadable, empty extraction) → delete the binary, `400` with a user-facing message. Surfaced inline on the create/replace screen.
- **Optional (flagged for the plan, default off):** for PDFs, set `policy_meta.pages` from the parsed page count when the user left it blank; manual entry otherwise.

---

## 6. Access control & storage lifecycle

- **Cross-user download** is the reason for dedicated endpoints. `GET /reviews/{id}/document` reuses `_load_owned_or_403(..., approver_ok=is_approver)` so an approver reads the maker's file without us touching `Files` ownership. Library download is open to any verified user.
- **Cleanup (each row owns its own binary, so deletions never orphan a sibling):**
  - `DELETE /reviews/{id}` (existing) also deletes the review's `policy_document` row **and** its binary (`Storage.delete_file`). It does **not** touch the library's independent copy.
  - Replacing a document deletes the superseded binary.
  - `DELETE /library/{code}` (existing unpublish) also deletes the library-owned `policy_document` + binary.

---

## 7. Frontend changes (no new views)

Goal: real upload on the new-review screen + download links; no other view restructuring.

- **`lib/types.ts`** — add `PolicyDocumentMeta = { filename; contentType; size }`; `PolicyMeta.document?: PolicyDocumentMeta`. Keep `filename`.
- **`lib/api.ts`** — `createReviewApi` becomes **multipart** (`FormData`: `file`, `meta` JSON, `strengths`); add `replaceReviewDocumentApi(id, file)`. Downloads use `window.open(`${BASE}/reviews/${id}/document`)` and `…/library/${code}/document` — the same auth-cookie pattern existing file downloads use (`${WEBUI_API_BASE_URL}/files/{id}/content` in [FileItemModal.svelte](../../../src/lib/components/common/FileItemModal.svelte)); no Bearer-header handling needed for a navigation download.
- **`lib/store.ts`** — `createReview(meta, file)` and `replaceDocument(reviewId, file)` go async/multipart; expose `uploading` / `parsing` / error state for the screen.
- **`views/UploadView.svelte`** — turn the decorative dropzone into a real file input + drag/drop: type/size validation, a selected-file chip (name/size/remove), required-file gate on "Create review", `Uploading… / Parsing…` button state, inline parse-error display.
- **`views/ReviewView.svelte`** — "Source document" affordance in the policy header: filename + **Download**; **Replace** when the viewer is the owner and the review is editable (`draft`/`rejected`).
- **Approver path** (`views/ApprovalQueueView.svelte` → review detail) — approver sees **Download**.
- **Library** (`views/AllPoliciesView.svelte` + `views/PolicyPopup.svelte`) — show **Download source** when `data.hasDocument`.

---

## 8. Testing strategy

- **Backend (pytest):**
  - create-with-file: stores binary, parses text, sets `policy_meta.document`, writes a `policy_document` row.
  - reject unsupported type / oversize (400); parse-failure cleanup (no review, no orphan binary).
  - replace: swaps binary (old deleted) + reopens `rejected` → `draft`.
  - review-scoped download: owner 200, approver 200, admin 200, unrelated user 403, missing 404.
  - approve copies the doc to a library-owned row; **library download survives review deletion**; unpublish removes the library doc; delete-review removes its binary.
  - DAO round-trip + the `UNIQUE(owner_type, owner_id)` invariant.
  - tiny real `docx`/`pdf`/`md`/`txt` fixtures assert expected extracted text.
- **Frontend (vitest):** `createReviewApi` multipart shape; store `createReview` wiring; `UploadView` validation (type/size/required) and error rendering.
- **Gates (Phase-1 bar):** backend pytest + frontend vitest green; `svelte-check` clean for policy-review.

---

## 9. File map

| Area | Files |
|---|---|
| Model + DAO | `backend/open_webui/models/policy_review.py` (add `PolicyDocument` table + `PolicyDocumentModel` + `PolicyDocuments` DAO) |
| Migration | `backend/open_webui/migrations/versions/<rev>_add_policy_document_table.py` |
| Router | `backend/open_webui/routers/policy_review.py` (multipart `POST /reviews`; new `PUT/GET /reviews/{id}/document`, `GET /library/{code}/document`; approve-copy; delete/replace cleanup) |
| Storage/parse reuse | `backend/open_webui/storage/provider.py` (`Storage`), `backend/open_webui/retrieval/utils.py` (`build_loader_from_config`), `backend/open_webui/retrieval/loaders/main.py` (`Loader`) |
| Config | size-cap constant (e.g. `POLICY_REVIEW_MAX_UPLOAD_MB`) |
| Frontend client | `src/lib/components/policy-review/lib/api.ts`, `lib/store.ts`, `lib/types.ts` |
| Frontend views | `views/UploadView.svelte`, `views/ReviewView.svelte`, `views/ApprovalQueueView.svelte`, `views/AllPoliciesView.svelte`, `views/PolicyPopup.svelte` |
| Tests | backend pytest (`backend/open_webui/test/policy_review/`), frontend vitest (`src/lib/components/policy-review/`), small binary fixtures |

No new permission keys (the three from Phase 1 suffice). No new frontend views.

---

## 10. Assumptions & open items

- **Auth on downloads:** navigation downloads (`window.open`) rely on the backend accepting the session cookie for `get_verified_user`, as the existing `Files` content links do. Confirm during implementation; fall back to a Bearer-fetch-to-blob download if cookie auth isn't honored on these routes.
- **Binary copy at publish:** implemented as read-via-`Storage.get_file` + re-`upload_file`, so the Library binary is genuinely independent of the review's. Acceptable storage cost (~one duplicate per published policy).
- **Legacy/seed reviews** (created before Phase 2, or seeded with no document) have no `policy_document`; download endpoints 404 and publish proceeds with `hasDocument` falsy. No backfill.
- **Autofill** (`POLICY_REVIEW_AUTOFILL`, default on) stays on through Phase 2; Phase 3 retires it.
- **PDF page-count auto-fill** is an optional nicety, default off; core behavior keeps manual `pages` entry.
- **Empty extraction** (a valid file that yields no text) is treated as a parse failure (`400`) — Phase 2 requires usable text for Phase 3.
