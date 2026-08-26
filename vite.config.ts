import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

import { viteStaticCopy } from 'vite-plugin-static-copy';
import { readFileSync } from 'node:fs';
import type * as fsType from 'node:fs';
import { createRequire } from 'node:module';

// --- Windows / McAfee EPERM workaround ---
// McAfee on-access scanning briefly locks freshly-written files, so the atomic
// rename Vite performs after optimizing deps (deps_temp -> deps) fails with
// `EPERM: operation not permitted, rename`. On Windows the optimizer routes
// this through its own `safeRename`, which retries EPERM for only ~5s and only
// when the destination is missing — not long enough for McAfee, and it bails
// outright when the destination already exists.
//
// The lock is transient, so we patch the real node:fs singleton's async
// `rename` (the one safeRename calls) to retry EPERM/EBUSY/etc. for up to ~60s
// with exponential backoff, unconditionally. We grab the singleton via
// createRequire (not the esbuild-wrapped `import`) so the mutation is visible
// to Vite's bundled optimizer, which runs in this same process after the
// config is evaluated.
if (process.platform === 'win32') {
	const fs: typeof fsType = createRequire(import.meta.url)('node:fs');
	const RETRYABLE = new Set(['EPERM', 'EBUSY', 'EACCES', 'ENOTEMPTY', 'EEXIST']);
	const isRetryable = (code?: string | null) => !!code && RETRYABLE.has(code);
	const RETRY_BUDGET_MS = 60_000;

	const origRename = fs.rename;
	fs.rename = function renameWithRetry(
		from: fsType.PathLike,
		to: fsType.PathLike,
		cb: (err: NodeJS.ErrnoException | null) => void
	) {
		const deadline = Date.now() + RETRY_BUDGET_MS;
		let delay = 50;
		const attempt = () =>
			origRename(from, to, (err) => {
				if (err && isRetryable(err.code) && Date.now() < deadline) {
					console.warn(`[vite] rename ${err.code}, retrying in ${delay}ms (AV lock)`);
					setTimeout(attempt, delay);
					delay = Math.min(delay * 2, 1000);
					return;
				}
				cb(err);
			});
		attempt();
	} as typeof fs.rename;

	// Belt and suspenders: the non-Windows commit path (and other callers) use
	// renameSync; give it the same retry so this survives Vite internals changes.
	const origRenameSync = fs.renameSync;
	const sleep = (ms: number) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
	fs.renameSync = function renameSyncWithRetry(from: fsType.PathLike, to: fsType.PathLike) {
		const deadline = Date.now() + RETRY_BUDGET_MS;
		let delay = 50;
		for (;;) {
			try {
				return origRenameSync(from, to);
			} catch (err) {
				const code = (err as NodeJS.ErrnoException).code;
				if (!isRetryable(code) || Date.now() > deadline) throw err;
				console.warn(`[vite] renameSync ${code}, retrying in ${delay}ms (AV lock)`);
				sleep(delay);
				delay = Math.min(delay * 2, 1000);
			}
		}
	};
}

// Pre-bundle the full dependency set in one pass up front. This avoids Vite's
// mid-session re-optimization (lazy discovery), which is the worst trigger for
// the EPERM rename race because the running server and browser still hold
// handles to the old deps folder.
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));
const doNotOptimize = new Set([
	'@sveltejs/adapter-node',
	'vite-plugin-static-copy',
	'pyodide',
	'@huggingface/transformers',
	'@pyscript/core',
	'@mediapipe/tasks-vision',
	'kokoro-js',
	'sql.js',
	'bits-ui',
	'@xyflow/svelte',
	'@sveltejs/svelte-virtual-list',
	'@tiptap/pm',
	'y-protocols'
]);
const optimizeDepsInclude = [
	...Object.keys(pkg.dependencies || {}).filter((dep) => !doNotOptimize.has(dep)),
	'dayjs/plugin/relativeTime',
	'dayjs/plugin/isToday',
	'dayjs/plugin/isYesterday',
	'dayjs/plugin/localizedFormat'
];

export default defineConfig({
	plugins: [
		sveltekit(),
		viteStaticCopy({
			targets: [
				{
					src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

					dest: 'wasm'
				}
			]
		})
	],
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	optimizeDeps: {
		include: optimizeDepsInclude
	},
	server: {
		proxy: {
			// Dev-only: published Site Publisher links live on the backend, which
			// the Vite origin doesn't serve. Proxy /sites/<slug> to the backend —
			// but NOT the bare /sites path, which is the SvelteKit manager page.
			'^/sites/.+': {
				target: 'http://localhost:8080',
				changeOrigin: true
			}
		}
	},
	build: {
		sourcemap: true
	},
	worker: {
		format: 'es'
	},
	esbuild: {
		pure: process.env.ENV === 'dev' ? [] : ['console.log', 'console.debug', 'console.error']
	}
});
