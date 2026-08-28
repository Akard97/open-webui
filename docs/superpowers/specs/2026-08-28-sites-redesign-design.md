# Sites Tool Redesign — Design Spec

Date: 2026-08-28
Status: Approved (mockup: `scratchpad/sites-redesign-mockup.html`, artifact "Sites Redesign")
Scope: **Frontend only.** Backend routers, models, and API client are untouched.

## 1. Goal

Rebuild the Sites tool UI as a centered two-column workbench: a left rail listing the
user's sites, and a detail panel showing the selected site across tabs (Overview,
Files, Settings, Analytics, Versions). Analytics and Versions are **design-preview
mockups** with clearly labeled sample data until the features ship. The modal-based
`SiteEditor` is removed; creating a site happens inline in the detail panel.

Decisions locked with the user:

- Create flow: **inline in the detail panel** (no modal).
- Mood: **clean pro dashboard with Osool accents** (Vercel/Netlify calm, teal used
  sparingly for primary actions and live status).
- Detail structure: **Overview + 4 tabs** (Files, Settings, Analytics, Versions).
- Unimplemented tabs: **realistic sample data + "PREVIEW" pill**, plus a caption
  "Sample data — ships in a later phase".
- Implementation: **full rebuild, plain Tailwind** (no shadcn — that is scoped to
  WorkOS), reusing app conventions and existing `ConfirmDialog`.

## 2. Layout

Everything renders inside the existing `/sites` route and app shell (app sidebar
stays). The tool itself is a centered frame:

```
┌─ page (max-w ~1160px, centered) ─────────────────────────────┐
│ Sites            Publish static pages and share them…        │
│ ┌─ shell card (border, rounded-2xl, shadow, min-h 640px) ──┐ │
│ │ rail 280px │ detail (flex-1)                             │ │
│ │ ─ ＋ New site (teal) │ header: name, URL+copy, Live pill │ │
│ │ ─ My sites/All users │ tabs: Overview Files Settings     │ │
│ │ ─ site list          │       Analytics° Versions°        │ │
│ │                      │ active pane                       │ │
│ └──────────────────────┴───────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
° = PREVIEW pill
```

Responsive: below ~860px the grid stacks — rail on top (border-bottom instead of
border-right), detail below. Stat grids collapse 4→2→1 columns. No horizontal page
scroll; wide content scrolls in its own container.

## 3. Components

All under `src/lib/components/sites/`. `SiteEditor.svelte` is **deleted**.
`lib/access.ts` and `lib/visibility.ts` stay as-is.

| Component | Responsibility |
| --- | --- |
| `SitesPage.svelte` | Shell + state owner: loads sites, holds `selectedId`, `tab`, `mode` (`view` \| `create`), `showAll`; renders rail + detail; hosts delete `ConfirmDialog`. |
| `SiteRail.svelte` | "＋ New site" button, admin My sites / All users segmented toggle, site list (live dot, name, visibility chip, mono slug, owner name when All users). Emits `select(site)`, `create()`, `toggleAll()`. |
| `SiteDetail.svelte` | Header (name, URL line + copy, Live/Private pill, Open button) + tab bar + renders active tab component. |
| `tabs/OverviewTab.svelte` | URL card (copy / open), stat tiles (Views·7d **preview**, Files count + total size, Visibility, Updated + relative time), Details panel (entry file, created, owner), Quick actions panel (jump links to Files / Settings / Versions tabs). |
| `tabs/FilesTab.svelte` | Dropzone (replace semantics, identical to current editor), staged-file list with ENTRY badge and sizes, "Opens with" select when >1 HTML, "Publish changes" button → `updateSite`. |
| `tabs/SettingsTab.svelte` | Name, slug (with origin prefix, auto-slugify until touched — port existing logic), who-can-view radio cards + `AccessControl` when "specific", "Save changes" → `updateSite` + `updateSiteAccess` (keep the existing partial-failure toast: files saved but access failed). Danger zone → delete confirm. |
| `tabs/AnalyticsTab.svelte` | **Static preview.** Inline-SVG 30-day area chart (Osool 3125C stroke, soft fill), 3 KPI tiles, top-pages table with proportion bars. Hardcoded sample data; PREVIEW pill in tab label + caption under the chart. No API calls. |
| `tabs/VersionsTab.svelte` | **Static preview.** Timeline list (v3 CURRENT with green ring, v2/v1 with Restore buttons that do nothing but are visually complete). Sample data; PREVIEW pill + caption. |
| `CreatePanel.svelte` | Inline create form replacing detail panel: name, link, dropzone, who-can-view radio cards, Cancel / Publish. On success: reload list, select new site, switch to `view` mode + Overview tab. Reuses the same dropzone + radio-card markup as Files/Settings (extract `FileDrop.svelte` + `VisibilityPicker.svelte` shared subcomponents). |

