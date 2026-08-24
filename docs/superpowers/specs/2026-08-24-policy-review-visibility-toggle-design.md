# Policy Review Visibility Toggle — Design

**Date:** 2026-08-24
**Status:** Approved (approach A)

## Problem

The Policy Review tool is still in development, but its rail entry is
`visible: () => true`, so every user sees it (e.g. `ahmad@ahmad.com`, a
regular user). We need it hidden from the general user base while it is
being built, with an admin-controlled switch to reveal it when ready.

## Decisions (from brainstorming)

- **When hidden**, the tool remains visible to **admins and users with the
  `features.policy_checker` permission** (option C). These are the people
  building and piloting the tool.
- **Policy Review only.** The WorkOS rail item keeps its current behavior;
  no generic per-tool toggle framework (YAGNI).
- **Approach A:** clone the existing `ENABLE_NOTES` persistent-config
  pattern end-to-end. Runtime-toggleable via webui.db, no rebuild or
  redeploy needed to flip it.

## Design

### 1. Backend config flag

`ENABLE_POLICY_REVIEW` PersistentConfig in
`backend/open_webui/config.py`, next to `ENABLE_NOTES` (~line 1735):

- key path `policy_review.enable`, env var `ENABLE_POLICY_REVIEW`
- **default `False`** — hidden out of the box

Wire-up mirrors `ENABLE_NOTES` exactly:

- `main.py`: import + `app.state.config.ENABLE_POLICY_REVIEW = ENABLE_POLICY_REVIEW`
- `main.py` `/api/config` features dict (~line 2443):
  `'enable_policy_review': app.state.config.ENABLE_POLICY_REVIEW`
  (exposed to all logged-in users, same as `enable_notes`)
- `routers/auths.py` admin config GET / AdminConfig model / POST:
  add `ENABLE_POLICY_REVIEW` to all three places (~lines 1023, 1053, 1086, 1131)

### 2. Admin UI switch

`src/lib/components/admin/Settings/General.svelte`, features block
(next to the Notes switch, ~line 632):

```svelte
<div class="mb-2.5 flex w-full items-center justify-between pr-2">
    <div class=" self-center text-xs font-medium">
        {$i18n.t('Policy Review')} ({$i18n.t('Beta')})
    </div>
    <Switch bind:state={adminConfig.ENABLE_POLICY_REVIEW} />
</div>
```

`adminConfig` is fetched/saved through the existing admin config
endpoints, so no new frontend API code.

### 3. Shared visibility predicate

New exported helper in
`src/lib/components/policy-review/lib/visibility.ts`:

```ts
export function canSeePolicyReview(ctx: { user: any; config: any }): boolean {
    return (
        (ctx.config?.features?.enable_policy_review ?? false) ||
        ctx.user?.role === 'admin' ||
        !!ctx.user?.permissions?.features?.policy_checker
    );
}
```

One predicate, used by both the rail and the route guard, so they can
never disagree.

### 4. Rail item

`src/lib/components/app/railItems.ts` — replace `visible: () => true`
on the `policy-review` entry with `visible: canSeePolicyReview`, and
update the comment to describe the new gating.

### 5. Route guard

`src/routes/(app)/policy-review/+layout.svelte` — on mount, if
`!canSeePolicyReview({ user: $user, config: $config })`, redirect with
`goto('/home')` before rendering children. Blocks deep links for
ineligible users. (Client-side guard only — the policy-review backend
endpoints already enforce their own permission checks server-side; the
library-read endpoints remain open, which matches current behavior.)

### 6. Tests

- **Frontend (vitest):** `src/lib/components/policy-review/lib/visibility.test.ts` —
  table-driven cases for `canSeePolicyReview`: flag on/off × role
  admin/user × policy_checker true/false/missing. (Rail wiring is not
  unit-tested — importing `railItems.ts` would pull Svelte icon
  components into vitest; the manual smoke test covers it.)
- **Backend (pytest):** `test_config_flag.py` — `ENABLE_POLICY_REVIEW`
  defaults to `False`. (Admin-config round-trip needs the full app;
  covered by the manual smoke test instead.)

## Error handling

- `config` or `user` not yet loaded → predicate returns `false` for
  plain users (`?? false` on the flag) unless admin/permission matches;
  rail simply omits the item until stores populate. No crash paths.
- Flag flipped off while a user is inside the tool → they keep their
  session until next navigation/reload; acceptable for a beta toggle
  (same behavior as ENABLE_NOTES).

## Out of scope

- WorkOS gating (explicitly deferred).
- Server-side blocking of policy library read endpoints.
- Generic multi-tool visibility framework.
