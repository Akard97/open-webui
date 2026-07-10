# AI Avatar Generation — Design

**Date:** 2026-07-11
**Status:** Approved (brainstorm complete)
**Owner:** Ahmad Alsawarieh

## Summary

Add a third avatar option to the Account tab (alongside image upload and initials): the user
uploads a reference photo and gets back an AI-generated, deliberately stylized professional
avatar that resembles them without being photorealistic. Generation runs through OpenAI
`gpt-image-2` behind a new self-contained backend router, with a single org-wide locked style,
a per-user daily quota, and an admin kill switch.

Direction history: dicebear styles (both playful and corporate sets) and five in-house
generative SVG concepts were mocked and rejected; the user explicitly chose AI generation
from a reference photo with a professional corporate look.

## Goals

- One-click professional avatar from a reference photo, consistent look across the org.
- No photorealism — clearly illustrated/stylized output.
- Bounded cost (daily per-user cap, medium quality) and admin control (default OFF).
- Reference photos never persisted server-side.

## Non-goals

- Style presets or user-supplied style prompts (single locked style only).
- Onboarding/signup integration (Account tab only).
- Local/offline generation (ComfyUI etc.) — deployment VM has no GPU.
- Storing generation history or galleries.

## UX flow

1. `UserProfileImage.svelte` (Account tab) gains a fourth hover action, **AI Avatar**,
   next to Remove / Initials / Gravatar. Hidden entirely when the feature flag is off.
   Because `UserProfileImage` is shared with the admin Edit User modal, the action is
   additionally gated by a `showAIAvatar` prop that only `Account.svelte` sets — the
   feature is deliberately absent from the admin surface.
2. Clicking opens a new dialog (`AIAvatarDialog.svelte` under
   `src/lib/components/chat/Settings/Account/`):
   - Photo source: upload (drag/drop or click), or "use current photo" when
     `profileImageUrl` holds a real image (not the initials data URL / default `user.png`).
   - Static privacy note: "Your photo is sent to OpenAI to create the avatar; it isn't stored."
   - **Generate** button → progress state (~10–20 s) → large circular preview.
   - Actions after generation: **Use avatar** / **Regenerate**. Remaining daily quota shown
     ("7 generations left today").
3. **Use avatar** writes the result into `profileImageUrl` (bound up to `Account.svelte`);
   the user persists it with the existing Save flow (`updateUserProfile`). No new
   persistence path for the avatar itself.

## Backend

New router `backend/open_webui/routers/avatar.py`, registered in `main.py` as
`app.include_router(avatar.router, prefix='/api/v1/avatar', tags=['avatar'])` —
same self-contained pattern as `policy_review.py`.

### `POST /api/v1/avatar/generate`

- Auth: any logged-in user (`get_verified_user`).
- Body: multipart file upload (`photo`), image types png/jpeg/webp, max 10 MB.
- Server downsizes the photo so its longest edge ≤ 1024 px before the API call
  (caps input-token cost), in memory only — never written to disk or DB.
- Calls OpenAI Images Edit (`client.images.edit`) with:
  - `model="gpt-image-2"`
  - `image=<downsized photo>`
  - `prompt=<locked style prompt>` (config-overridable, see below)
  - `size="1024x1024"`, `quality="medium"`, `output_format="webp"`
- Response: `{ "image": "data:image/webp;base64,...", "remaining": <int> }`.
- Cost reference (docs, 2026-07): 1024×1024 low $0.006 / high ~$0.211 per image
  plus input tokens; medium ≈ a few cents per generation.

### `GET /api/v1/avatar/quota`

- Returns `{ "remaining": <int>, "limit": <int> }` so the dialog can show quota
  before the first generation.

### Quota

- New table `avatar_generation` (`user_id`, `date` (UTC day), `count`) with an Alembic
  migration, following the fork's existing migration pattern. Restart-proof and
  multi-worker-safe.
- Increment on successful generation only (failed OpenAI calls don't consume quota).
- Exceeded → HTTP 429 with a message including when the quota resets (midnight UTC).

### Config (env, PersistentConfig where it makes sense)

| Key | Default | Purpose |
| --- | --- | --- |
| `AVATAR_GENERATION_ENABLED` | `false` | Kill switch; also drives the frontend flag. |
| `AVATAR_OPENAI_API_KEY` | empty → falls back to `IMAGES_OPENAI_API_KEY` (config.py:3935, itself falling back to `OPENAI_API_KEY`) | Key used for generation. |
| `AVATAR_DAILY_LIMIT` | `10` | Per-user daily generation cap. |
| `AVATAR_STYLE_PROMPT` | built-in prompt below | Tune style without redeploy. |

Feature exposure: add `enable_avatar_generation` to the `features` dict returned by
`/api/config` (in `main.py` `get_app_config`), so the frontend reads
`$config?.features?.enable_avatar_generation`.

### Locked style prompt (default, tuned during implementation testing)

> Professional corporate avatar portrait of this person: clean modern flat vector
> illustration, simplified stylized features that resemble but do not exactly replicate
> them, head-and-shoulders composition, confident friendly expression, business attire,
> plain soft muted-teal background, subtle teal accents. No text, no logos,
> no photorealism.

## Error handling

- Feature off → frontend never shows the action; direct API call returns 403.
- No API key resolvable → 400 with actionable admin-facing message.
- Quota exceeded → 429 + reset time; dialog shows message and disables Generate.
- OpenAI failure or content refusal (e.g. moderation) → 502/400 passthrough with a
  user-readable toast; quota not consumed.
- Oversized/wrong-type upload → 400 before any API call.

## Frontend result handling

- The returned 1024×1024 webp data URL is resized client-side to ≤ 512 px (reusing the
  existing canvas resize utilities in `src/lib/utils`) before being placed in
  `profileImageUrl`, keeping the stored `profile_image_url` payload small.

## Testing

- Backend pytest (`backend/open_webui/test/avatar/`): feature flag off → 403;
  quota enforcement incl. 429 and reset; happy path with mocked OpenAI client;
  upload validation (type/size); failed generation does not consume quota.
- Frontend vitest: dialog state machine (idle → generating → preview → applied),
  quota display, feature-flag gating of the action.
- Manual browser smoke with a real API key at the end (prompt tuning happens here).

## Security & privacy

- Reference photo processed in memory only by application code; not logged, not persisted.
  (Framework caveat: Starlette's multipart parser may spool uploads larger than ~1 MB to a
  temporary file before router code runs — an OS-managed temp file deleted at request end,
  outside this feature's control.)
- Org API key stays server-side; the browser never talks to OpenAI.
- Photos leave the server to OpenAI's API (not used for training by default per
  OpenAI API terms) — org accepts this by enabling the flag (default OFF).
- Endpoint requires authentication; quota bounds abuse of the org key.