State flow: `SitesPage` owns everything; children are presentational and emit
callbacks. Selecting a site resets `tab` to Overview. After delete: select the next
remaining site or show the empty state.

Empty states:

- Zero sites → detail area shows a centered invite ("Nothing published yet…") with a
  Publish CTA that opens the create panel.
- No selection is impossible in view mode (first site auto-selected on load).

## 4. Visual language

Scoped token block on the shell root (`.sites-root`), dark values under
`.dark .sites-root` (app toggles the `dark` class on `<html>`):

| Token | Light | Dark |
| --- | --- | --- |
| ground | `#f7f9f9` | `#0b1416` |
| card | `#ffffff` | `#111c1f` |
| ink | `#16282d` | `#e4edee` |
| muted / faint | `#5d7176` / `#8fa0a4` | `#93a6aa` / `#5f7478` |
| border / hairline | `#e2e9ea` / `#edf2f3` | `#223236` / `#1a282b` |
| accent (Osool 315C family) | `#00677F` | `#2fb8cf` |
| accent-soft / soft-ink | `#e3f1f4` / `#00566a` | `#123239` / `#7fd4e4` |
| live (Osool 576C) | `#789D4A` | `#9dc06a` |
| danger | `#c2410c` | `#f0824d` |
| chart (Osool 3125C) | `#00A9CE` | `#2fb8cf` |

Type: app font stack for UI; slugs, URLs, and filenames in `font-mono`
(Tailwind); stat numerals `tabular-nums`. Headings tight letter-spacing.
Site name in detail header uses the deep teal ink.

## 5. Motion (Emil rules)

- Tab pane switch: 180ms enter, `cubic-bezier(0.23,1,0.32,1)` (strong ease-out),
  opacity 0→1 + translateY(4px)→0. No exit animation (instant swap).
- Pressables (`New site`, buttons, copy): `scale(0.97)` on `:active`,
  `transition: transform 140ms ease-out`. Never `transition: all`.
- Live pill dot: 2.4s opacity pulse.
- Copy buttons flip label to "Copied ✓" for 1.2s (no animation).
- Hover states gated behind `@media (hover:hover) and (pointer:fine)`.
- `prefers-reduced-motion: reduce` → disable pane translate and pulse (keep
  opacity fades).
- No animation on keyboard-driven focus traversal.

## 6. Data & API

Existing client functions only: `getSites(token, showAll)`, `createSite`,
`updateSite`, `updateSiteAccess`, `deleteSite`. Backend already returns
`files: [{name,size,content_type}]`, `created_at`, `updated_at` — Overview's
Files/size/Updated tiles use real data. Views tile is preview-labeled sample.
`siteAccessLevel()` / `isEveryoneGrant()` keep powering visibility chips and
radio state. Timestamps rendered as relative ("2 days ago") via existing
dayjs utilities used elsewhere in the app.

## 7. Errors & edge cases

- All strings through `$i18n.t`; toasts via `svelte-sonner` (unchanged pattern).
- Preserve the existing two-step save failure message in Settings ("Site files
  saved, but updating who can view failed…").
- Duplicate-filename and case-insensitive checks stay server-side; surface errors
  via toast as today.
- Admin "All users" view: owner name under site rows; admins can open, edit, and
  delete other users' sites (backend already authorizes admin).
- Deleting the currently selected site selects the next site, else empty state.
- Create panel Cancel returns to previously selected site (or empty state).

## 8. Testing

- Frontend unit tests (vitest) where the app has them for sites — port/replace any
  existing component tests; cover: slugify auto-fill until touched, entry-file
  defaulting (`index.html` wins), grantsForLevel mapping, delete-selects-next logic.
- Backend suites untouched (must stay green: sites 47+19).
- Manual browser smoke checklist (post-build): list/select, create inline, replace
  files, entry select, access change each level, delete, admin All-users, dark mode,
  narrow width, reduced motion.

## 9. Out of scope / future

- Real analytics (needs request logging — separate backend phase).
- Real version history (needs snapshot storage — separate backend phase).
- URL deep-linking (`/sites?site=…`) — nice-to-have follow-up.
- QR code sharing — dropped from mockup review.
