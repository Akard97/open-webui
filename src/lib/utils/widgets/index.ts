// Inline chat widgets: types, validation, palette and vega-lite translation.
// The model emits ```widget fences with a compact JSON payload (or ```widget-html
// with a raw HTML document); WidgetBlock.svelte parses/validates and dispatches.

import { formatNumber } from '$lib/utils';

export const WIDGET_HEIGHT_MESSAGE = '__osoolWidgetHeight';

export type WidgetColor = 'emerald' | 'blue' | 'violet' | 'amber' | 'rose' | 'gray';

export interface ChartWidget {
	type: 'chart';
	chart: 'bar' | 'line' | 'area' | 'pie' | 'donut' | 'scatter';
	title?: string;
	subtitle?: string;
	x: (string | number)[];
	series: { name?: string; values: number[] }[];
	stacked?: boolean;
	format?: 'number' | 'percent' | 'currency';
	currency?: string;
}

export interface KpiWidget {
	type: 'kpi';
	items: {
		label: string;
		value: string | number;
		delta?: string;
		trend?: 'up' | 'down' | 'flat';
		color?: WidgetColor;
	}[];
}

export interface CardsWidget {
	type: 'cards';
	columns?: number;
	items: {
		title: string;
		subtitle?: string;
		body?: string;
		badge?: string;
		color?: WidgetColor;
		action?: { label: string; message: string };
	}[];
}

export interface TableWidget {
	type: 'table';
	title?: string;
	columns: { key: string; label: string; badge?: boolean; align?: 'left' | 'center' | 'right' }[];
	rows: Record<string, string | number | boolean | null>[];
}

export interface TasksWidget {
	type: 'tasks';
	title?: string;
	layout?: 'list' | 'cards';
	items: {
		key: string;
		title: string;
		status?: string;
		priority?: string;
		due?: string;
		progress?: number;
		assignees?: string[];
		note?: string;
		id?: string;
		ws?: string;
	}[];
}

export interface TimelineWidget {
	type: 'timeline';
	items: {
		title: string;
		date?: string;
		description?: string;
		status?: 'done' | 'active' | 'pending';
	}[];
}

export interface ButtonsWidget {
	type: 'buttons';
	label?: string;
	items: { label: string; message: string; style?: 'primary' | 'secondary' }[];
}

export interface FormWidget {
	type: 'form';
	title?: string;
	submit?: string;
	template?: string;
	fields: {
		name: string;
		label: string;
		type?: 'text' | 'number' | 'select' | 'textarea' | 'date' | 'checkbox';
		options?: (string | number)[];
		placeholder?: string;
		required?: boolean;
	}[];
}

export type Widget =
	| ChartWidget
	| KpiWidget
	| CardsWidget
	| TableWidget
	| TasksWidget
	| TimelineWidget
	| ButtonsWidget
	| FormWidget;

export type WidgetValidation = { ok: true; widget: Widget } | { ok: false; error: string };

const CHART_KINDS = ['bar', 'line', 'area', 'pie', 'donut', 'scatter'];
const COLORS: WidgetColor[] = ['emerald', 'blue', 'violet', 'amber', 'rose', 'gray'];

const isNonEmptyArray = (value: unknown): value is unknown[] =>
	Array.isArray(value) && value.length > 0;

const asColor = (value: unknown): WidgetColor | undefined =>
	COLORS.includes(value as WidgetColor) ? (value as WidgetColor) : undefined;

