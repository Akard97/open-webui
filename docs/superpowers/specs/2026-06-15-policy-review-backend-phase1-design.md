# Policy Review (PRP) backend — Phase 1: persistence, API & rewire

**Date:** 2026-06-15
**Status:** Approved (brainstorming) — ready for implementation planning
**Scope:** Phase 1 of the Policy Review backend. Make the maker-checker workflow **real and multi-user** on a database, behind permission-enforced REST endpoints, and rewire the finalized frontend off `localStorage` onto those endpoints. **No file upload, no document parsing, no AI scan** — those are Phases 2 and 3.

Related: `2026-06-14-policy-review-finalization-design.md` (the finalized frontend), memory `policy-review-access`, `osool-rebrand`.

---

## 1. Purpose & context

The Policy Review tool lets the Organizational Excellence (OE) team review draft policies against the **PRP Master Checklist v2.0** (6 themes, 70 items, weighted scoring, two mandatory gates, three verdicts) and publish approved policies into a Library all staff can read. The frontend is finished and runs entirely client-side on seeded mock data persisted to `localStorage` (key `osool.policyReview.v3`). This phase replaces that mock layer with a real backend.

Phase 1 delivers a fully working maker-checker loop with **manual verdicts**: a reviewer creates a review, sets every verdict by hand, submits it; an approver sees it in a real cross-user queue and approves (publishing to the Library) or rejects (returning it). The checklist admin (draft → publish → versioned) is real. The only things missing versus the eventual product are the *file upload*, the *document parsing*, and the *AI scan* — explicitly deferred.

### Decisions locked during brainstorming
1. **LLM access (Phase 3, recorded now so the schema anticipates it):** the tool gets its own model selector that points at any provider already configured in Osool's connection layer — Anthropic (native), OpenAI, Gemini (via its OpenAI-compatible endpoint), or any OpenAI-compatible base URL. The scan will call `generate_chat_completion` with the selected model id and use provider-agnostic structured JSON output. **Not built in Phase 1.**
2. **Spec structure:** one spec per phase. This document is Phase 1 only; Phases 2 and 3 get their own brainstorm + spec + plan.
3. **Review creation in Phase 1:** keep the existing upload screen, but the file is **optional and unparsed**. We capture the metadata (including `filename`) so the UI looks right; we do **not** store the binary or parse it. Verdicts are entered manually.
4. **Seeding:** full prototype parity — seed the real PRP v2.0 checklist + 3 standards, the ~60 demo library policies, **and** the 5 demo reviews.

### Scope boundary

| In Phase 1 | Deferred |
|---|---|
| DB models + one Alembic migration (4 tables) | File upload + storage (Phase 2) |
| REST endpoints for checklist, reviews, library | Document parsing docx/pdf/md → text (Phase 2) |
| Endpoint-level permission enforcement | AI scan of `auto` items + model selector (Phase 3) |
| Server-enforced lifecycle/locking | Audit-log *UI surface* (write now, no screen) |
| Snapshot-on-review (the frozen copy) | Approver notifications, checklist import/export |
| Authoritative server-side scoring | Side-by-side document viewer |
| Audit-log *writes* | |
| Seed checklist + standards + library + demo reviews | |
| Frontend rewire: `localStorage` → API | |

**Forward-compatibility rule:** Phase 1 schema is designed so Phases 2–3 add no migration churn. The `results` JSON already carries `comment`/`ref`/`confidence` (AI fields); `policy_meta` already carries `filename`. Adding a real file link in Phase 2 and AI-written results in Phase 3 needs no table changes.

---

## 2. The four core decisions

**1. Document model, not normalized tables.** Each checklist version is stored as a single row whose `data` column holds the whole definition (themes/sections/items/standards/verdictBands) as JSON. Each review's answers are a single JSON map keyed by `itemId`. The app always consumes the *whole* checklist at once and never queries it per-item, so chopping it into theme/section/item FK tables buys nothing and costs ordering, draft-vs-active duplication, and cascade complexity. *Rejected:* normalized relational tables.

