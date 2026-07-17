<script lang="ts">
	import { getContext, onDestroy, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		getUserValvesById,
		getUserValvesSpecById,
		updateUserValvesById
	} from '$lib/apis/functions';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';

	import {
		EFFORT_LEVELS,
		type EffortLevel,
		functionIdFromModelId,
		indexToLevel,
		levelIndex,
		mergeEffort,
		normalizeEffort,
		specHasEffort
	} from './EffortMenu/effort';

	const i18n = getContext('i18n');

	export let modelId: string | null = null;

	let show = false;
	let available = false;
	let functionId: string | null = null;
	let level: EffortLevel = 'default';
	let confirmedLevel: EffortLevel = 'default';
	let valves: Record<string, unknown> = {};

	let trackEl: HTMLDivElement | null = null;
	let canvasEl: HTMLCanvasElement | null = null;

	let writeTimer: ReturnType<typeof setTimeout> | null = null;
	let initSeq = 0;

	let dragCleanup: (() => void) | null = null;

	// session cache: function id -> whether its user-valves spec exposes EFFORT
	const specCache: Record<string, boolean> = {};

	const THUMB_POSITIONS = [8, 50, 92];

	$: void init(modelId);

	const init = async (id: string | null) => {
		const seq = ++initSeq;
		show = false;
		available = false;

		if (!id) {
			return;
		}
		const fnId = functionIdFromModelId(id);

		if (!(fnId in specCache)) {
			try {
				const spec = await getUserValvesSpecById(localStorage.token, fnId);
				specCache[fnId] = specHasEffort(spec);
			} catch (e) {
				console.warn('EffortMenu: valves spec fetch failed', e);
				specCache[fnId] = false;
			}
		}
		if (seq !== initSeq || !specCache[fnId]) {
			return;
		}

		let userValves: unknown = {};
		try {
			userValves = await getUserValvesById(localStorage.token, fnId);
		} catch (e) {
			console.warn('EffortMenu: user valves fetch failed', e);
		}
		if (seq !== initSeq) {
			return;
		}

		functionId = fnId;
		valves =
			userValves && typeof userValves === 'object' && !Array.isArray(userValves)
				? (userValves as Record<string, unknown>)
				: {};
		level = normalizeEffort(valves.EFFORT);
		confirmedLevel = level;
		available = true;
	};

	const levelLabel = (l: EffortLevel) =>
		l === 'default' ? $i18n.t('Default') : l === 'xhigh' ? $i18n.t('X-High') : $i18n.t('Max');

	const accentColor = (l: EffortLevel, dark: boolean) =>
		l === 'max' ? (dark ? '#f0c274' : '#e0a13f') : dark ? '#6fc4d4' : '#3d94a8';

	const hexA = (hex: string, alpha: number) => {
		const n = parseInt(hex.slice(1), 16);
		return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
	};

	const drawDots = () => {
		if (!trackEl || !canvasEl) {
			return;
		}
		const w = trackEl.clientWidth;
		const h = trackEl.clientHeight;
		if (w === 0 || h === 0) {
			return;
		}
		const dark = document.documentElement.classList.contains('dark');
		canvasEl.width = w * 2;
		canvasEl.height = h * 2;
		const ctx = canvasEl.getContext('2d');
		if (!ctx) {
			return;
		}
		ctx.scale(2, 2);
		ctx.clearRect(0, 0, w, h);
		const accent = accentColor(level, dark);
		const cols = Math.floor(w / 7);
		const frac = levelIndex(level) / (EFFORT_LEVELS.length - 1);
		for (let c = 0; c < cols; c++) {
			const x = 6 + c * 7;
			const t = cols > 1 ? c / (cols - 1) : 0;
			for (let r = 0; r < 3; r++) {
				const y = h / 2 + (r - 1) * 7;
				const active = t <= frac + 0.001;
				const alpha = active ? (dark ? 0.12 : 0.18) + t * 0.85 : dark ? 0.07 : 0.1;
				const radius = active ? 1.1 + t * 1.3 : 1.1;
				ctx.beginPath();
				ctx.arc(x, y, radius, 0, Math.PI * 2);
				ctx.fillStyle = active
					? hexA(accent, Math.min(1, alpha))
					: dark
						? 'rgba(255,255,255,0.10)'
						: 'rgba(0,0,0,0.10)';
				ctx.fill();
			}
		}
	};

	const scheduleDraw = async () => {
		await tick();
		requestAnimationFrame(drawDots);
	};

	$: if (show) {
		void scheduleDraw();
	}

	const commitWrite = async () => {
		writeTimer = null;
		if (!functionId || level === confirmedLevel) {
			return;
		}
		const target = level;
		try {
			let base: unknown = valves;
			try {
				const fresh = await getUserValvesById(localStorage.token, functionId);
				if (fresh && typeof fresh === 'object' && !Array.isArray(fresh)) {
					base = fresh;
				}
			} catch (e) {
				console.warn('EffortMenu: refresh before write failed, using snapshot', e);
			}
			const updated = mergeEffort(base, target);
			const res = await updateUserValvesById(localStorage.token, functionId, updated);
			if (!res) {
				throw new Error('valve update failed');
			}
			valves = updated;
			confirmedLevel = target;
		} catch (e) {
			console.error('EffortMenu: valve update failed', e);
			toast.error($i18n.t('Failed to update effort'));
			level = confirmedLevel;
			void scheduleDraw();
		}
	};

	const setLevel = (next: EffortLevel) => {
		if (next === level) {
			return;
		}
		level = next;
		void scheduleDraw();
		if (writeTimer) {
			clearTimeout(writeTimer);
		}
		writeTimer = setTimeout(() => void commitWrite(), 400);
	};

	const setFromClientX = (clientX: number) => {
		if (!trackEl) {
			return;
		}
		const rect = trackEl.getBoundingClientRect();
		if (rect.width === 0) {
			return;
		}
		const t = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
		setLevel(indexToLevel(t * (EFFORT_LEVELS.length - 1)));
	};

	const onTrackPointerDown = (e: PointerEvent) => {
		if (dragCleanup) {
			dragCleanup();
		}
		setFromClientX(e.clientX);
		const move = (ev: PointerEvent) => setFromClientX(ev.clientX);
		const end = () => dragCleanup?.();
		dragCleanup = () => {
			window.removeEventListener('pointermove', move);
			window.removeEventListener('pointerup', end);
			window.removeEventListener('pointercancel', end);
			dragCleanup = null;
		};
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', end);
		window.addEventListener('pointercancel', end);
	};

	const onTrackKeydown = (e: KeyboardEvent) => {
		const idx = levelIndex(level);
		if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
			e.preventDefault();
			setLevel(indexToLevel(idx + 1));
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
			e.preventDefault();
			setLevel(indexToLevel(idx - 1));
		} else if (e.key === 'Home') {
			e.preventDefault();
			setLevel('default');
		} else if (e.key === 'End') {
			e.preventDefault();
			setLevel('max');
		}
	};

	onDestroy(() => {
		dragCleanup?.();
		if (writeTimer) {
			clearTimeout(writeTimer);
			void commitWrite();
		}
	});
