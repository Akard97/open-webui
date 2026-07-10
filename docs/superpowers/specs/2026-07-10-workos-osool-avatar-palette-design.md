# WorkOS Osool Avatar Palette Design

## Goal

Replace the unrelated avatar colors in WorkOS with one deterministic Osool identity palette led by the primary brand ink `#00313F`. Apply the palette to every initials-based user avatar while keeping different users visually distinct.

## Palette

The avatar palette reuses the categorical Osool colors already established for dashboard widgets:

1. `#00313F` — primary brand ink
2. `#026C80` — deep teal
3. `#00A5BA` — Pantone 3125 teal
4. `#769A4A` — Pantone 576 olive
5. `#DFA244` — sand
6. `#C96B5D` — terracotta
7. `#54C2D1` — light teal
8. `#A4C979` — light olive

The existing stable string hash continues to assign a palette entry from a user ID or normalized actor name. A user's avatar therefore keeps the same color across WorkOS surfaces and renders.

Initials use white or Osool ink text when either meets WCAG AA contrast. A black fallback is allowed for a mid-tone background where neither brand foreground reaches the threshold. The candidate with the strongest contrast is selected, and every palette pair must meet WCAG AA's 4.5:1 requirement for normal text.

## Architecture

`src/lib/components/workos/lib/avatar.ts` remains the single source of avatar identity styling. It will expose the new avatar palette and a helper that returns the assigned background and foreground together.

The label palette remains a separate export because `store.ts` uses it when creating labels. Avatar changes must not recolor labels, task statuses, priorities, health indicators, or calendar states.

All initials-based user renderers will consume the shared helper:

- task, list, detail, overview, hover-card, and team-switcher avatars through `AssigneeAvatars.svelte`;
- activity and mention avatars in `MyWorkView.svelte`;
- the board-assignee stack in `Topbar.svelte`;
- member avatars in `TeamSettingsDialog.svelte` and `WorkspaceSettingsDialog.svelte`;
- the assignee marker in `TimelineBar.svelte`.

Existing shadcn-svelte `Avatar` and `AvatarFallback` composition stays in place where already used. This change centralizes identity colors without replacing unrelated layout or interaction markup.

## Behavior and Edge Cases

- The same non-empty ID or name always returns the same background and foreground pair.
- Empty and unknown values still receive a deterministic, accessible palette entry.
- Hash collisions are acceptable; the palette distinguishes users visually but does not serve as a unique identifier.
- Dark mode uses the same identity color so a user does not change identity when the theme changes. Existing rings and borders continue separating overlapping avatars from the surrounding surface.

## Verification

Unit tests in `avatar.test.ts` will be written before implementation and will verify:

- the palette is led by `#00313F` and contains only the approved Osool colors;
- assignments are deterministic and distributed across multiple entries;
- avatar colors come from the avatar palette rather than the label palette;
- every background/foreground pair meets a 4.5:1 contrast ratio.

After the focused test passes, run the relevant frontend test suite and Svelte type checking. Finally, inspect WorkOS in the browser to confirm the palette appears consistently on the board, timeline, top bar, My Work, and access dialogs.

## Out of Scope

- Changing profile photographs or uploaded avatar images.
- Recoloring task labels, statuses, priorities, health states, or non-user decorative circles.
- Changing avatar sizes, spacing, typography, or membership behavior.
