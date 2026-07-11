/**
 * Pure time-of-day buckets for the /home hero. Thresholds mirror
 * docs/mockups/hub-homepage-v6.html. The component maps these
 * discriminants to i18n strings.
 */
export type Greeting = 'morning' | 'afternoon' | 'evening';
export type Daymark = 'sun' | 'moon';
export type Wish = 'bright' | 'rest' | 'calm';

export function greetingForHour(h: number): Greeting {
	if (h < 12) return 'morning';
	if (h < 17) return 'afternoon';
	return 'evening';
}

export function daymarkForHour(h: number): Daymark {
	return h >= 19 || h < 6 ? 'moon' : 'sun';
}

export function wishForHour(h: number): Wish {
	if (h < 12) return 'bright';
	if (h < 17) return 'rest';
	return 'calm';
}