**2. Snapshot = reference + embedded copy (the frozen photocopy).** Each review stores both `checklist_version_id` (provenance link) **and** `checklist_snapshot` (the full pinned definition JSON). Scoring and display always read the snapshot, never the live active version. This is the definitive fix for the known gap where `versionFor()` falls back to the active version — the review carries its own copy for life, so publishing a new checklist version never re-grades work in progress. *Rejected:* reference-only relying on a "never mutate a published version" invariant.

**3. Library is its own table, upserted on publish.** A standalone `policy_library` table holds published canon. Approving a review upserts a library row keyed by policy `code`; the ~60 seeded POLICIES are pre-inserted rows with `source_review_id = null`. A derived "view over approved reviews" can't represent seeded canon that never had a review, and loses library-only fields (summary, outline, related, nextReview). *Rejected:* derived library.

**4. Authoritative server-side scoring.** [scoring.ts](src/lib/components/policy-review/lib/scoring.ts) (pure, ~70 lines) is ported to `scoring.py`. The server uses it for exactly two trust-sensitive jobs: **gating submit** (block until `humanItemsRemain` is false — no `pending`, no unresolved `human`) and **computing the library score/verdict at publish**. The frontend keeps its TS copy for live display; both are tested against a shared fixture set so they cannot drift. *Rejected:* client-only scoring.

---

## 3. Data model — 4 tables

Conventions (matching newer Open WebUI code, e.g. [notes.py](backend/open_webui/models/notes.py)): `Text` primary keys from `str(uuid.uuid4())`; `BigInteger` timestamps from `int(time.time_ns())`; `JSON` columns; Pydantic models with `model_config = ConfigDict(from_attributes=True)`; async DAO classes using `get_async_db_context` from `open_webui.internal.db`; tables prefixed `policy_`. All four tables are created by **one** Alembic migration under `backend/open_webui/migrations/versions/`.

### `policy_checklist_version`
The versioned definition. At most one `active` and at most one `draft` exist at any time (enforced in the DAO).

