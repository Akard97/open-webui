import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

import { viteStaticCopy } from 'vite-plugin-static-copy';
import { readFileSync } from 'node:fs';

// TEMP TEST HARNESS (remove once McAfee exclusion is verified): forces Vite to
// optimize the full dependency set in one pass, which deterministically EPERMs
// while McAfee on-access scanning locks node_modules/.vite/deps. Used as a fast
// pass/fail check for the exclusion via: rm -rf node_modules/.vite && npx vite optimize --force
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
