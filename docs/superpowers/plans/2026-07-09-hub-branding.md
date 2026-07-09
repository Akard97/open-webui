# Osool Intelligence Hub Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Global shell shows the platform brand "Osool Intelligence Hub" (sidebar brand, browser tab titles) instead of the sub-product name "Osool AI".

**Architecture:** The brand name flows from one knob: backend `WEBUI_NAME` (env, default `Osool Intelligence Hub`) → `/api/config` `name` → frontend `$WEBUI_NAME` store → sidebar + `<title>` tags. We delete the `WEBUI_NAME=Osool AI` compose override so the fork default takes over, then fix the handful of frontend spots that hardcode a brand string instead of using `$WEBUI_NAME`, and bundle the hub logo as a Vite import so it survives image rebuilds.

**Tech Stack:** SvelteKit (Svelte 4/5 mixed), Vite asset imports, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-07-09-hub-branding-design.md`

## Global Constraints

- Tab title format everywhere: `{Page} • {$WEBUI_NAME}` — bullet `•` (U+2022), never middot `·`; never hardcode the brand string in components.
- The rail item label `Osool AI` in `src/lib/components/app/railItems.ts` is the chat sub-product name — do NOT change it.
- `src/app.html` line 111 static bootstrap `<title>Osool Intelligence Hub</title>` is already correct — do NOT change it.
- Browser favicon, PWA icons, manifest: untouched.
- No unit tests for these changes: they are static markup/branding strings with no logic; verification is by exact grep sweeps (Task 5) plus runtime smoke. Do not build a component-test harness for `<svelte:head>`.
- Two repos: Tasks 2–4 in `C:\Projects\open-webui` (branch `osool`); Task 1 in `C:\Projects\Osool-AI`. Commit each repo separately.
- The user runs their own Vite hot-reload dev server — do NOT start a dev server, and do NOT rebuild the Docker image. Frontend edits are live on save.

---

### Task 1: Remove WEBUI_NAME override from compose files (Osool-AI repo)

**Files:**
- Modify: `C:\Projects\Osool-AI\docker-compose.yml:9`
- Modify: `C:\Projects\Osool-AI\docker-compose.prod.yml:37`

**Interfaces:**
- Produces: backend `/api/config` returns `"name": "Osool Intelligence Hub"` (fork default from `backend/open_webui/env.py`). Every `$WEBUI_NAME` consumer downstream (Tasks 2–4 markup) renders this string.

- [ ] **Step 1: Delete the override in `docker-compose.yml`**

In `C:\Projects\Osool-AI\docker-compose.yml`, the open-webui service currently has:

```yaml
    environment:
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
      - WEBUI_NAME=Osool AI
```

Delete only the `- WEBUI_NAME=Osool AI` line, leaving:

```yaml
    environment:
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
```

- [ ] **Step 2: Delete the override in `docker-compose.prod.yml`**

Same service block currently has:

```yaml
    environment:
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
      - WEBUI_NAME=Osool AI
      - WEBUI_URL=https://${OSOOL_HOSTNAME}
```

Delete only the `- WEBUI_NAME=Osool AI` line, leaving:

```yaml
    environment:
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
      - WEBUI_URL=https://${OSOOL_HOSTNAME}
```

- [ ] **Step 3: Verify compose config no longer carries the var**

Run (in `C:\Projects\Osool-AI`):

```powershell
docker compose config | Select-String WEBUI_NAME
```

Expected: no output.

- [ ] **Step 4: Recreate the open-webui container (env change needs recreate, not restart)**

```powershell
docker compose up -d open-webui
```

Expected: `Container osool-ai-open-webui-1  Recreated` then `Started`.

- [ ] **Step 5: Verify backend reports the new name**

```powershell
Invoke-RestMethod http://localhost:3000/api/config | Select-Object -ExpandProperty name
```

Expected output: `Osool Intelligence Hub`

- [ ] **Step 6: Commit (Osool-AI repo)**

```powershell
git -C C:\Projects\Osool-AI add docker-compose.yml docker-compose.prod.yml
git -C C:\Projects\Osool-AI commit -m @'
chore(compose): drop WEBUI_NAME override, use fork default brand