// Tolerant validation: unknown extra keys are ignored, only structurally
// required keys are enforced so slightly-off model output still renders.
export const validateWidget = (payload: unknown): WidgetValidation => {
	if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
		return { ok: false, error: 'Widget payload must be a JSON object' };
	}

	const obj = payload as Record<string, unknown>;
	const type = obj.type;

	switch (type) {
		case 'chart': {
			if (!isNonEmptyArray(obj.series)) {
				return { ok: false, error: `"chart" widget requires a non-empty "series" array` };
			}
			const series = (obj.series as unknown[])
				.map((s, idx) => {
					const item = (s ?? {}) as Record<string, unknown>;
					const values = Array.isArray(item.values)
						? item.values.map((v) => Number(v)).filter((v) => Number.isFinite(v))
						: [];
					return { name: item.name != null ? String(item.name) : `Series ${idx + 1}`, values };
				})
				.filter((s) => s.values.length > 0);
			if (series.length === 0) {
				return { ok: false, error: `"chart" widget series need numeric "values"` };
			}
			const x = Array.isArray(obj.x)
				? (obj.x as unknown[]).map((v) => (typeof v === 'number' ? v : String(v)))
				: series[0].values.map((_, idx) => idx + 1);
			return {
				ok: true,
				widget: {
					type: 'chart',
					chart: CHART_KINDS.includes(obj.chart as string)
						? (obj.chart as ChartWidget['chart'])
						: 'bar',
					title: obj.title != null ? String(obj.title) : undefined,
					subtitle: obj.subtitle != null ? String(obj.subtitle) : undefined,
					x,
					series,
					stacked: obj.stacked === true,
					format: ['number', 'percent', 'currency'].includes(obj.format as string)
						? (obj.format as ChartWidget['format'])
						: undefined,
					currency: obj.currency != null ? String(obj.currency) : undefined
				}
			};
		}
		case 'kpi': {
			if (!isNonEmptyArray(obj.items)) {
				return { ok: false, error: `"kpi" widget requires a non-empty "items" array` };
			}
			const items = (obj.items as unknown[])
				.map((entry) => {
					const item = (entry ?? {}) as Record<string, unknown>;
					if (item.label == null || item.value == null) return null;
					return {
						label: String(item.label),
						value: String(item.value),
						delta: item.delta != null ? String(item.delta) : undefined,
						trend: ['up', 'down', 'flat'].includes(item.trend as string)
							? (item.trend as 'up' | 'down' | 'flat')
							: undefined,
						color: asColor(item.color)
					};
				})
				.filter((item) => item !== null);
			if (items.length === 0) {
				return { ok: false, error: `"kpi" items need "label" and "value"` };
			}
			return { ok: true, widget: { type: 'kpi', items } };
		}
		case 'cards': {
			if (!isNonEmptyArray(obj.items)) {
				return { ok: false, error: `"cards" widget requires a non-empty "items" array` };
			}
			const items = (obj.items as unknown[])
				.map((entry) => {
					const item = (entry ?? {}) as Record<string, unknown>;
					if (item.title == null) return null;
					const action = (item.action ?? null) as Record<string, unknown> | null;
					return {
						title: String(item.title),
						subtitle: item.subtitle != null ? String(item.subtitle) : undefined,
						body: item.body != null ? String(item.body) : undefined,
						badge: item.badge != null ? String(item.badge) : undefined,
						color: asColor(item.color),
						action:
							action && action.label != null && action.message != null
								? { label: String(action.label), message: String(action.message) }
								: undefined
					};
				})
				.filter((item) => item !== null);
			if (items.length === 0) {
				return { ok: false, error: `"cards" items need a "title"` };
			}
			const columns = Number(obj.columns);
			return {
				ok: true,
				widget: {
					type: 'cards',
					columns: Number.isFinite(columns) ? Math.min(Math.max(Math.round(columns), 1), 3) : undefined,
					items
				}
			};
		}
		case 'table': {
			if (!isNonEmptyArray(obj.columns) || !Array.isArray(obj.rows)) {
				return { ok: false, error: `"table" widget requires "columns" and "rows" arrays` };
			}
			const columns = (obj.columns as unknown[])
				.map((entry) => {
					const col = (entry ?? {}) as Record<string, unknown>;
					if (col.key == null) return null;
					return {
						key: String(col.key),
						label: String(col.label ?? col.key),
						badge: col.badge === true,
						align: ['left', 'center', 'right'].includes(col.align as string)
							? (col.align as 'left' | 'center' | 'right')
							: undefined
					};
				})
				.filter((col) => col !== null);
			if (columns.length === 0) {
				return { ok: false, error: `"table" columns need a "key"` };
			}
			const rows = (obj.rows as unknown[]).map((row) =>
				typeof row === 'object' && row !== null && !Array.isArray(row)
					? (row as Record<string, string | number | boolean | null>)
					: {}
			);
			return {
				ok: true,
				widget: {
					type: 'table',
					title: obj.title != null ? String(obj.title) : undefined,
					columns,
					rows
				}
			};
		}
		case 'timeline': {
			if (!isNonEmptyArray(obj.items)) {
				return { ok: false, error: `"timeline" widget requires a non-empty "items" array` };
			}
			const items = (obj.items as unknown[])
				.map((entry) => {
					const item = (entry ?? {}) as Record<string, unknown>;
					if (item.title == null) return null;
					return {
						title: String(item.title),
						date: item.date != null ? String(item.date) : undefined,
						description: item.description != null ? String(item.description) : undefined,
						status: ['done', 'active', 'pending'].includes(item.status as string)
							? (item.status as 'done' | 'active' | 'pending')
							: undefined
					};
				})
				.filter((item) => item !== null);
			if (items.length === 0) {
				return { ok: false, error: `"timeline" items need a "title"` };
			}
			return { ok: true, widget: { type: 'timeline', items } };
		}
		case 'buttons': {
			if (!isNonEmptyArray(obj.items)) {
				return { ok: false, error: `"buttons" widget requires a non-empty "items" array` };
			}
			const items = (obj.items as unknown[])
				.map((entry) => {
					const item = (entry ?? {}) as Record<string, unknown>;
					if (item.label == null || item.message == null) return null;
					return {
						label: String(item.label),
						message: String(item.message),
						style: item.style === 'secondary' ? ('secondary' as const) : ('primary' as const)
					};
				})
				.filter((item) => item !== null);
			if (items.length === 0) {
				return { ok: false, error: `"buttons" items need "label" and "message"` };
			}
			return {
				ok: true,
				widget: {
					type: 'buttons',
					label: obj.label != null ? String(obj.label) : undefined,
					items
				}
			};
		}
		case 'form': {
			if (!isNonEmptyArray(obj.fields)) {
				return { ok: false, error: `"form" widget requires a non-empty "fields" array` };
			}
			const fields = (obj.fields as unknown[])
				.map((entry) => {
					const field = (entry ?? {}) as Record<string, unknown>;
					if (field.name == null) return null;
					return {
						name: String(field.name),
						label: String(field.label ?? field.name),
						type: ['text', 'number', 'select', 'textarea', 'date', 'checkbox'].includes(
							field.type as string
						)
							? (field.type as FormWidget['fields'][number]['type'])
							: ('text' as const),
						options: Array.isArray(field.options)
							? (field.options as unknown[]).map((option) => String(option))
							: undefined,
						placeholder: field.placeholder != null ? String(field.placeholder) : undefined,
						required: field.required === true
					};
				})
				.filter((field) => field !== null);
			if (fields.length === 0) {
				return { ok: false, error: `"form" fields need a "name"` };
			}
			return {
				ok: true,
				widget: {
					type: 'form',
					title: obj.title != null ? String(obj.title) : undefined,
					submit: obj.submit != null ? String(obj.submit) : undefined,
					template: obj.template != null ? String(obj.template) : undefined,
					fields
				}
			};
		}
		case 'tasks': {
			if (!isNonEmptyArray(obj.items)) {
				return { ok: false, error: `"tasks" widget requires a non-empty "items" array` };
			}
			const items = (obj.items as unknown[])
				.map((entry) => {
					const item = (entry ?? {}) as Record<string, unknown>;
					if (item.title == null) return null;
					const progress = item.progress != null ? Number(item.progress) : NaN;
					return {
						key: item.key != null ? String(item.key) : '',
						title: String(item.title),
						status: item.status != null ? String(item.status) : undefined,
						priority: item.priority != null ? String(item.priority) : undefined,
						due: item.due != null ? String(item.due) : undefined,
						progress: Number.isFinite(progress)
							? Math.min(Math.max(Math.round(progress), 0), 100)
							: undefined,
						assignees: Array.isArray(item.assignees)
							? (item.assignees as unknown[]).map((a) => String(a))
							: undefined,
						note: item.note != null ? String(item.note) : undefined,
						id: item.id != null ? String(item.id) : undefined,
						ws: item.ws != null ? String(item.ws) : undefined
					};
				})
				.filter((item) => item !== null);
			if (items.length === 0) {
				return { ok: false, error: `"tasks" items need a "title"` };
			}
			return {
				ok: true,
				widget: {
					type: 'tasks',
					title: obj.title != null ? String(obj.title) : undefined,
					layout: obj.layout === 'cards' ? 'cards' : 'list',
					items
				}
			};
		}
		default:
			return {
				ok: false,
				error: `Unknown widget type "${String(type)}" (expected chart, kpi, cards, table, tasks, timeline, buttons or form)`
			};
	}
};

