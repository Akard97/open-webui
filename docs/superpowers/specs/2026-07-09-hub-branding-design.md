# Hub Branding — "Osool Intelligence Hub" Platform Brand

**Date:** 2026-07-09
**Status:** Approved (design), pending implementation
**Repos touched:** `open-webui` fork (this repo) + `Osool-AI` (compose files only)

## Problem

The app currently presents itself as "Osool AI" in the global shell (sidebar brand,
browser tab titles), but "Osool AI" is one sub-product of the platform — alongside
WorkOS and Policy Review. The platform brand is **Osool Intelligence Hub** and the
global shell must reflect it.

Root cause: `docker-compose.yml` and `docker-compose.prod.yml` in the Osool-AI repo
set `WEBUI_NAME=Osool AI`, overriding the fork's default (`Osool Intelligence Hub`
in both `backend/open_webui/env.py` and `src/lib/constants.ts` `APP_NAME`). The
frontend `$WEBUI_NAME` store is hydrated from backend config (`backendConfig.name`),
so the override propagates to the sidebar, tab titles, PWA manifest, opensearch
descriptor, and the About page.

## Decisions

1. **Tab title convention:** `{Page} • Osool Intelligence Hub` everywhere, via
   `$WEBUI_NAME` (never hardcoded). Full brand name; no short variant.
2. **Hub logo:** bundled Vite import (same pattern as the WorkOS logo fix), not a
   `/static` URL — the backend static copy is wiped on image rebuild.
3. **Scope:** platform brand only. Sub-product logos (rail icons for Osool AI /
   WorkOS / Policy Review) stay as the current generic line icons; a per-module
   logo pass is a separate future effort.

## Changes

### 1. Name source of truth (Osool-AI repo)

Remove the `WEBUI_NAME=Osool AI` line from:

- `docker-compose.yml` (open-webui service environment)
- `docker-compose.prod.yml` (same)

The fork default `Osool Intelligence Hub` takes over. Requires a container
**recreate** (env change; restart is not enough). This alone fixes: sidebar brand
text, every `{page} • {$WEBUI_NAME}` title, PWA manifest name/short_name,
opensearch, Settings → About.

### 2. Tab title standardization (this repo)

Rule: every `<svelte:head><title>` is `{Page} • {$WEBUI_NAME}`.

Known offenders to fix:

- `src/routes/(app)/workos/+page.svelte` — `WorkOS · Osool` → `WorkOS • {$WEBUI_NAME}`
- `src/routes/(app)/policy-review/+page.svelte` — `Policy Review · Osool` →
  `Policy Review • {$WEBUI_NAME}`
- `src/lib/components/channel/Channel.svelte` (~line 294) — hardcoded
  `#{channel} • Osool Intelligence Hub` → use `$WEBUI_NAME`
- `src/routes/+layout.svelte` (~lines 485, 616, 724) — desktop `Notification`
  titles hardcode `• Osool Intelligence Hub` → use `$WEBUI_NAME`

Implementation also audits all remaining `<title>` blocks (`grep '<title'`) and
aligns any other hardcoded or odd-format titles found.

### 3. Hub logo bundling (this repo)

- Copy `static/favicon.png` (Osool grid mark) → `src/lib/assets/osool-logo.png`.
- `src/lib/components/app/AppSidebar.svelte`: replace
  `src="{WEBUI_BASE_URL}/static/favicon.png"` with the bundled import.
- Check `MobileRailDrawer.svelte` / `MobileAppBar.svelte` for the same `/static`
  logo pattern and apply the same fix if present.
- Browser favicon, PWA icons, and manifest are **not** touched.

### 4. Policy Review breadcrumb (this repo)

`src/lib/components/policy-review/chrome/Topbar.svelte` (~line 22): root crumb
`Osool AI` → `{$WEBUI_NAME}` (renders "Osool Intelligence Hub").

## Out of scope

- Per-module logos/wordmarks in the rail or module headers.
- Favicon / PWA icon redesign.
- Backend network identifiers (User-Agent, HTTP-Referer, favicon URL) — per the
  standing rebrand decision, these stay as-is for now.
- i18n string audit (en-US/ar already say "Osool Intelligence Hub" where relevant).

## Testing

**Static:**

- `grep -rn "· Osool" src/` → no matches.
- `grep -rn "Osool AI" src/` → only `railItems.ts` label (the chat module nav
  item — intentionally "Osool AI").
- `grep -rn "Osool Intelligence Hub" src/` → only `app.html` bootstrap title,
  `constants.ts` `APP_NAME`, and i18n strings; no hardcoded titles in components.

**Runtime (after container recreate + Vite hot reload):**

- Sidebar brand shows the bundled logo + "Osool Intelligence Hub".
- Tab titles: Home, chat, WorkOS, Policy Review all read
  `{Page} • Osool Intelligence Hub`.
- Policy Review breadcrumb root reads "Osool Intelligence Hub".
- Settings → About shows "Osool Intelligence Hub".