"Osool AI" is the chat sub-product, not the platform. The open-webui
fork's default WEBUI_NAME is "Osool Intelligence Hub"; removing the
override makes the fork the single source of truth for the brand.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
'@
```

---

### Task 2: Standardize hardcoded tab/notification titles to $WEBUI_NAME (open-webui repo)

**Files:**
- Modify: `src/routes/(app)/workos/+page.svelte:5-7`
- Modify: `src/routes/(app)/policy-review/+page.svelte:5-7`
- Modify: `src/lib/components/channel/Channel.svelte:9-16,277-295`
- Modify: `src/routes/+layout.svelte:485,616,724`

**Interfaces:**
- Consumes: `WEBUI_NAME` writable store from `$lib/stores` (already hydrated from backend config in `+layout.svelte:1031`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: WorkOS page title**

In `src/routes/(app)/workos/+page.svelte`, replace the whole file content's script+head portion. Current file:

```svelte
<script lang="ts">
	import WorkOSApp from '$lib/components/workos/WorkOSApp.svelte';
</script>

<svelte:head>
	<title>WorkOS · Osool</title>
</svelte:head>

<WorkOSApp />
```

New file content:

```svelte
<script lang="ts">
	import WorkOSApp from '$lib/components/workos/WorkOSApp.svelte';
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>WorkOS • {$WEBUI_NAME}</title>
</svelte:head>

<WorkOSApp />
```

- [ ] **Step 2: Policy Review page title**

In `src/routes/(app)/policy-review/+page.svelte`, same shape. Current file:

```svelte
<script lang="ts">
	import PolicyReviewApp from '$lib/components/policy-review/PolicyReviewApp.svelte';
</script>

<svelte:head>
	<title>Policy Review · Osool</title>
</svelte:head>

<PolicyReviewApp />
```

New file content:

```svelte
<script lang="ts">
	import PolicyReviewApp from '$lib/components/policy-review/PolicyReviewApp.svelte';
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>Policy Review • {$WEBUI_NAME}</title>
</svelte:head>

<PolicyReviewApp />
```

- [ ] **Step 3: Channel titles**

In `src/lib/components/channel/Channel.svelte`, add `WEBUI_NAME` to the stores import (lines 9–16). Current:

```ts
	import {
		chatId,
		channels,
		channelId as _channelId,
		showSidebar,
		socket,
		user
	} from '$lib/stores';
```

New:

```ts
	import {
		chatId,
		channels,
		channelId as _channelId,
		showSidebar,
		socket,
		user,
		WEBUI_NAME
	} from '$lib/stores';