// Osool brand categorical palettes (light/dark variants). Anchored on the
// brand ink #00313f with Pantone 3125/315/576-derived companions.
export const CHART_COLORS_LIGHT = [
	'#00a5ba', // teal (Pantone 3125)
	'#769a4a', // olive (Pantone 576)
	'#026c80', // deep teal (Pantone 315)
	'#dfa244', // sand
	'#c96b5d', // terracotta
	'#00313f', // ink (brand primary)
	'#54c2d1', // light teal
	'#a4c979' // light olive
];

export const CHART_COLORS_DARK = [
	'#2fc4d9',
	'#9bc46a',
	'#3fa1b5',
	'#eec06a',
	'#e08d7d',
	'#7fcfdd',
	'#c4dba0',
	'#6b8f9c'
];

// Named palette for kpi/cards/timeline accents, tinted to the Osool brand
// (keys stay generic — they are the model-facing vocabulary). Every class
// literal is spelled out so Tailwind's scanner picks them up.
export const PALETTE: Record<
	WidgetColor,
	{ tile: string; badge: string; dot: string; accent: string; text: string }
> = {
	emerald: {
		tile: 'bg-gradient-to-br from-[#769a4a] to-[#5a7c37]',
		badge: 'bg-[#769a4a]/15 text-[#5a7c37] dark:text-[#a4c979]',
		dot: 'bg-[#769a4a]',
		accent: 'from-[#769a4a] to-[#93b566]',
		text: 'text-[#5a7c37] dark:text-[#a4c979]'
	},
	blue: {
		tile: 'bg-gradient-to-br from-[#00a5ba] to-[#026c80]',
		badge: 'bg-[#00a5ba]/15 text-[#026c80] dark:text-[#4cc3d4]',
		dot: 'bg-[#00a5ba]',
		accent: 'from-[#00a5ba] to-[#33b9c9]',
		text: 'text-[#026c80] dark:text-[#4cc3d4]'
	},
	violet: {
		tile: 'bg-gradient-to-br from-[#026c80] to-[#00313f]',
		badge: 'bg-[#026c80]/15 text-[#00313f] dark:text-[#7fcfdd]',
		dot: 'bg-[#026c80]',
		accent: 'from-[#026c80] to-[#00a5ba]',
		text: 'text-[#00313f] dark:text-[#7fcfdd]'
	},
	amber: {
		tile: 'bg-gradient-to-br from-[#dfa244] to-[#c08427]',
		badge: 'bg-[#dfa244]/15 text-[#a8761f] dark:text-[#ecc27a]',
		dot: 'bg-[#dfa244]',
		accent: 'from-[#dfa244] to-[#ecc27a]',
		text: 'text-[#a8761f] dark:text-[#ecc27a]'
	},
	rose: {
		tile: 'bg-gradient-to-br from-[#c96b5d] to-[#a94f42]',
		badge: 'bg-[#c96b5d]/15 text-[#a94f42] dark:text-[#e39a8e]',
		dot: 'bg-[#c96b5d]',
		accent: 'from-[#c96b5d] to-[#dd8d80]',
		text: 'text-[#a94f42] dark:text-[#e39a8e]'
	},
	gray: {
		tile: 'bg-gradient-to-br from-[#44636e] to-[#2b4650]',
		badge: 'bg-[#44636e]/15 text-[#44636e] dark:text-gray-400',
		dot: 'bg-[#44636e]',
		accent: 'from-[#44636e] to-[#5f7f8a]',
		text: 'text-[#44636e] dark:text-gray-400'
	}
};

