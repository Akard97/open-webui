<script lang="ts">
	// Scanning stage — animated "AI is reviewing" view with two modes:
	//   sequential — one item at a time, fast accelerator
	//   bulk       — theme-by-theme, items finish in parallel
	// Port of scanning.jsx from the PRP-2 design handoff.

	import { onDestroy, untrack } from 'svelte';
	import { get } from 'svelte/store';
	import Icon from '../ui/Icon.svelte';
	import type { ItemVerdict } from '../lib/types';
	import { stage, view, activeVersion, activeReview } from '../lib/store';

	const version = get(activeVersion);
	const review = get(activeReview);
	const meta = review?.policyMeta;

	type FlatItem = {
		key: string;
		prp: string;
		n: number;
		text: string;
		result: ItemVerdict;
		theme: string;
	};

	type ThemeGroup = { id: string; name: string; items: FlatItem[] };

	const items: FlatItem[] = (() => {
		const all: FlatItem[] = [];
		(version?.sections ?? []).forEach((sec) => {
			sec.items.forEach((it) => {
				const key = `${sec.id}-${it.n}`;
				all.push({
					key,
					prp: sec.id,
					n: it.n,
					text: it.text,
					result: review?.results[key]?.result ?? 'pending',
					theme: sec.theme
				});
			});
		});
		return all;
	})();

	const themeGroups: ThemeGroup[] = (() => {
		const map = new Map<string, FlatItem[]>();
		items.forEach((it) => {
			if (!map.has(it.theme)) map.set(it.theme, []);
			map.get(it.theme)!.push(it);
		});
		const themeMeta = Object.fromEntries((version?.themes ?? []).map((t) => [t.id, t]));
		return [...map.entries()].map(([id, list]) => ({
			id,
			name: themeMeta[id]?.name ?? id,
			items: list
		}));
	})();

	let mode = $state<'bulk' | 'sequential'>('bulk');
	let runKey = $state(0);
	let seqIdx = $state(0);
	let bulkThemeIdx = $state(0);
	let bulkStatus = $state<Record<string, 'running' | 'done'>>({});

	let timers: ReturnType<typeof setTimeout>[] = [];
	function clearTimers() {
		timers.forEach((t) => clearTimeout(t));
		timers = [];
	}
	onDestroy(clearTimers);

	function done() {
		stage.set('review');
		view.set('review');
	}

	// Reset whenever mode/runKey changes.
	$effect(() => {
		// dependency
		void mode;
		void runKey;
		clearTimers();
		seqIdx = 0;
		bulkThemeIdx = 0;
		bulkStatus = {};
	});

	// Sequential driver.
	$effect(() => {
		if (mode !== 'sequential') return;
		if (seqIdx >= items.length) {
			const t = setTimeout(done, 600);
			timers.push(t);
			return () => clearTimeout(t);
		}
		const dur = seqIdx < 3 ? 320 : seqIdx < 8 ? 180 : 110;
		const t = setTimeout(() => {
			seqIdx = seqIdx + 1;
		}, dur);
		timers.push(t);
		return () => clearTimeout(t);
	});

	// Bulk driver.
	$effect(() => {
		if (mode !== 'bulk') return;
		if (bulkThemeIdx >= themeGroups.length) {
			const t = setTimeout(done, 700);
			timers.push(t);
			return () => clearTimeout(t);
		}
		const theme = themeGroups[bulkThemeIdx];
		// Read the accumulated statuses via untrack(): this effect's real
		// dependencies are `mode` and `bulkThemeIdx`. Tracking the bulkStatus
		// read here would make the effect depend on state it also writes,
		// self-invalidating into effect_update_depth_exceeded.
		bulkStatus = {
			...untrack(() => bulkStatus),
			...Object.fromEntries(theme.items.map((it) => [it.key, 'running' as const]))
		};
		const finishes = theme.items.map((it, i) => ({
			it,
			at: 380 + ((i * 79) % 1100) + Math.random() * 220
		}));
		const localTimers: ReturnType<typeof setTimeout>[] = [];
		finishes.forEach(({ it, at }) => {
			const t = setTimeout(() => {
				bulkStatus = { ...bulkStatus, [it.key]: 'done' };
			}, at);
			timers.push(t);
			localTimers.push(t);
		});
		const themeDuration = Math.max(...finishes.map((f) => f.at)) + 500;
		const advance = setTimeout(() => {
			bulkThemeIdx = bulkThemeIdx + 1;
		}, themeDuration);
		timers.push(advance);
		localTimers.push(advance);
		return () => localTimers.forEach((t) => clearTimeout(t));
	});

	let doneCount = $derived(
		mode === 'sequential'
			? seqIdx
			: Object.values(bulkStatus).filter((s) => s === 'done').length
	);
	let pct = $derived(Math.min(100, Math.round((doneCount / items.length) * 100)));

	let currentTheme = $derived.by<ThemeGroup | null>(() => {
		if (mode === 'sequential') {
			const it = items[seqIdx];
			if (!it) return null;
			return themeGroups.find((t) => t.id === it.theme) ?? null;
		}
		return themeGroups[bulkThemeIdx] ?? null;
	});

	function bulkItemClass(it: FlatItem): string {
		const st = bulkStatus[it.key];
		if (st === 'running') return 'running';
		if (st === 'done') {
			if (it.result === 'compliant') return 'ok';
			if (it.result === 'non-compliant') return 'bad';
			return 'warn';
		}
		return 'wait';
	}

	function seqItemClass(it: FlatItem): string {
		const i = items.findIndex((x) => x.key === it.key);
		if (i < seqIdx) {
			if (it.result === 'compliant') return 'ok';
			if (it.result === 'non-compliant') return 'bad';
			return 'warn';
		}
		if (i === seqIdx) return 'running';
		return 'wait';
	}

	function bulkThemeClass(ti: number): string {
		if (ti === bulkThemeIdx) return 'active';
		if (ti < bulkThemeIdx) return 'done';
		return 'pending';
	}

	function seqThemeClass(tg: ThemeGroup): string {
		const tgDone = tg.items.filter((it) => items.findIndex((x) => x.key === it.key) < seqIdx).length;
		const hasActive = tg.items.some((it) => it.key === items[seqIdx]?.key);
		if (hasActive) return 'active';
		if (tgDone === tg.items.length) return 'done';
		if (tgDone === 0) return 'pending';
		return '';
	}

	function bulkThemeDoneCount(tg: ThemeGroup): number {
		return tg.items.filter((it) => bulkStatus[it.key] === 'done').length;
	}

	function seqThemeDoneCount(tg: ThemeGroup): number {
		return tg.items.filter((it) => items.findIndex((x) => x.key === it.key) < seqIdx).length;
	}