| column | type | notes |
|---|---|---|
| `id` | Text PK | uuid. (The frontend's `'v2.0'` becomes `label`, not the id.) |
| `label` | Text | `'v2.0'`, `'v2.1'`, … |
| `status` | Text | `active` \| `draft` \| `archived` |
| `data` | JSON | `{ changeSummary, themes[], sections[], verdictBands, standards[] }` — mirrors `ChecklistVersion` minus the identity/status fields |
| `published_at` | BigInteger, null | |
| `published_by_id` | Text, null | real user id when published by a user |
| `published_by_name` | Text, null | display name (also used for seed) |
| `created_at` | BigInteger | |
| `updated_at` | BigInteger | |

### `policy_review`
The unit of work.

| column | type | notes |
|---|---|---|
| `id` | Text PK | uuid |
| `policy_meta` | JSON | `PolicyMeta` (name, code, version, owner, reviewer, reviewDate, pages, filename) |
| `checklist_version_id` | Text | provenance link to the version snapshotted |
| `checklist_snapshot` | JSON | **pinned** full checklist definition; scoring/display read this |
| `results` | JSON | `Record<itemId, ItemResult>` |
| `status` | Text | `draft` \| `pending` \| `approved` \| `rejected` |
| `approval` | JSON | `ApprovalState` (status, sentAt, decidedAt, decidedBy, note) |
| `strengths` | JSON | `string[]` |
| `created_by_id` | Text, null | real owner's user id; **null for seeded demo reviews** |
| `created_by_name` | Text | display owner (fictional for seed) |
| `created_at` | BigInteger | indexed |
| `updated_at` | BigInteger | |

Indexes: `created_by_id` (for "my reviews"), `status` (for the queue).

### `policy_library`
Published canon, readable by all staff.

| column | type | notes |
|---|---|---|
| `id` | Text PK | uuid |
| `code` | Text, unique | natural key (e.g. `OSOOL-RE-POL-014`); publish upserts by this |
| `data` | JSON | full `LibraryPolicy` (title, fn, owner, version, status, score, pages, nextReview, summary, outline, related, …) |
| `source_review_id` | Text, null | set when published from a review; null for seeded canon |
| `created_at` | BigInteger | |
| `updated_at` | BigInteger | |

### `policy_audit`
Append-only history. Written in Phase 1; no UI surface this phase.

| column | type | notes |
|---|---|---|
| `id` | Text PK | uuid |
| `entity_type` | Text | `review` \| `checklist` |
| `entity_id` | Text | review id / version id |
| `action` | Text | `created`·`updated`·`submitted`·`approved`·`rejected`·`reopened`·`published`·`checklist_published` |
| `actor_id` | Text, null | acting user id |
| `actor_name` | Text | acting user display name |
| `detail` | JSON, null | e.g. note, `{from,to}` status, version label |
| `created_at` | BigInteger | indexed; plus index on (`entity_type`,`entity_id`) |

---

## 4. API surface

One router module `backend/open_webui/routers/policy_review.py`, registered in [main.py](backend/open_webui/main.py) as
`app.include_router(policy_review.router, prefix="/api/v1/policy", tags=["policy"])`.

Auth uses `get_verified_user` from `utils/auth.py`. Permission checks use
`has_permission(user.id, "features.<key>", request.app.state.config.USER_PERMISSIONS, db=db)`
from `utils/access_control`, with the standard admin bypass: `if user.role != "admin" and not await has_permission(...)`. The three keys (`policy_checker`, `policy_approver`, `policy_admin`) already exist in [config.py](backend/open_webui/config.py). Errors raise `HTTPException` with `ERROR_MESSAGES` from `constants.py`.

### Checklist — `/api/v1/policy/checklist`
| Method & path | Permission | Purpose |
|---|---|---|
| `GET /active` | any verified user | the active version (needed to render a review) |
| `GET /versions` | `policy_admin` | list active + archived history |
| `GET /versions/{id}` | `policy_admin` | one version (provenance/history) |
| `GET /draft` | `policy_admin` | the current working draft (or null) |
| `POST /draft` | `policy_admin` | start a draft = clone the active version |
| `PUT /draft` | `policy_admin` | save draft edits |
| `POST /draft/publish` | `policy_admin` | validate, then publish: archive old active, draft → new active |
| `DELETE /draft` | `policy_admin` | discard the draft |

Publish validation mirrors [checklist.ts](src/lib/components/policy-review/lib/checklist.ts) `validateDraft`: theme weights sum to 100%, every theme has ≥1 PRP group, every group has ≥1 item. New label via `nextLabel` (`v2.0` → `v2.1`). Writes a `checklist_published` audit entry.

### Reviews — `/api/v1/policy/reviews`
| Method & path | Permission | Purpose |
|---|---|---|
| `POST /` | `policy_checker` | create a review from metadata; snapshots the active version into `checklist_snapshot`; all items start `pending`; `created_by_id` = caller |
| `GET /mine` | `policy_checker` | reviews where `created_by_id` = caller |
| `GET /queue` | `policy_approver` | reviews with `status = pending` |
| `GET /{id}` | owner, or `policy_approver`/admin | one review (with its snapshot + results) |
| `PATCH /{id}/results` | `policy_checker`, **owner**, status `draft` or `rejected` | set/patch item results; editing a `rejected` review **reopens it to `draft`** |
| `POST /{id}/submit` | `policy_checker`, **owner**, status `draft` | server re-scores; allowed only if no unresolved items; `draft → pending` |
| `POST /{id}/approve` | `policy_approver`, status `pending` | compute final score/verdict; `pending → approved`; **upsert into `policy_library`**; stamp decidedBy/At |
| `POST /{id}/reject` | `policy_approver`, status `pending` | requires a note; `pending → rejected` (returns to owner) |

Each mutation writes the matching `policy_audit` row.

### Library — `/api/v1/policy/library`
| Method & path | Permission | Purpose |
|---|---|---|
| `GET /` | any verified user | list published policies |
| `GET /{code}` | any verified user | one policy by code |

---

## 5. Enforcement & locking (server-side state machine)

```
draft ──submit──▶ pending ──approve──▶ approved (locked, in Library)
  ▲                  │
  │                  └──reject(+note)──▶ rejected
  └────── edit (reopen) ───────────────────┘
```

The server enforces, independent of the UI:
- **Draft** — only the owner may PATCH results or submit. **Submit blocked** until the authoritative scorer reports `humanItemsRemain = false`.
- **Pending** — read-only for the reviewer (no results edits, no resubmit); appears in the approver queue. Only an approver/admin may approve or reject.
- **Approved** — immutable for everyone. Already upserted into the Library, stamped with `decidedBy`/`decidedAt`.
- **Rejected (Returned)** — an approver decision requiring a note. The owner editing it (PATCH results) transitions it back to `draft` for fix + resubmit.

Ownership = `review.created_by_id == user.id`. System admins bypass permission checks per the standard pattern.

---

## 6. Scoring port

Create `backend/open_webui/utils/policy_review/scoring.py` (or a `policy_review` package) porting `computeScores` exactly: per-theme `compliant / (compliant + non-compliant)`, `human`/`pending` held aside, gate themes must clear their threshold, overall = weight-weighted average, verdict bands from the snapshot's `verdictBands`. Inputs: the **snapshot** definition + the review `results`. Used by `POST /submit` (gate) and `POST /approve` (final score/verdict for the library row). A shared fixture set (a handful of `(definition, results) → expected ScoreResult` cases) is checked into both the Python and TS test suites so the two implementations stay identical.

---

## 7. Frontend rewire (`localStorage` → API)

Goal: **no view changes.** Only the data layer under [store.ts](src/lib/components/policy-review/lib/store.ts) changes.

- Add `src/lib/components/policy-review/lib/api.ts` — a thin client wrapping the endpoints in §4 (using the app's existing auth'd fetch convention).
- Rewire `store.ts`:
  - Drop the `localStorage` load/persist and the seed-on-load path.
  - On init, fetch the active checklist, my reviews, the queue (if approver), and the library.
  - The lifecycle mutators (`createReview`, `updateItemResult`, `submitForApproval`, `approveAndPublish`, `rejectPolicy`, `startDraft`/`publishDraft`/`discardDraft`) become async: call the API, then update the stores from the response.
  - `myReviews`/`approvalQueue`/`publishedPolicies` become server-fed lists instead of client-derived filters (the server already filters by owner/status).
- **Snapshot fix:** `versionFor()` and the review views read `review.checklistSnapshot` (the pinned copy returned by the API) instead of looking up the active version. This removes the fallback-to-active bug end to end.
- `computeScores`/`summarizeReview` stay client-side for live display, fed by the snapshot.
- The upload screen stays; the file input is optional and unparsed. Creating a review sends only the metadata (incl. `filename`).
- The access gates (`canUseChecker`, `canApprove`, `canAdmin`) already read `user.permissions.features.*` — unchanged.

---

## 8. Seeding

A first-run seeder (idempotent: runs only when `policy_checklist_version` is empty) loads:
1. the active checklist v2.0 + the 3 standards,
2. the ~60 `policy_library` rows (`source_review_id = null`),
3. the 5 demo `policy_review` rows (snapshot = the seeded active version; `created_by_id = null`; fictional `created_by_name`).

The canonical content lives in the frontend [seed.ts](src/lib/components/policy-review/lib/seed.ts) today. To avoid hand-retyping 70 items, **export it once to a committed JSON file** the backend reads at seed time (`backend/open_webui/internal/policy_review/seed_data.json` or similar). The seeder is invoked on startup after migrations, guarded by the empty-table check and an optional config flag (e.g. `POLICY_REVIEW_SEED_DEMO_DATA`, default true) so a real deployment can later seed canon-only.

**Known demo limitation:** the 5 demo reviews have `created_by_id = null`, so they won't appear under any real user's "My reviews." They will populate the approval queue (`status = pending`) and the library (approved ones). Optionally, the seeder can assign one demo review to the first admin/seed user for a richer "My reviews" demo — deferred decision.

---

## 9. Testing strategy

- **Scoring parity** — Python `scoring.py` vs TS `scoring.ts` produce identical `ScoreResult` on the shared fixtures (submit-gate cases, gate pass/fail, verdict bands, human/pending held aside).
- **Permissions** — every endpoint rejects callers lacking the required permission; admin bypass works; library read works for any verified user.
- **Lifecycle/locking** — submit blocked while items unresolved; submit locks the review to the reviewer; approve publishes to the library + stamps + locks; reject requires a note and returns to the owner; editing a rejected review reopens it.
- **Snapshot guarantee** — create a review, publish a *new* checklist version, confirm the review's snapshot and computed score are unchanged.
- **Seeding** — first run populates checklist + 60 library rows + 5 reviews; a second startup does not duplicate.
- **DAO** — CRUD round-trips for each table; the ≤1-active/≤1-draft invariant holds across publish.

Backend tests follow the repo's existing pytest setup for routers/models. Where practical, write tests first (TDD) for the scorer and the lifecycle transitions.

---

## 10. File map

| Area | Files |
|---|---|
| Models + DAO | `backend/open_webui/models/policy_review.py` (4 table classes + Pydantic models + DAO singletons) |
| Migration | `backend/open_webui/migrations/versions/<rev>_add_policy_review_tables.py` (create 4 tables + indexes) |
| Router | `backend/open_webui/routers/policy_review.py`; registration in `backend/open_webui/main.py` |
| Scoring | `backend/open_webui/utils/policy_review/scoring.py` + tests |
| Seeding | `backend/open_webui/internal/policy_review/seed_data.json` + seeder invoked at startup; one-time export script from `seed.ts` |
| Frontend client | `src/lib/components/policy-review/lib/api.ts` (new) |
| Frontend rewire | `src/lib/components/policy-review/lib/store.ts` (drop localStorage, call API); `lib/reviews.ts` `versionFor()` reads the snapshot |
| Tests | backend pytest (scoring parity, permissions, lifecycle, snapshot, seeding, DAO); shared scoring fixtures in both suites |
| Config | optional `POLICY_REVIEW_SEED_DEMO_DATA` flag in `config.py` (default true) |

No new permission keys (the three exist). The frontend permission constants and Groups UI are unchanged from the finalization phase.

---

## 11. Phases 2 & 3 (roadmap — not built here)

- **Phase 2 — Document upload & parsing:** real upload via the existing `Storage` provider + `Files`; parse docx/pdf/md → text via the retrieval `Loader`/`process_file`; link the stored file + extracted text to the review; wire the upload screen to real upload. No schema change beyond a file reference inside `policy_meta`/`results` (already accommodated).
- **Phase 3 — AI scan:** run each `auto` item against the extracted text via `generate_chat_completion` using the tool's selected model (Anthropic/OpenAI/Gemini/OpenAI-compatible), producing `result` + `comment` + `ref` + `confidence` written into the existing `results` shape; run as an async background job (reuse `tasks.py` + Socket.IO progress); `[H]` items left for the human; a tool-level model-selector setting.

---

## 12. Assumptions & open items

- **Auth'd fetch** in `api.ts` follows whatever convention the existing frontend uses for calling `/api/v1/*` (token/cookie handling) — confirm against a sibling store during implementation.
- **Checklist version id mapping:** backend ids are uuids; the frontend currently uses the label (`v2.0`) as the id. The rewire maps the API's `id`/`label` onto the frontend types; seeded data sets `label = 'v2.0'`.
- **Audit read endpoint** is out of scope (no surface this phase); revisit when the audit UI is designed.
- **Demo-review ownership** (assigning one to a real user) is a deferred seeding nicety.
- **`POLICY_REVIEW_SEED_DEMO_DATA` flag** is a nice-to-have; if it complicates Phase 1, demo data can simply always seed on first run.
