export const EFFORT_LEVELS = ['default', 'xhigh', 'max'] as const;
export type EffortLevel = (typeof EFFORT_LEVELS)[number];

export const normalizeEffort = (value: unknown): EffortLevel =>
	EFFORT_LEVELS.includes(value as EffortLevel) ? (value as EffortLevel) : 'default';

export const levelIndex = (level: EffortLevel): number => EFFORT_LEVELS.indexOf(level);

export const indexToLevel = (index: number): EffortLevel =>
	EFFORT_LEVELS[Math.min(EFFORT_LEVELS.length - 1, Math.max(0, Math.round(index)))];

export const functionIdFromModelId = (modelId: string): string => modelId.split('.')[0];

export const specHasEffort = (spec: unknown): boolean => {
	const enumValues = (spec as { properties?: { EFFORT?: { enum?: unknown } } })?.properties
		?.EFFORT?.enum;
	return (
		Array.isArray(enumValues) && EFFORT_LEVELS.every((level) => enumValues.includes(level))
	);
};

export const mergeEffort = (valves: unknown, level: EffortLevel): Record<string, unknown> => ({
	...(valves && typeof valves === 'object' && !Array.isArray(valves)
		? (valves as Record<string, unknown>)
		: {}),
	EFFORT: level
});