</script>

<div class="scan-wrap fade-in">
	<div class="scan-left">
		<div class="scan-doc">
			<div class="doc-icon"><Icon name="fileText" size={20} /></div>
			<div class="doc-name">{meta?.name}</div>
			<div class="doc-meta">{meta?.code} · {meta?.version}</div>
			<div class="scan-progress">
				<div class="label">
					<span>Reviewing</span>
					<span class="pct">{pct}%</span>
				</div>
				<div class="scan-bar"><div class="fill" style="width: {pct}%"></div></div>
				<div class="scan-counts"><b>{doneCount}</b> of {items.length} checks</div>
			</div>
		</div>

		<div class="scan-strategy">
			<div class="strat-label">Strategy</div>
			<div class="strat-segs">
				<button
					class="strat-seg"
					class:active={mode === 'sequential'}
					onclick={() => {
						mode = 'sequential';
						runKey = runKey + 1;
					}}
					type="button">Sequential</button
				>
				<button
					class="strat-seg"
					class:active={mode === 'bulk'}
					onclick={() => {
						mode = 'bulk';
						runKey = runKey + 1;
					}}
					type="button">Bulk by theme</button
				>
			</div>
		</div>

		<div style="margin-top:14px">
			<button class="btn btn-sm btn-ghost" onclick={done} type="button">
				Skip to results <Icon name="arrowR" size={11} />
			</button>
		</div>
	</div>

	<div class="scan-right">
		<div class="scan-stage">
			<div class="scan-stage-spinner"><div class="spinner lg"></div></div>
			<div class="scan-stage-text">
				<h2>Running PRP Master Checklist</h2>
				<p>
					{#if currentTheme}
						Reviewing <b>{currentTheme.name}</b>
					{:else}
						Finalising…
					{/if}
				</p>
			</div>
		</div>

		<div class="dot-board">
			{#each themeGroups as tg, ti (tg.id)}
				{@const cls = mode === 'bulk' ? bulkThemeClass(ti) : seqThemeClass(tg)}
				{@const doneN = mode === 'bulk' ? bulkThemeDoneCount(tg) : seqThemeDoneCount(tg)}
				<div class="dot-theme {cls}">
					<div class="dt-head">
						<span class="dt-id">{tg.id}</span>
						<span class="dt-name">{tg.name}</span>
						<span class="dt-count">{doneN}/{tg.items.length}</span>
					</div>
					<div class="dt-dots">
						{#each tg.items as it (it.key)}
							<span class="dot {mode === 'bulk' ? bulkItemClass(it) : seqItemClass(it)}"></span>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	</div>
</div>