// Accent color assigned to items that don't declare one (kpi/cards cycle
// through it by index).
export const DEFAULT_COLOR_CYCLE: WidgetColor[] = [
	'violet',
	'emerald',
	'blue',
	'amber',
	'rose',
	'gray'
];

// Osool-ink primary button, shared by the buttons widget and the form submit.
export const BRAND_BUTTON_CLASS =
	'bg-gradient-to-r from-[#026c80] to-[#00313f] text-white enabled:hover:opacity-90';

// Deterministic badge color for table cells, hashed from the cell text.
export const badgeColorForValue = (value: string): WidgetColor => {
	let hash = 0;
	for (let i = 0; i < value.length; i++) {
		hash = (hash * 31 + value.charCodeAt(i)) | 0;
	}
	return COLORS[Math.abs(hash) % COLORS.length];
};

export const isArcChart = (widget: ChartWidget): boolean =>
	widget.chart === 'pie' || widget.chart === 'donut';

// Vega expression: compact number label ("7.12B" instead of d3's "7.12G").
const COMPACT_VALUE_EXPR = "replace(format(datum.value, '.3~s'), 'G', 'B')";

// Translate the compact chart schema into a themed vega-lite spec sized for
// the chat column. Rendered as a live vega view (tooltips need interactivity).
export const toVegaLiteSpec = (widget: ChartWidget, dark: boolean, width = 520): object => {
	const labelColor = dark ? '#9ca3af' : '#5b7683';
	const labelStrong = dark ? '#d1d5db' : '#00313f';
	const gridColor = dark ? 'rgba(156, 163, 175, 0.14)' : 'rgba(0, 49, 63, 0.1)';
	const colors = dark ? CHART_COLORS_DARK : CHART_COLORS_LIGHT;

	const config = {
		background: 'transparent',
		font: 'ui-sans-serif, system-ui, sans-serif',
		bar: { cornerRadiusEnd: 4 },
		arc: {},
		line: { strokeWidth: 2.5 },
		point: { size: 60, filled: true },
		area: { opacity: 0.4, line: { strokeWidth: 2 } },
		axis: {
			labelColor,
			titleColor: labelColor,
			gridColor,
			gridDash: [3, 3],
			domainOpacity: 0,
			tickOpacity: 0,
			labelFontSize: 11,
			titleFontSize: 11,
			labelPadding: 6
		},
		legend: {
			labelColor,
			titleColor: labelColor,
			labelFontSize: 11,
			symbolSize: 70,
			symbolType: 'circle'
		},
		range: { category: colors },
		view: { stroke: null }
	};

	const valueLabelExpr =
		widget.format === 'percent' ? "format(datum.value, '.0%')" : COMPACT_VALUE_EXPR;

	if (isArcChart(widget)) {
		// Arc charts use the first series only; x entries are the slice labels.
		const values = widget.series[0].values.map((value, idx) => ({
			label: String(widget.x[idx] ?? idx + 1),
			value
		}));
		const total = values.reduce((sum, v) => sum + v.value, 0);
		const donut = widget.chart === 'donut';

		return {
			$schema: 'https://vega.github.io/schema/vega-lite/v5.json',
			width: Math.min(width, 340),
			height: 240,
			autosize: { type: 'fit', contains: 'padding' },
			data: { values },
			transform: [
				{ joinaggregate: [{ op: 'sum', field: 'value', as: 'total' }] },
				{ calculate: 'datum.value / datum.total', as: 'pct' },
				{
					calculate: "datum.label + ' ' + format(datum.value / datum.total, '.0%')",
					as: 'sliceLabel'
				}
			],
			encoding: {
				theta: { field: 'value', type: 'quantitative', stack: true },
				color: {
					field: 'label',
					type: 'nominal',
					legend: { title: null, orient: 'bottom' },
					sort: null
				},
				tooltip: [
					{ field: 'label', type: 'nominal', title: 'Label' },
					{ field: 'value', type: 'quantitative', format: ',', title: 'Value' },
					{ field: 'pct', type: 'quantitative', format: '.1%', title: 'Share' }
				]
			},
			layer: [
				{
					mark: {
						type: 'arc',
						outerRadius: 82,
						...(donut ? { innerRadius: 52 } : {}),
						cornerRadius: 3,
						padAngle: 0.008
					}
				},
				{
					// Slice labels only where the slice is big enough to carry one.
					mark: { type: 'text', radius: 100, fontSize: 10.5, fontWeight: 600, fill: labelStrong },
					encoding: {
						text: { field: 'sliceLabel' },
						opacity: { condition: { test: 'datum.pct < 0.06', value: 0 }, value: 1 }
					}
				},
				...(donut
					? [
							{
								mark: { type: 'text', fontSize: 17, fontWeight: 700, fill: labelStrong },
								encoding: {
									theta: null,
									color: null,
									tooltip: null,
									text: { value: formatNumber(total) }
								}
							}
						]
					: [])
			],
			config
		};
	}

	const rows: { x: string | number; series: string; value: number }[] = [];
	for (const series of widget.series) {
		series.values.forEach((value, idx) => {
			rows.push({ x: widget.x[idx] ?? idx + 1, series: series.name ?? '', value });
		});
	}

	const multiSeries = widget.series.length > 1;
	const xIsNumeric = widget.x.every((value) => typeof value === 'number');
	const totalPoints = widget.x.length * widget.series.length;

	// Data labels only when there's room for them.
	const showLabels =
		!widget.stacked &&
		widget.chart !== 'scatter' &&
		(widget.chart === 'bar' ? totalPoints <= 14 : widget.x.length <= 12 && totalPoints <= 24);

	const markType =
		widget.chart === 'line'
			? { type: 'line', point: true }
			: widget.chart === 'area'
				? { type: 'area', point: true }
				: widget.chart === 'scatter'
					? { type: 'point' }
					: { type: 'bar' };

	const encoding: Record<string, unknown> = {
		x: {
			field: 'x',
			type: xIsNumeric ? 'quantitative' : widget.chart === 'bar' ? 'nominal' : 'ordinal',
			axis: { title: null, grid: false, labelAngle: widget.x.length > 8 ? -40 : 0 },
			...(xIsNumeric ? {} : { sort: null })
		},
		y: {
			field: 'value',
			type: 'quantitative',
			axis: {
				title: null,
				tickCount: 5,
				...(widget.format === 'percent'
					? { format: '.0%' }
					: { format: '~s', labelExpr: "replace(datum.label, 'G', 'B')" })
			},
			...(widget.stacked && (widget.chart === 'bar' || widget.chart === 'area')
				? { stack: 'zero' }
				: {})
		},
		tooltip: [
			{ field: 'x', type: 'nominal', title: 'Item' },
			...(multiSeries ? [{ field: 'series', type: 'nominal', title: 'Series' }] : []),
			{ field: 'value', type: 'quantitative', format: ',', title: 'Value' }
		]
	};

	if (multiSeries) {
		encoding.color = { field: 'series', type: 'nominal', legend: { title: null, orient: 'top' }, sort: null };
		if (widget.chart === 'bar' && !widget.stacked) {
			encoding.xOffset = { field: 'series' };
		}
	} else {
		encoding.color = { value: colors[0] };
	}

	return {
		$schema: 'https://vega.github.io/schema/vega-lite/v5.json',
		width,
		height: 210,
		autosize: { type: 'fit', contains: 'padding' },
		data: { values: rows },
		transform: [{ calculate: valueLabelExpr, as: 'valueLabel' }],
		encoding,
		layer: [
			{ mark: markType },
			...(showLabels
				? [
						{
							mark: {
								type: 'text',
								baseline: 'bottom',
								dy: widget.chart === 'bar' ? -4 : -8,
								fontSize: 10,
								fontWeight: 600,
								fill: labelStrong
							},
							encoding: { text: { field: 'valueLabel' }, color: null, tooltip: null }
						}
					]
				: [])
		],
		config
	};
};

// Parse the optional `<!-- height: 400 -->` hint on the first line of a
// widget-html document.
export const parseHeightHint = (html: string): number | null => {
	const match = html.match(/^\s*<!--\s*height:\s*(\d+)\s*-->/);
	if (!match) return null;
	return Math.min(Math.max(parseInt(match[1], 10), 80), 640);
};

// Fill a form template's {name} placeholders; fall back to "label: value" lines.
export const fillTemplate = (
	template: string | undefined,
	values: Record<string, string>,
	labels: Record<string, string>
): string => {
	if (template) {
		return template.replace(/\{(\w+)\}/g, (raw, name) => values[name] ?? raw);
	}
	return Object.entries(values)
		.filter(([, value]) => value !== '')
		.map(([name, value]) => `${labels[name] ?? name}: ${value}`)
		.join('\n');
};
