import { it } from 'vitest';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildActiveVersion, buildSeedReviews, POLICIES } from './seed';

// Resolve to <repo-root>/backend/open_webui/internal/policy_review/seed_data.json
// This file lives at src/lib/components/policy-review/lib/exportSeed.test.ts,
// so we go up 6 directories to reach the repo root.
const __filename = fileURLToPath(import.meta.url);
const repoRoot = join(dirname(__filename), '..', '..', '..', '..', '..');

it('export policy seed data to backend JSON', () => {
	const active = buildActiveVersion();
	const reviews = buildSeedReviews();
	const payload = {
		activeVersion: active,
		library: POLICIES,
		reviews
	};
	const out = join(repoRoot, 'backend/open_webui/internal/policy_review/seed_data.json');
	mkdirSync(dirname(out), { recursive: true });
	writeFileSync(out, JSON.stringify(payload, null, 2));
});