</script>

{#if available}
	<Dropdown bind:show side="top" align="start" sideOffset={10}>
		<Tooltip content={$i18n.t('Effort')} placement="top">
			<button
				type="button"
				id="effort-menu-button"
				aria-label={$i18n.t('Effort')}
				class="flex items-center gap-1.5 h-[30px] px-2.5 rounded-full text-xs font-semibold border transition-colors focus:outline-hidden {level ===
				'default'
					? 'border-transparent text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
					: level === 'xhigh'
						? 'text-[#17707f] dark:text-[#6fc4d4] bg-[#3d94a8]/10 dark:bg-[#3d94a8]/15 border-[#3d94a8]/30'
						: 'text-[#a06716] dark:text-[#f0c274] bg-[#e0a13f]/15 dark:bg-[#e0a13f]/10 border-[#e0a13f]/30'}"
			>
				<Bolt className="size-3.5" />
				<span>{level === 'default' ? $i18n.t('Effort') : levelLabel(level)}</span>
			</button>
		</Tooltip>

		<div
			slot="content"
			dir="ltr"
			class="w-[250px] rounded-2xl px-4 pt-3.5 pb-4 bg-white dark:bg-gray-850 border border-gray-100 dark:border-gray-800 shadow-lg"
		>
			<div class="flex items-center gap-1.5 mb-3">
				<span class="text-[13px] font-semibold text-gray-700 dark:text-gray-200"
					>{$i18n.t('Effort')}</span
				>
				<span
					class="text-[13px] font-bold {level === 'max'
						? 'text-[#a06716] dark:text-[#f0c274]'
						: level === 'xhigh'
							? 'text-[#17707f] dark:text-[#6fc4d4]'
							: 'text-gray-500 dark:text-gray-400'}">{levelLabel(level)}</span
				>
				<Tooltip
					content={$i18n.t('Higher effort means deeper reasoning, slower and costlier responses')}
					placement="top"
					className="ml-auto"
				>
					<span
						class="flex items-center justify-center size-4 rounded-full text-[10px] font-bold bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 cursor-default"
						>?</span
					>
				</Tooltip>
			</div>

			<div
				class="flex justify-between text-[11px] font-medium text-gray-400 dark:text-gray-500 mb-2"
			>
				<span>{$i18n.t('Faster')}</span>
				<span>{$i18n.t('Smarter')}</span>
			</div>

			<div
				bind:this={trackEl}
				role="slider"
				tabindex="0"
				aria-label={$i18n.t('Effort')}
				aria-valuemin={0}
				aria-valuemax={EFFORT_LEVELS.length - 1}
				aria-valuenow={levelIndex(level)}
				aria-valuetext={levelLabel(level)}
				class="relative h-[26px] rounded-full bg-gray-100 dark:bg-gray-900 cursor-pointer touch-none focus:outline-hidden focus-visible:ring-2 focus-visible:ring-gray-300 dark:focus-visible:ring-gray-700"
				on:pointerdown={onTrackPointerDown}
				on:keydown={onTrackKeydown}
			>
				<div class="absolute inset-0 rounded-full overflow-hidden">
					<canvas bind:this={canvasEl} class="w-full h-full block"></canvas>
				</div>
				<div
					class="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 size-[18px] rounded-full bg-white dark:bg-gray-100 shadow-[0_1px_4px_rgba(0,0,0,0.35)] transition-[left] duration-150 pointer-events-none"
					style="left: {THUMB_POSITIONS[levelIndex(level)]}%"
				></div>
			</div>

			<div class="flex justify-between mt-2 text-[10px] font-semibold uppercase tracking-wide">
				{#each EFFORT_LEVELS as l (l)}
					<button
						type="button"
						class="focus:outline-hidden {l === level
							? 'text-gray-700 dark:text-gray-100'
							: 'text-gray-400 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400'}"
						on:click={() => setLevel(l)}>{levelLabel(l)}</button
					>
				{/each}
			</div>
		</div>
	</Dropdown>
{/if}
