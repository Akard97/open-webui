import { theme as themeStore } from '$lib/stores';

/**
 * Every theme class name applyTheme may add to <html>, so the stale ones can
 * be stripped before applying the active theme. Single source of truth shared
 * by Settings/General.svelte and the rail ThemeSwitcher.
 */
export const THEME_LIST = ['dark', 'light', 'oled-dark'];

/** True when the OS prefers a dark color scheme. SSR-safe (false on the server). */
export function prefersSystemDark(): boolean {
	return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/**
 * Collapse a stored theme to the light/dark mode that is *effectively* showing:
 * 'system' resolves via the OS preference, 'oled-dark' counts as 'dark'. Pure so
 * it can be unit-tested without a DOM.
 */
export function resolveMode(theme: string, systemPrefersDark: boolean): 'light' | 'dark' {
	if (theme === 'system') {
		return systemPrefersDark ? 'dark' : 'light';
	}
	return theme === 'light' ? 'light' : 'dark';
}

/**
 * Apply a theme to the document: toggle the <html> classes, restore the gray
 * CSS variables (the part that separates plain Dark from OLED), and update the
 * meta theme-color. Ported from Settings/General.svelte with SSR guards added.
 * No-op during SSR.
 */
export function applyTheme(_theme: string): void {
	if (typeof document === 'undefined') {
		return;
	}

	let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

	if (_theme === 'system') {
		themeToApply = prefersSystemDark() ? 'dark' : 'light';
	}

	if (themeToApply === 'dark' && !_theme.includes('oled')) {
		document.documentElement.style.setProperty('--color-gray-800', '#333');
		document.documentElement.style.setProperty('--color-gray-850', '#262626');
		document.documentElement.style.setProperty('--color-gray-900', '#171717');
		document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
	}

	THEME_LIST.filter((e) => e !== themeToApply).forEach((e) => {
		e.split(' ').forEach((cls) => {
			document.documentElement.classList.remove(cls);
		});
	});

	themeToApply.split(' ').forEach((cls) => {
		document.documentElement.classList.add(cls);
	});

	const metaThemeColor = document.querySelector('meta[name="theme-color"]');
	if (metaThemeColor) {
		if (_theme.includes('system')) {
			const systemTheme = prefersSystemDark() ? 'dark' : 'light';
			metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
		} else {
			metaThemeColor.setAttribute(
				'content',
				_theme === 'dark' ? '#171717' : _theme === 'oled-dark' ? '#000000' : '#ffffff'
			);
		}
	}

	if (typeof window !== 'undefined') {
		const externalApplyTheme = (window as unknown as { applyTheme?: () => void }).applyTheme;
		if (externalApplyTheme) {
			externalApplyTheme();
		}
	}

	if (_theme.includes('oled')) {
		document.documentElement.style.setProperty('--color-gray-800', '#101010');
		document.documentElement.style.setProperty('--color-gray-850', '#050505');
		document.documentElement.style.setProperty('--color-gray-900', '#000000');
		document.documentElement.style.setProperty('--color-gray-950', '#000000');
		document.documentElement.classList.add('dark');
	}
}

/**
 * Persist and apply a theme: update the store, write localStorage, mutate the
 * document. The single entry point used by both the Settings dropdown and the
 * rail switcher so they can never drift.
 */
export function setTheme(theme: string): void {
	themeStore.set(theme);
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem('theme', theme);
	}
	applyTheme(theme);
}
