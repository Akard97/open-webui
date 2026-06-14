# Policy Review (PRP) tool — UI/UX finalization design

**Date:** 2026-06-14
**Status:** Approved (brainstorming) — ready for implementation planning
**Scope:** Finalize the full product UI/UX (frontend + seeded mock data) for the Policy Review tool *before* the backend is built. Outcome is a complete, navigable, clickable prototype whose data model is backend-shaped (not throwaway).

Related: `2026-06-14-policy-review-cleanup-design.md`, memory `policy-review-access`, `osool-rebrand`.

---

## 1. Purpose & context

The Policy Review tool (`/policy-review`) lets the Organizational Excellence (OE) team review draft policies against the **PRP Master Checklist v2.0** and publish approved policies into a Library that all staff can read. The checklist is a real artifact: 6 themes (T1–T6), 70 items, weighted scoring, two mandatory gates (T1, T2 at ≥85%), three verdicts (Approved ≥85% + gates / Conditional ≥70% + gates / Rejected <70% or gate fail). Some items are flagged `[H]` — they require human judgment and the AI leaves them blank.

This phase finalizes the **whole** user journey (reviewer → approver → admin → viewer), fixes the gaps left by the prior cleanup pass, and adds a new **tool-admin page** that makes the checklist fully editable and versioned. It remains frontend-only with seeded data; no real backend endpoints, file parsing, or AI scanning yet.

### Decisions locked during brainstorming
1. **Admin access** = a new group-assignable permission `features.policy_admin` (third permission alongside `policy_checker`, `policy_approver`). System admins always have it.
2. **Checklist control depth** = full structural control (items, themes, weights, gates, thresholds, codes, auto/human flags) **plus** a draft → publish versioning lifecycle.
3. **Demo approach** = seed every queue with mock data; demo via real logins / group-permission toggles. **No persona switcher.**
4. **Navigation** = lean and role-aware, with an Overview landing page; every visible nav item works; placeholder items removed.

---

## 2. Roles & information architecture

Four independent, stackable capabilities. A user's surface is the **union** of every permission they hold. System admins (`user.role === 'admin'`) pass all four gates.

| Surface | Viewer (all) | Reviewer `policy_checker` | Approver `policy_approver` | Admin `policy_admin` |
|---|:--:|:--:|:--:|:--:|
| Overview (role-aware landing) | ✓ | ✓ | ✓ | ✓ |
| Policy library (read published) | ✓ | ✓ | ✓ | ✓ |
| New review (upload → scan → review) | — | ✓ | — | — |
| My reviews (track own, fix rejects) | — | ✓ | — | — |
| Approval queue (approve/reject/publish) | — | — | ✓ | — |
| Checklist admin (structure + versions) | — | — | — | ✓ |

**Sidebar (lean, role-aware):** Search · Overview · Policy library · — *Reviewing* — New review · My reviews · — *Approvals* — Approval queue (count) · — *Administration* — Checklist admin · (footer: identity + honest role label).

**Removed** (inert placeholders / fake counts): Dashboard placeholder, "In Review", "Compliance Checker", Exceptions, Templates, Audit log, Settings, and the hardcoded 142/7/3 counts.

**Gates** live in `policy-review/lib/store.ts` as derived stores: `canUseChecker`, `canApprove` (existing) and **new** `canAdmin = role==='admin' || features.policy_admin`. The Hub rail entry stays `visible: () => true` (everyone can reach the Library).

**Library visibility rule:** the Library shows **published canon only**. Pipeline states (draft / in-review / pending / rejected) live in the OE surfaces (My reviews, Approval queue), not in front of general staff.

---

## 3. Review lifecycle & locking

A *review* is the unit of work. It moves through a state machine; locking + library-publish behavior is what closes the previously-deferred gaps.

```
Upload → AI scan → Review (draft) → [submit] → Pending approval
                                                   ├─ [approve & publish] → Published (Library)
                                                   └─ [reject + note] → Returned → (reopens) → Review (draft)
```

**Statuses:** `draft` → `pending` → `approved` | `rejected`; `rejected` reopens to `draft`.

