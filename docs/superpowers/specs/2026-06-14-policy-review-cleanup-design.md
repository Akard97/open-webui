# Policy Review — UI honesty/cleanup pass

**Date:** 2026-06-14
**Status:** Approved (design)
**Scope:** Frontend only. No store, workflow, permission, or backend changes.

## Context

The Policy Review tool (`/policy-review`) is an OE-owned maker-checker workflow
(reviewer uploads/scans/reviews → approver approves & publishes) with a Policy
Library open to all users. See [[policy-review-access]].

The tool is currently frontend-only with mock data. A full review of the
three-role user journey (viewer / reviewer / approver) surfaced deeper workflow
gaps (no approver inbox, the submit→approve→publish loop doesn't visibly close,
reviews don't lock after submission). **Those are explicitly deferred** — they
belong with the backend work and were ruled out of scope for this pass.

What this pass addresses: the UI presents several elements that claim data or
activity that does not exist, and mislabels every user as part of the OE team.
The goal is that **nothing on screen is false**, without changing how the tool
behaves.

## Goal

Remove false/placeholder UI surfaces so the tool is honest about its current
(mock, single-review) state, while leaving all behaviour unchanged.

## Scope

### In scope — three changes

1. **Sidebar: remove the "Recent reviews" + "Archived" lists.**
   - File: `src/lib/components/policy-review/chrome/ToolSidebar.svelte`
   - Remove the `Recent reviews` heading and the `sb-chats` block (the
     `recent` list, the nested `Archived` heading, and the `archived` list) —
     currently markup lines ~111–129.
   - Remove the now-unused `recent` and `archived` data arrays (~32–45) and the
     `pillClass` helper (~47–49).
   - Result: the sidebar ends with the Workspace nav group → foot-links
     (Templates / Audit log / Settings) → user footer.

2. **Topbar: remove the sync badge.**
   - File: `src/lib/components/policy-review/chrome/Topbar.svelte`
   - Remove the `pl-topbar-sync` span (~43–52) — the
     "Synced 14m ago · Etimad · SharePoint · Drive" indicator implies a live
     ingestion pipeline that does not exist.
   - Remove the now-unused `syncedMinutesAgo`, `stale`, and `syncLabel`
     constants (~16–21).
   - `tb-actions` retains only the contextual New review / Export buttons
     (shown for checkers in the review stage).

3. **Footer: honest per-user identity.**
   - File: `src/lib/components/policy-review/chrome/ToolSidebar.svelte` (~144–148)
   - Today the footer hardcodes "Organizational Excellence" as every user's
     department, appending "· Approver" / "· Reviewer" when applicable — so a
     plain viewer who is not OE is still labelled OE.
   - New behaviour, derived only from data we can verify
     (`canApprove` / `canUseChecker`):
     - Approver → `Organizational Excellence · Approver`
     - Reviewer (checker, not approver) → `Organizational Excellence · Reviewer`
     - Everyone else (plain viewer) → `Viewer` (no OE department)
   - The user name continues to come from `$user.name`.

4. **Orphaned CSS cleanup** (consequence of 1 & 2).
   - File: `src/lib/components/policy-review/styles.css`
   - After removal these selectors are referenced nowhere else (verified by
     search — only ToolSidebar/Topbar use them): `.sb-chats`, `.sb-chat`
     and descendants, `.pill` / `.pill-inreview` / `.pill-approved` /
     `.pill-draft` / `.pill-rejected` (~107–121); `.pl-topbar-sync` and its
     `.dot` / `.stale` variants (~1467–1491).
   - Remove these blocks. Confirm exact boundaries at edit time (line numbers
     are approximate) and re-confirm no other usage before deleting.

### Out of scope (intentionally left as-is)

- **Dead sidebar nav items** — Search, Dashboard, In Review, Approvals,
  Compliance Checker, Exceptions, Templates, Audit log, Settings — and their
  counts (`142`, `7`, `3`). Kept untouched per explicit decision.
- **All workflow logic** — upload, scanning, review/override, submit, approve,
  reject, publish; the stores in `lib/store.ts`; persistence.
- **Permissions** — `features.policy_checker` / `features.policy_approver`,
  rail visibility, admin toggles, backend config.
- **Library popup** Download / Open PDF buttons (real future functionality,
  not decorative falsehoods).
- The deeper journey gaps (approver inbox, closing the publish loop, locking a
  review after submission) — deferred to the backend phase.

## Non-goals

This is not a redesign and not a behaviour change. A user who runs the tool
before and after this pass performs the exact same actions with the exact same
results; only the false/placeholder chrome is gone.

## Verification

- Run the existing frontend checks (lint / typecheck / build) for the touched
  files; ensure no unused-variable or unused-import warnings remain after the
  array/helper/constant removals.
- Manual smoke (mock data):
  - Sidebar no longer shows Recent/Archived; Workspace nav and footer render.
  - Topbar no longer shows the sync badge; contextual buttons still appear in
    the review stage for a checker.
  - Footer label: approver shows "· Approver", reviewer shows "· Reviewer",
    a plain (no-permission) user shows "Viewer" with no OE department. Verify
    by toggling `policy_checker` / `policy_approver` (or admin vs plain user).
- Grep the policy-review folder to confirm the removed CSS classes have no
  remaining references.

## Risks

- **Low.** Pure deletion + one label-logic change, scoped to three files
  (plus their shared stylesheet). No shared utilities or stores are modified.
  Main risk is removing a CSS block still referenced elsewhere — mitigated by
  re-confirming usage at edit time.