```

Then in the `<svelte:head>` block (lines 277–295), replace both hardcoded suffixes. Current:

```svelte
<svelte:head>
	{#if channel?.type === 'dm'}
		<title
			>{channel?.name.trim() ||
				channel?.users.reduce((a, e, i, arr) => {
					if (e.id === $user?.id) {
						return a;
					}

					if (a) {
						return `${a}, ${e.name}`;
					} else {
						return e.name;
					}
				}, '')} • Osool Intelligence Hub</title
		>
	{:else}
		<title>#{channel?.name ?? 'Channel'} • Osool Intelligence Hub</title>
	{/if}
</svelte:head>
```

New:

```svelte
<svelte:head>
	{#if channel?.type === 'dm'}
		<title
			>{channel?.name.trim() ||
				channel?.users.reduce((a, e, i, arr) => {
					if (e.id === $user?.id) {
						return a;
					}

					if (a) {
						return `${a}, ${e.name}`;
					} else {
						return e.name;
					}
				}, '')} • {$WEBUI_NAME}</title
		>
	{:else}
		<title>#{channel?.name ?? 'Channel'} • {$WEBUI_NAME}</title>
	{/if}
</svelte:head>
```

- [ ] **Step 4: Desktop notification titles**

In `src/routes/+layout.svelte` (`WEBUI_NAME` is already imported there — it calls `WEBUI_NAME.set(...)` at line 1031), make three replacements:

Line 485, current:

```ts
					new Notification(`${data.title} • Osool Intelligence Hub`, {
```

New:

```ts
					new Notification(`${data.title} • ${$WEBUI_NAME}`, {
```

Line 616, current:

```ts
							new Notification(`${displayTitle} • Osool Intelligence Hub`, {
```

New:

```ts
							new Notification(`${displayTitle} • ${$WEBUI_NAME}`, {
```

Line 724, current:

```ts
						new Notification(`${title} • Osool Intelligence Hub`, {
```

New:

```ts
						new Notification(`${title} • ${$WEBUI_NAME}`, {
```

- [ ] **Step 5: Verify no hardcoded brand titles remain**

```powershell
git grep -n "· Osool" -- src/
git grep -n "• Osool Intelligence Hub" -- src/
```

Expected: both produce no output.

- [ ] **Step 6: Commit**

```powershell
git add "src/routes/(app)/workos/+page.svelte" "src/routes/(app)/policy-review/+page.svelte" src/lib/components/channel/Channel.svelte src/routes/+layout.svelte
git commit -m @'
fix(branding): use $WEBUI_NAME in all tab and notification titles

WorkOS/Policy Review pages hardcoded "· Osool" and Channel/desktop
notifications hardcoded the full brand. Standardize on
"{Page} • {$WEBUI_NAME}" so the platform name has one source of truth.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
'@
```

---

### Task 3: Bundle the hub logo as a Vite import (open-webui repo)

**Files:**
- Create: `src/lib/assets/osool-logo.png` (byte-for-byte copy of `static/favicon.png`)
- Modify: `src/lib/components/app/AppSidebar.svelte:6,40-47`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `$lib/assets/osool-logo.png` — bundled Osool grid-mark asset; future consumers (mobile shell, login page) should import this instead of `/static/favicon.png`.

- [ ] **Step 1: Copy the logo asset into src**

```powershell
New-Item -ItemType Directory -Force src\lib\assets
Copy-Item static\favicon.png src\lib\assets\osool-logo.png
```

Expected: `src/lib/assets/osool-logo.png` exists (Osool grid mark, ~PNG a few KB).

- [ ] **Step 2: Switch AppSidebar to the bundled import**

In `src/lib/components/app/AppSidebar.svelte`:

Line 6, current (`WEBUI_BASE_URL`'s only use in this file is the logo `src` — verified — so drop it):

```ts
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
```

New:

```ts
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import osoolLogo from '$lib/assets/osool-logo.png';
```

Logo `<img>` (lines 40–47), current:

```svelte
		<span class="w-10 shrink-0 flex items-center justify-center">
			<img
				src="{WEBUI_BASE_URL}/static/favicon.png"
				alt={$WEBUI_NAME}
				class="size-6 rounded object-contain"
				draggable="false"
			/>
		</span>
```

New:

```svelte
		<span class="w-10 shrink-0 flex items-center justify-center">
			<img
				src={osoolLogo}
				alt={$WEBUI_NAME}
				class="size-6 rounded object-contain"
				draggable="false"
			/>
		</span>
```

- [ ] **Step 3: Confirm no other app-shell component uses the /static logo**

```powershell
git grep -n "static/favicon.png" -- src/lib/components/app/
```

Expected: no output. (Other `/static/favicon.png` uses elsewhere — e.g. `+layout.svelte` favicon `<link>`, notification icons — are the actual favicon and stay as-is per spec.)

- [ ] **Step 4: Type/asset check**

The repo already imports `.png` modules (see `src/lib/components/workos/chrome/Sidebar.svelte:10`), so no new type declaration is needed. Sanity-check the import resolves:

```powershell
npx vite build --logLevel error
```

Expected: build completes without "Rollup failed to resolve import" errors. (If the user's Vite dev server is running, the page hot-reloads and the sidebar logo still renders — same visual, now bundled.)

- [ ] **Step 5: Commit**

```powershell
git add src/lib/assets/osool-logo.png src/lib/components/app/AppSidebar.svelte
git commit -m @'
fix(branding): bundle hub logo as Vite import in app sidebar

/static/favicon.png is served from a path that container rebuilds can
reset to the stock icon (same failure mode as the WorkOS logo). Bundle
the Osool grid mark so the sidebar brand always ships with the build.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
'@
```

---

### Task 4: Policy Review breadcrumb root shows the platform brand (open-webui repo)

**Files:**
- Modify: `src/lib/components/policy-review/chrome/Topbar.svelte:1-22`

**Interfaces:**
- Consumes: `WEBUI_NAME` store from `$lib/stores`.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Import the store and fix the crumb**

`Topbar.svelte` is a Svelte 5 component (uses `$derived`). Add the store import to the script block. Current (lines 1–15):

```svelte
<script lang="ts">
	// Top bar: breadcrumb + right-side action buttons.
	// Port of the topbar block from the design's app.jsx.

	import Icon from '../ui/Icon.svelte';
	import { view, stage, goNewReview, canUseChecker, activeReview } from '../lib/store';
	import { POLICY_META } from '../lib/seed';

	let meta = $derived($activeReview?.policyMeta ?? POLICY_META);

	function startNewReview() {
		goNewReview();
	}

</script>
```

New:

```svelte
<script lang="ts">
	// Top bar: breadcrumb + right-side action buttons.
	// Port of the topbar block from the design's app.jsx.

	import Icon from '../ui/Icon.svelte';
	import { WEBUI_NAME } from '$lib/stores';
	import { view, stage, goNewReview, canUseChecker, activeReview } from '../lib/store';
	import { POLICY_META } from '../lib/seed';

	let meta = $derived($activeReview?.policyMeta ?? POLICY_META);

	function startNewReview() {
		goNewReview();
	}

</script>
```

Line 22, current:

```svelte
		<span class="crumb">Osool AI</span>
```

New:

```svelte
		<span class="crumb">{$WEBUI_NAME}</span>
```

- [ ] **Step 2: Verify the module has no other "Osool AI" leftovers**

```powershell
git grep -n "Osool AI" -- src/
```

Expected output: exactly one hit — `src/lib/components/app/railItems.ts:55` (the chat sub-product nav label, intentional).

- [ ] **Step 3: Commit**

```powershell
git add src/lib/components/policy-review/chrome/Topbar.svelte
git commit -m @'
fix(policy-review): breadcrumb root shows platform brand

The crumb hardcoded "Osool AI", which is the chat sub-product, not the
platform. Use $WEBUI_NAME so it reads "Osool Intelligence Hub".

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
'@
```

---

### Task 5: Final verification sweep

**Files:**
- No changes — verification only.

**Interfaces:**
- Consumes: all prior tasks.

- [ ] **Step 1: Static sweeps (open-webui repo)**

```powershell
git grep -n "· Osool" -- src/
```
Expected: no output.

```powershell
git grep -n "• Osool Intelligence Hub" -- src/
```
Expected: no output (all title suffixes now go through `$WEBUI_NAME`).

```powershell
git grep -n "Osool AI" -- src/
```
Expected: only `src/lib/components/app/railItems.ts:55`.

```powershell
git grep -n "static/favicon.png" -- src/lib/components/app/
```
Expected: no output.

- [ ] **Step 2: Runtime smoke (manual, user's running stack — do NOT start a Vite server)**

With the recreated container (Task 1) and the user's hot-reload dev server:

- Sidebar top: Osool grid-mark logo renders; expanded rail reads "Osool Intelligence Hub".
- Tab titles read `Home • Osool Intelligence Hub`, `WorkOS • Osool Intelligence Hub`, `Policy Review • Osool Intelligence Hub`; a chat tab reads `{chat title} • Osool Intelligence Hub`.
- Policy Review breadcrumb root reads "Osool Intelligence Hub".
- Settings → About shows "Osool Intelligence Hub".

If the user's dev server is not running, report the static-sweep results and list these runtime checks as pending manual smoke — do not start a server (standing rule).
