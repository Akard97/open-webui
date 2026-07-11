import { describe, it, expect } from 'vitest';
import { greetingForHour, daymarkForHour, wishForHour } from './greeting';

describe('greetingForHour', () => {
	it('morning strictly before 12', () => {
		expect(greetingForHour(0)).toBe('morning');
		expect(greetingForHour(6)).toBe('morning');
		expect(greetingForHour(11)).toBe('morning');
	});
	it('afternoon from 12 strictly before 17', () => {
		expect(greetingForHour(12)).toBe('afternoon');
		expect(greetingForHour(16)).toBe('afternoon');
	});
	it('evening from 17', () => {
		expect(greetingForHour(17)).toBe('evening');
		expect(greetingForHour(23)).toBe('evening');
	});
});

describe('daymarkForHour', () => {
	it('moon from 19:00 and before 06:00', () => {
		expect(daymarkForHour(19)).toBe('moon');
		expect(daymarkForHour(23)).toBe('moon');
		expect(daymarkForHour(0)).toBe('moon');
		expect(daymarkForHour(5)).toBe('moon');
	});
	it('sun from 06:00 strictly before 19:00', () => {
		expect(daymarkForHour(6)).toBe('sun');
		expect(daymarkForHour(12)).toBe('sun');
		expect(daymarkForHour(18)).toBe('sun');
	});
});

describe('wishForHour', () => {
	it('bright strictly before 12', () => {
		expect(wishForHour(0)).toBe('bright');
		expect(wishForHour(11)).toBe('bright');
	});
	it('rest from 12 strictly before 17', () => {
		expect(wishForHour(12)).toBe('rest');
		expect(wishForHour(16)).toBe('rest');
	});
	it('calm from 17', () => {
		expect(wishForHour(17)).toBe('calm');
		expect(wishForHour(23)).toBe('calm');
	});
});
