# Site Publisher — Design

**Date:** 2026-08-26
**Status:** Approved (pending spec review)
**Branch:** `osool`

## Purpose

A bonus tool that lets selected users publish small static websites (HTML plus supporting
files such as images or CSS) and share them under custom links on the app's own domain,
e.g. `https://ai.osoolre.com/sites/<slug>`. The typical source is a page generated with
claude.ai that the user wants to host and share.

Each user can publish many sites, and every site carries its own access level.

## Decisions (locked with user)

1. **URL scheme:** fixed prefix. The app owns `/sites/`; the user chooses only the slug.
   Example: `ai.osoolre.com/sites/test`.
2. **Publish gate:** admin-granted permission `features.site_publisher` (same mechanism as
   `features.policy_checker`), toggleable per group in the admin panel. Admins bypass.
3. **Session isolation:** published pages are served with
   `Content-Security-Policy: sandbox allow-scripts`. Scripts run, but the page gets an
   opaque origin — it cannot read localStorage, cookies, or call the API with the viewer's
   credentials. No separate subdomain and no script stripping.
4. **Upload shape:** multi-file picker, flat structure (no subfolders). Relative references
   in the HTML resolve because assets are served next to the entry file.
5. **Architecture:** lean self-contained option — one new `site` table, file bytes on disk,
   sharing via the existing `access_grant` table.

## Data model

One new table `site` (Alembic migration; head at time of writing: `d3e4f5a6b7c8`):

| column        | type    | notes                                                        |
| ------------- | ------- | ------------------------------------------------------------ |
| `id`          | Text PK | uuid                                                         |
| `user_id`     | Text    | owner                                                        |
| `name`        | Text    | display name                                                 |
| `slug`        | Text    | globally unique (DB unique constraint), `^[a-z0-9-]{3,60}$`, no leading/trailing hyphen; editable (old link stops working) |
| `public`      | Boolean | `true` = served without login                                |
| `files`       | JSON    | manifest: `[{"name", "size", "content_type"}]`               |
| `entry_file`  | Text    | which HTML file opens at `/sites/{slug}`                     |
| `created_at`  | BigInteger | ms epoch                                                  |
| `updated_at`  | BigInteger | ms epoch                                                  |

### Access model

Reuses the fork's `access_grant` table with `resource_type='site'`, combined with
`site.public`:

| level                | representation                                              |
| -------------------- | ----------------------------------------------------------- |
| Public (no login)    | `site.public = true` (grants irrelevant for serving)        |
| Everyone in Osool    | grant `user:*` permission `read`                            |
| Specific people      | grants for listed `user`/`group` principals, permission `read` |
| Private (owner only) | no grants                                                   |

Owner and admins always have full access. Grants are written with the existing
`AccessGrants.set_access_grants` helper; checks use the existing grant helpers.

## Storage

- Bytes on disk at `DATA_DIR/sites/<site_id>/<filename>`.
- Flat: filenames must match `^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$` (no path separators,
  no leading dot, ASCII-safe). Anything else is rejected with a 400. Duplicate names in
  one upload are rejected.
- Limits (module constants): max 30 files per site, 10 MB per file, 30 MB per site total.
- Create/update: write files, then update row (manifest + entry_file) in one request.
  Update replaces the folder contents entirely (a site is uploaded as a unit).
- Delete: remove row, remove grants, remove folder.
- At least one `.html` file required; if exactly one, it becomes `entry_file`
  automatically, otherwise the client must specify which (default suggestion:
  `index.html` when present).

## Backend API — `backend/open_webui/routers/sites.py`

Mounted at `/api/v1/sites`. All management endpoints require a verified user with
`features.site_publisher` permission (or admin).

| endpoint                        | behavior                                                      |
| ------------------------------- | ------------------------------------------------------------- |
| `GET /`                         | list my sites; admin with `?all=true` lists everyone's        |
| `POST /`                        | create — multipart form: `files[]`, `name`, `slug`, `entry_file?`, `public`, `grants` (JSON) |
| `GET /{id}`                     | detail (owner or admin)                                       |
| `POST /{id}/update`             | replace files and/or update `name`/`slug`/`entry_file` (owner or admin) |
| `POST /{id}/access`             | update `public` flag + grants (owner or admin)                |
| `DELETE /{id}`                  | delete site (owner or admin)                                  |