**Locking rules:**
- **Draft** — reviewer freely edits verdicts/overrides/comments, resolves `[H]` items. **Submit is blocked** until every item is resolved (no `pending`, no unresolved `human`).
- **Pending** — review is **read-only for the reviewer** (no edits, no Reset); it appears in the approver's queue. *(Fixes the ungated reset / edit-after-submit gap.)*
- **Published** — locked for everyone; policy is **inserted into the Library** as published canon with its score/verdict; decision is stamped (`decidedBy`, `decidedAt`). *(Fixes "publish didn't publish".)*
- **Returned** — reject requires a note; the review **reopens as draft** for fix + resubmit.

**Gaps closed** (from the prior pass): (1) approver-only users now land on a reachable Approval queue instead of being bounced to the Library; (2) the Approval queue is a real surface; (3) approve publishes + locks, submit locks.

---

## 4. The four journeys

- **Viewer (everyone):** Overview → Library → open policy → read (summary, outline, status, score, related). Published canon only.
- **Reviewer / maker (`policy_checker`):** New review → upload → AI scan runs *auto* items against the **active published checklist version** → Review workspace (themed checklist, AI verdicts with confidence + citations, resolve `[H]`, override/comment) → Submit for approval (note) → tracked in My reviews as Pending; if Returned, fix + resubmit.
- **Approver / checker (`policy_approver`):** Approval queue (seeded + in-session submissions) → open a submission → read-only review + full decision context (weighted score, gate pass/fail, verdict, strengths, critical gaps, reviewer note) → Approve & publish **or** Reject + note.
- **Admin (`policy_admin`):** Checklist admin → edit draft → Publish a new version → active for *new* reviews; in-flight reviews keep their snapshot.

**UploadView fix:** it currently advertises a fictional theme set (GOV/SCO/PRO/CTR/RSK/REV). Replace so upload, scan, review, and admin all read the *same* active checklist (real T1–T6).

---

## 5. Admin page & checklist versioning

**Four tabs:**
1. **Checklist** — live tree editor: themes → PRP groups → items, add/reorder/edit/remove at every level. Per **item**: requirement text, standard-code tags, `auto` vs `human [H]` flag. Per **theme**: name, weight %, gate on/off, threshold. Per **PRP group**: code, title, intent.
2. **Scoring & gates** — verdict bands (≥85 / ≥70 / fail), gate thresholds, weights panel enforcing *themes sum to 100%*.
3. **Standards & codes** — manage the code vocabulary (OEC, ISO 9001:2015, OM / Osool Metapolicy): label, abbreviation, description. Item tags come from this controlled list.
4. **Access** — read-only summary of which groups hold each permission, with a link to the real group-permissions screen (no duplication of the permission system).

**Versioning model:**
- **One working draft** at a time; admin edits accumulate there and affect nothing live until Publish.
- **Publish validates, then freezes:** weights sum to 100%, every theme/PRP group has ≥1 item, and the admin sees an impact summary (items added/removed/reworded). Result is a new **immutable** version (e.g. v2.1) that becomes Active; the previous Active drops into history.
- **Reviews snapshot on start:** a new review records *which version* it's assessed against and carries that snapshot for life. Publishing never moves the goalposts under an in-flight reviewer; every review shows its checklist-version provenance (audit).
- **History** is viewable, read-only.

---

## 6. Prototype state & data model

Two aggregate roots: the versioned **checklist definition**, and **reviews** that snapshot it. This forces a split that today's `mocks.ts` conflates (definition vs. a specific review's answers) — and it's the same shape the backend will expose.

**Checklist definition (versioned):**
- `Theme` — id, name, weight, gate, threshold.
- `Section` (PRP group) — id, theme, title, codes, intent, `items: ChecklistItemDef[]`.
- `ChecklistItemDef` — id, n, text, codes, `assessment: 'auto' | 'human'`.
- `ChecklistVersion` — id, label (`v2.0`), `status: 'active' | 'draft' | 'archived'`, publishedAt, publishedBy, changeSummary, themes, sections, verdictBands.

**Review (per policy):**
- `Review` — id, policyMeta, `checklistVersionId` (snapshot), `results: Record<itemId, ItemResult>`, `status`, `approval`, createdBy, createdAt.
- `ItemResult` — itemId, `result: 'compliant' | 'non-compliant' | 'human' | 'pending'`, comment?, ref?, confidence?, reviewed?, edited?.