Validation errors return 400 with a clear detail message (slug taken, slug invalid, file
too large, too many files, no HTML file, bad entry file, bad filename).

## Serving route

Registered on the main FastAPI app **before** the SPA catch-all mount:

- `GET /sites/{slug}` → serves `entry_file`
- `GET /sites/{slug}/{filename}` → serves that asset

Resolution and rules:

1. Look up site by slug; unknown slug → 404.
2. Access check:
   - `public` → serve without auth.
   - Otherwise resolve the requester from the existing token cookie / bearer header.
     - No valid session → 302 redirect to `/auth?redirect=<original path>` for the entry
       route; 401 for asset paths (assets are fetched by the page, not navigated to).
     - Valid session → allow if owner, admin, or a `read` grant matches (`user:*`,
       their user id, or one of their groups). Otherwise **404** — existence is not
       leaked to unauthorized users.
3. Path safety: requested filename must exist in the manifest, and the resolved on-disk
   path must stay inside the site's folder (defense in depth against traversal).
4. Response headers on **every** served file:
   - `Content-Security-Policy: sandbox allow-scripts`
   - `X-Content-Type-Options: nosniff`
   - correct `Content-Type` from the manifest
   The CSP applies to all responses (not only HTML) because SVG can also carry scripts.
5. No caching subtleties in v1: `Cache-Control: no-cache` so replaced files show
   immediately.

Dev-mode caveat: links only work on the backend origin (the Vite dev server does not
proxy `/sites/*`). Production is single-origin, so links work as-is.

## Frontend

- **Sidebar:** "Sites" item gated by a `canSeeSites` predicate — user has
  `features.site_publisher` permission or is admin (same pattern as
  `canSeePolicyReview`).
- **Route:** manager page at `/sites` (SvelteKit route). No collision with published
  links: the backend only claims `/sites/{slug}` (slug is non-empty), so the bare
  `/sites` path falls through to the SPA.
- **Manager page:** list of my sites — name, full link with copy button, visibility
  badge (Public / Everyone / Specific / Private), file count, updated date. Admin sees
  all sites (with owner shown).
- **Create/Edit dialog:**
  - name; slug auto-generated from name, editable, validated live;
  - multi-file picker (drag-and-drop or browse), file list with sizes, remove buttons;
  - entry-file auto-detected (single HTML) or selectable;
  - access section: four-level picker; "Specific people" reveals a user/group selector;
  - clear error surfacing for validation failures (slug taken, limits).
- **Delete:** confirm dialog.
- **Styling:** core-app styling (Osool look). NOT WorkOS shadcn — that design system is
  scoped to `.workos-root`.
- **i18n:** en-US + ar strings for all new UI.
- **Admin panel:** "Site Publisher" toggle added to the group permissions UI alongside
  the existing Policy Review toggles.

## Testing

Backend (pytest, self-contained like `test/policy_review`):

- DAO/table: create, slug uniqueness, update, delete.
- Router: permission gate (no flag → 403, admin bypass), create/update/delete flows,
  validation matrix (slug rules, file limits, filename sanitization, entry-file rules).
- Serving: full access matrix — public/no-login, `user:*` grant with and without login,
  specific user grant, group grant, private, owner, admin; 404 for unauthorized and
  unknown slugs; redirect for anonymous on non-public entry; traversal attempts rejected;
  CSP + nosniff headers present on all served responses.

Frontend: `npm run check` + build pass. Browser smoke performed by the user with a
provided checklist (publish multi-file site, links resolve, access levels behave,
sandbox blocks localStorage access from a published page).

## Out of scope (YAGNI)

- Nested folders / zip upload.
- Versioning or rollback of site contents.
- Per-file access control.
- View counters or analytics.
- Custom domains or subdomain serving.
- Editing file contents in-app (replace-only).