**Store (`policy-review/lib`):**
- `checklist` store — `versions: ChecklistVersion[]` (seeded v2.0 = today's `THEMES` + `SECTIONS`, *definition only*), editable `draft`, derived `activeVersion`.
- `reviews` store — `reviews: Review[]` (replaces the single global `sections`/`approval`), `activeReviewId`.
- Derived, role-filtered — `myReviews` (= reviews I created), `approvalQueue` (= `status === 'pending'`), Library = seeded published `POLICIES` **plus** any review that reaches `approved`. New gate `canAdmin`.
- Lifecycle mutators — `createReview`, `submitForApproval`, `approveAndPublish` (→ insert into library), `rejectPolicy`, plus checklist `editDraft` / `publishDraft`.

**Seeded so every surface is populated without a persona switcher:**
- "Digital City Asset Disposal Policy" stays as one in-progress review (rich workspace).
- Several `pending` reviews (other policies/owners) so the queue always has work.
- A couple `approved` + `rejected` for My reviews history and the Returned→edit loop.
- `POLICIES` remains the published Library canon.
- "Top Strengths" becomes per-review seeded data (not a hardcoded global as it is today in `ReviewView`).

**Persistence:** bump localStorage key to `osool.policyReview.v3`; discard/reseed the old v2 shape (acceptable for a prototype).

**Routing:** `PolicyReviewApp.svelte` switches on `view ∈ {overview, library, new-review, my-reviews, approvals, admin}`, each gated per the matrix; Overview/Library open to all.

---

## 7. Scope boundaries

**Built now (clickable, frontend + seeded data):**
- `policy_admin` permission (group-assignable) + "Policy Admin" toggle.
- Lean role-aware shell + 6 views.
- Review lifecycle with real locking; approve → insert into Library; reject → reopen.
- Admin page (4 tabs) + draft → publish versioning + snapshot-on-review.
- Data-model refactor (checklist-versions + reviews stores + seeded data); UploadView themes fix.

**Deferred to the backend phase (not faked now):**
- Real file upload/parse and real AI scanning (Scan advances with seeded verdicts).
- Multi-user persistence & true cross-user handoff (queues are per-browser seeded).
- Real publish to a shared store, and **endpoint-level permission enforcement** (checker on upload/submit, approver on approve/reject, admin on checklist mutations, library read open to `get_verified_user`).
- Audit log surface, approver notifications, checklist import/export, real side-by-side document viewer (citations stay as quotes).

**One backend touch this phase:** registering `policy_admin` edits `backend/open_webui/config.py` for the permission *default* only — mirrors `policy_checker`/`policy_approver` exactly. Everything else is frontend.

---

## 8. File map

| Area | Files |
|---|---|
| Permission | `backend/open_webui/config.py` (add `policy_admin` default), `src/lib/constants/permissions.ts`, `admin/Users/Groups/Permissions.svelte` |
| Types & data | `policy-review/lib/types.ts` (split def vs review), `lib/seed.ts` (was `mocks.ts`), `lib/checklist.ts` (new: clone/validate/publish), `lib/scoring.ts` (adapt to results-by-itemId) |
| State | `lib/store.ts` (checklist + reviews stores, `canAdmin`, lifecycle mutators) |
| Shell | `PolicyReviewApp.svelte` (6-view routing), `chrome/ToolSidebar.svelte` (lean nav), `chrome/Topbar.svelte` |
| Views | `OverviewView` (new), `AllPoliciesView` (role-filter to published), `UploadView`/`ScanningView`/`ReviewView` (per-review + active checklist + lock), `MyReviewsView` (new), `ApprovalQueueView` (new) |
| Admin | `views/admin/AdminApp.svelte` + `ChecklistTab` / `ScoringTab` / `StandardsTab` / `AccessTab` (all new) |
| Overlays | `ItemDrawer`, `SubmitApprovalModal`, `ApprovalBanner`, `PolicyPopup` (adapt to per-review model) |
| Rail | `app/railItems.ts` — unchanged (Library visible to all) |

---

## 9. Assumptions & defaults

- **Overview landing** is composed per role: viewer = recently published + search; reviewer = my open reviews + start new; approver = pending count + queue; admin = active version + draft status. Multi-role users see the union.
- **Standard codes seed** = OEC (Organizational Excellence Checklist), ISO 9001:2015, OM (Osool Metapolicy).
- **`[H]` items** map to `assessment: 'human'` in the definition; the scan leaves them `pending`/`human` for the reviewer.
- Scoring logic is unchanged in spirit (weighted theme average + gates + verdict bands), adapted to read `ItemResult` by `itemId` against a snapshot's themes.
