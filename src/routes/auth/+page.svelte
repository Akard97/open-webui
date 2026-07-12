<script lang="ts">
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';

	import { toast } from 'svelte-sonner';

	import { onMount, onDestroy, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import {
		ldapUserSignIn,
		getSessionUser,
		userSignIn,
		userSignUp,
		updateUserTimezone
	} from '$lib/apis/auths';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket, theme } from '$lib/stores';

	import { generateInitialsImage, getUserTimezone } from '$lib/utils';
	import { setTheme, resolveMode, prefersSystemDark } from '$lib/utils/theme';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import OnBoarding from '$lib/components/OnBoarding.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	import osoolLogo from '$lib/assets/osool-logo.png';
	import artCampus from '$lib/assets/signin/signin-osool-campus.webp';
	import artTowers from '$lib/assets/signin/signin-osool-towers.webp';
	import artCourtyard from '$lib/assets/signin/signin-osool-courtyard.webp';

	import { daymarkForHour, wishForHour } from '../(app)/home/greeting';

	const i18n = getContext<any>('i18n');

	let loaded = false;

	let mode = $config?.features.enable_ldap ? 'ldap' : 'signin';

	let form = null;

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';

	let ldapUsername = '';

	// Computed once on load, like the mockup / home page.
	const now = new Date();
	const h = now.getHours();
	const daymark = daymarkForHour(h);
	const wishKey = wishForHour(h);

	$: dateText = now.toLocaleDateString($i18n.language, {
		weekday: 'long',
		month: 'long',
		day: 'numeric'
	});

	$: artWish = {
		bright: $i18n.t('start the morning bright'),
		rest: $i18n.t('make the afternoon count'),
		calm: $i18n.t('wind down, we kept things ready')
	}[wishKey];

	// rotating art pane — first image random, advances every 10s, dots switch manually
	const artImages = [artCampus, artTowers, artCourtyard];
	let artIdx = 0;
	let artTimer: ReturnType<typeof setInterval> | undefined;

	const startArtTimer = () => {
		if (artTimer) {
			clearInterval(artTimer);
		}
		artTimer = setInterval(() => {
			artIdx = (artIdx + 1) % artImages.length;
		}, 10000);
	};

	const selectArt = (i: number) => {
		artIdx = i;
		startArtTimer();
	};

	$: themeMode = resolveMode($theme, prefersSystemDark());
	const toggleTheme = () => setTheme(themeMode === 'dark' ? 'light' : 'dark');

	$: onboardingActive = $config?.onboarding ?? false;
	$: autoSignIn =
		($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false;
	$: showForm = $config?.features.enable_login_form || $config?.features.enable_ldap || form;

	$: heading = onboardingActive
		? { pre: $i18n.t('Create the'), word: $i18n.t('admin account') }
		: mode === 'ldap'
			? { pre: $i18n.t('Sign in with'), word: 'LDAP' }
			: mode === 'signup'
				? { pre: $i18n.t('Create your'), word: $i18n.t('account') }
				: { pre: $i18n.t('Welcome'), word: $i18n.t('back') };

	$: subText = onboardingActive
		? `${$WEBUI_NAME} ${$i18n.t(
				'does not make any external connections, and your data stays securely on your locally hosted server.'
			)}`
		: mode === 'signup'
			? $i18n.t("A few details and you're in — your workspace is waiting.")
			: $i18n.t('Sign in to reach Osool AI, WorkOS and everything in between.');

	const setSessionUser = async (sessionUser, redirectPath: string | null = null) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t(`You're now logged in.`));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}
			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			// Update user timezone
			const timezone = getUserTimezone();
			if (sessionUser.token && timezone) {
				updateUserTimezone(sessionUser.token, timezone);
			}

			if (!redirectPath) {
				redirectPath = $page.url.searchParams.get('redirect') || '/home';
			}

			goto(redirectPath);
			localStorage.removeItem('redirectPath');
		}
	};

	const signInHandler = async () => {
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		if ($config?.features?.enable_signup_password_confirmation) {
			if (password !== confirmPassword) {
				toast.error($i18n.t('Passwords do not match.'));
				return;
			}
		}

		const sessionUser = await userSignUp(name, email, password, generateInitialsImage(name)).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		if (mode === 'ldap') {
			await ldapSignInHandler();
		} else if (mode === 'signin') {
			await signInHandler();
		} else {
			await signUpHandler();
		}
	};

	const oauthCallbackHandler = async () => {
		// Get the value of the 'token' cookie
		function getCookie(name) {
			const match = document.cookie.match(
				new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)')
			);
			return match ? decodeURIComponent(match[1]) : null;
		}

		const token = getCookie('token');
		if (!token) {
			return;
		}

		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!sessionUser) {
			return;
		}

		localStorage.token = token;
		await setSessionUser(sessionUser, localStorage.getItem('redirectPath') || null);
	};

	let onboarding = false;

	onMount(async () => {
		artIdx = Math.floor(Math.random() * artImages.length);
		startArtTimer();

		const redirectPath = $page.url.searchParams.get('redirect');
		if ($user !== undefined) {
			goto(redirectPath || '/home');
		} else {
			if (redirectPath) {
				localStorage.setItem('redirectPath', redirectPath);
			}
		}

		const error = $page.url.searchParams.get('error');
		if (error) {
			toast.error(error);
		}

		await oauthCallbackHandler();
		form = $page.url.searchParams.get('form');

		loaded = true;

		if (autoSignIn) {
			await signInHandler();
		} else {
			onboarding = $config?.onboarding ?? false;
		}
	});

	onDestroy(() => {
		if (artTimer) {
			clearInterval(artTimer);
		}
	});
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

<OnBoarding
	bind:show={onboarding}
	getStartedHandler={() => {
		onboarding = false;
		mode = $config?.features.enable_ldap ? 'ldap' : 'signup';
	}}
/>

<div class="auth-root" id="auth-page">
	<svg width="0" height="0" style="position:absolute">
		<defs>
			<!-- warm underline gradient: amber melting into brand teal (same as home v6) -->
			<linearGradient id="warmline-auth" x1="0" y1="0" x2="1" y2="0">
				<stop offset="0" stop-color="#e0a13f" />
				<stop offset="1" stop-color="#3d94a8" />
			</linearGradient>
		</defs>
		<symbol id="i-sun" viewBox="0 0 24 24"><path d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z"/></symbol>
		<symbol id="i-moon" viewBox="0 0 24 24"><path d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"/></symbol>
		<symbol id="i-mail" viewBox="0 0 24 24"><path d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75"/></symbol>
		<symbol id="i-key" viewBox="0 0 24 24"><path d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"/></symbol>
		<symbol id="i-user" viewBox="0 0 24 24"><path d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"/></symbol>
		<symbol id="i-arrow" viewBox="0 0 24 24"><path d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"/></symbol>
		<symbol id="i-chevl" viewBox="0 0 24 24"><path d="M15.75 19.5 8.25 12l7.5-7.5"/></symbol>
		<symbol id="i-chevr" viewBox="0 0 24 24"><path d="m8.25 4.5 7.5 7.5-7.5 7.5"/></symbol>
		<symbol id="i-lock" viewBox="0 0 24 24"><path d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"/></symbol>
		<symbol id="i-sparkles" viewBox="0 0 24 24"><path d="M9.813 15.904 9.5 16.938l-.313-1.034a3.75 3.75 0 0 0-2.466-2.466L5.687 13.5l1.034-.313a3.75 3.75 0 0 0 2.466-2.466L9.5 9.688l.313 1.034a3.75 3.75 0 0 0 2.466 2.466l1.034.312-1.034.313a3.75 3.75 0 0 0-2.466 2.466ZM18.259 8.715 18 9.75l-.259-1.035a2.625 2.625 0 0 0-1.956-1.956L14.75 6.5l1.035-.259a2.625 2.625 0 0 0 1.956-1.956L18 3.25l.259 1.035a2.625 2.625 0 0 0 1.956 1.956l1.035.259-1.035.259a2.625 2.625 0 0 0-1.956 1.956ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"/></symbol>
	</svg>

	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region"></div>

	{#if loaded}
		<main class="split">
			<!-- ================= form pane ================= -->
			<section class="pane form-pane">
				<div class="lines" aria-hidden="true">
					<i class="h" style="top:12%"></i>
					<i class="h" style="top:88%"></i>
					<i class="v" style="left:10%"></i>
					<i class="v" style="left:90%"></i>
					<s style="left:10%; top:12%"></s>
					<s style="left:90%; top:12%"></s>
					<s style="left:10%; top:88%"></s>
					<s style="left:90%; top:88%"></s>
				</div>

				<header class="brand">
					<img src={osoolLogo} alt="Osool" />
					<span
						><b>{$i18n.t('Osool Intelligence Hub')}</b><small>{$i18n.t('Internal platform')}</small
						></span
					>
					<button
						class="theme-switch"
						class:night={themeMode === 'dark'}
						type="button"
						role="switch"
						aria-checked={themeMode === 'dark'}
						aria-label={$i18n.t('Toggle theme')}
						on:click={toggleTheme}
					>
						<span class="knob"
							><svg class="icon"><use href={themeMode === 'dark' ? '#i-moon' : '#i-sun'} /></svg></span
						>
						<span class="lbl">{themeMode === 'dark' ? $i18n.t('dark') : $i18n.t('light')}</span>
					</button>
				</header>

				{#if autoSignIn}
					<div class="form-wrap">
						<div class="signing">
							<span>{$i18n.t('Signing in to {{WEBUI_NAME}}', { WEBUI_NAME: $WEBUI_NAME })}</span>
							<Spinner className="size-5" />
						</div>
					</div>
				{:else}
					<div class="form-wrap">
						<span class="eyebrow"
							><svg class="icon"><use href={daymark === 'moon' ? '#i-moon' : '#i-sun'} /></svg><span
								>{dateText}</span
							></span
						>

						<h1>
							{heading.pre}
							<span class="name"
								>{heading.word}<svg
									class="uline"
									viewBox="0 0 120 12"
									preserveAspectRatio="none"
									aria-hidden="true"><path d="M3 9 C 28 3.5, 62 3, 117 6.5" pathLength="100" /></svg
								></span
							>
						</h1>

						<p class="sub">{subText}</p>

						{#if showForm}
							<form
								on:submit={(e) => {
									e.preventDefault();
									submitHandler();
								}}
							>
								{#if mode === 'signup'}
									<div class="field">
										<label for="name">{$i18n.t('Full name')}</label>
										<div class="box">
											<svg class="icon"><use href="#i-user" /></svg>
											<input
												bind:value={name}
												type="text"
												id="name"
												autocomplete="name"
												placeholder={$i18n.t('Enter Your Full Name')}
												required
											/>
										</div>
									</div>
								{/if}

								{#if mode === 'ldap'}
									<div class="field">
										<label for="username">{$i18n.t('Username')}</label>
										<div class="box">
											<svg class="icon"><use href="#i-user" /></svg>
											<input
												bind:value={ldapUsername}
												type="text"
												id="username"
												name="username"
												autocomplete="username"
												placeholder={$i18n.t('Enter Your Username')}
												required
											/>
										</div>
									</div>
								{:else}
									<div class="field">
										<label for="email">{$i18n.t('Email')}</label>
										<div class="box">
											<svg class="icon"><use href="#i-mail" /></svg>
											<input
												bind:value={email}
												type="email"
												id="email"
												name="email"
												autocomplete="email"
												placeholder={$i18n.t('Enter Your Email')}
												required
											/>
										</div>
									</div>
								{/if}

								<div class="field">
									<label for="password">{$i18n.t('Password')}</label>
									<div class="box">
										<svg class="icon"><use href="#i-key" /></svg>
										<SensitiveInput
											bind:value={password}
											type="password"
											id="password"
											name="password"
											placeholder={$i18n.t('Enter Your Password')}
											autocomplete={mode === 'signup' ? 'new-password' : 'current-password'}
											outerClassName="flex flex-1 items-center min-w-0"
											inputClassName="w-full text-sm bg-transparent"
											showButtonClassName="peek"
											screenReader={true}
											required
										/>
									</div>
								</div>

								{#if mode === 'signup' && $config?.features?.enable_signup_password_confirmation}
									<div class="field">
										<label for="confirm-password">{$i18n.t('Confirm Password')}</label>
										<div class="box">
											<svg class="icon"><use href="#i-key" /></svg>
											<SensitiveInput
												bind:value={confirmPassword}
												type="password"
												id="confirm-password"
												name="confirm-password"
												placeholder={$i18n.t('Confirm Your Password')}
												autocomplete="new-password"
												outerClassName="flex flex-1 items-center min-w-0"
												inputClassName="w-full text-sm bg-transparent"
												showButtonClassName="peek"
												screenReader={true}
												required
											/>
										</div>
									</div>
								{/if}

								<button class="cta" type="submit">
									<span>
										{#if mode === 'ldap'}
											{$i18n.t('Authenticate')}
										{:else if mode === 'signin'}
											{$i18n.t('Sign in')}
										{:else if onboardingActive}
											{$i18n.t('Create Admin Account')}
										{:else}
											{$i18n.t('Create Account')}
										{/if}
									</span>
									<svg class="icon"><use href="#i-arrow" /></svg>
								</button>
							</form>
						{/if}

						{#if $config?.oauth?.providers?.microsoft}
							{#if showForm}
								<div class="divider">{$i18n.t('or continue with')}</div>
							{/if}
							<div class="sso">
								<button
									type="button"
									on:click={() => {
										window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
									}}
								>
									<svg class="mark" viewBox="0 0 21 21" aria-hidden="true">
										<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
											x="1"
											y="11"
											width="9"
											height="9"
											fill="#00a4ef"
										/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
											x="11"
											y="11"
											width="9"
											height="9"
											fill="#ffb900"
										/>
									</svg>
									{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}
								</button>
							</div>
						{/if}

						{#if showForm && mode !== 'ldap' && $config?.features.enable_signup && !onboardingActive}
							<p class="alt">
								{mode === 'signin'
									? $i18n.t("Don't have an account?")
									: $i18n.t('Already have an account?')}
								<button
									type="button"
									on:click={() => {
										mode = mode === 'signin' ? 'signup' : 'signin';
									}}
								>
									{mode === 'signin' ? $i18n.t('Sign up') : $i18n.t('Sign in')}
								</button>
							</p>
						{/if}

						{#if $config?.features.enable_ldap && $config?.features.enable_login_form}
							<p class="ldap">
								<button
									type="button"
									on:click={() => {
										if (mode === 'ldap') mode = onboardingActive ? 'signup' : 'signin';
										else mode = 'ldap';
									}}
								>
									{mode === 'ldap' ? $i18n.t('Continue with Email') : $i18n.t('Continue with LDAP')}
								</button>
							</p>
						{/if}

						{#if $config?.metadata?.login_footer}
							<div class="login-footer marked">
								{@html DOMPurify.sanitize(marked($config?.metadata?.login_footer))}
							</div>
						{/if}
					</div>
				{/if}

				<footer class="form-foot">
					<span class="lock"
						><svg class="icon"><use href="#i-lock" /></svg>
						{$i18n.t('Your data stays on Osool servers')}</span
					>
					<span>{$i18n.t('Need help? IT Service Desk')}</span>
				</footer>
			</section>

			<!-- ================= art pane ================= -->
			<aside class="pane art-pane">
				{#each artImages as src, i}
					<img class="art" class:active={i === artIdx} {src} alt="" />
				{/each}

				<button
					class="art-nav prev"
					type="button"
					aria-label={$i18n.t('Previous image')}
					on:click={() => selectArt((artIdx + artImages.length - 1) % artImages.length)}
				>
					<svg class="icon"><use href="#i-chevl" /></svg>
				</button>
				<button
					class="art-nav next"
					type="button"
					aria-label={$i18n.t('Next image')}
					on:click={() => selectArt((artIdx + 1) % artImages.length)}
				>
					<svg class="icon"><use href="#i-chevr" /></svg>
				</button>

				<div class="art-float">
					<span class="mini"><svg class="icon"><use href="#i-sparkles" /></svg></span>
					<span
						><b>{$i18n.t('Osool AI is online')}</b><small
							>{$i18n.t('Connected to company knowledge')}</small
						></span
					>
				</div>

				<div class="art-copy">
					<h2>
						{$i18n.t('One door to everything Osool')} <em>{artWish}</em>.
					</h2>
					<p>
						{$i18n.t(
							"Ask, plan, and find what you need. Your tools and your company's knowledge, together in one place."
						)}
					</p>
					<div class="art-chips">
						<span><i></i> {$i18n.t('Osool AI')}</span>
						<span><i></i> {$i18n.t('WorkOS')}</span>
						<span class="soon"><i></i> {$i18n.t('Presentation Maker')} — {$i18n.t('soon')}</span>
						<span class="soon"><i></i> {$i18n.t('Policies Library')} — {$i18n.t('soon')}</span>
					</div>
				</div>
			</aside>
		</main>
	{/if}
</div>

<style>
	.auth-root {
		/* ramps come from src/tailwind.css */
		--gray-50: var(--color-gray-50);
		--gray-100: var(--color-gray-100);
		--gray-200: var(--color-gray-200);
		--gray-400: var(--color-gray-400);
		--gray-500: var(--color-gray-500);
		--gray-600: var(--color-gray-600);
		--gray-800: var(--color-gray-800);
		--gray-850: var(--color-gray-850);
		--gray-900: var(--color-gray-900);
		--gray-950: var(--color-gray-950);

		--brand-100: var(--color-brand-100);
		--brand-400: var(--color-brand-400);
		--brand-500: var(--color-brand-500);
		--brand-600: var(--color-brand-600);

		/* warm layer (matches home v6) */
		--sun-ink: oklch(0.52 0.115 62);
		--sunwash: oklch(0.9 0.07 80 / 0.26);

		--backdrop: var(--gray-50);
		--frame: #ffffff;
		--card: #ffffff;
		--ink: var(--gray-800);
		--muted: var(--gray-600);
		--faint: var(--gray-500);
		--placeholder: var(--gray-400);
		--border: var(--gray-200);
		--hairline: var(--gray-100);
		--hover: var(--gray-100);
		--gridline: oklch(0.32 0 0 / 0.05);
		--node: oklch(0.32 0 0 / 0.2);
		--wash: oklch(0.945 0.028 216.54 / 0.45);
		--accent: #00313f; /* brand-700 / Pantone 309 C */
		--mid: var(--brand-600);
		--cta: #00313f;
		--cta-fg: #fff;
		--shadow-m: 0 1px 3px oklch(0 0 0 / 0.05), 0 8px 24px oklch(0 0 0 / 0.06);

		/* replaces the mockup's body responsibilities */
		position: relative;
		min-height: 100dvh;
		display: grid;
		place-items: center;
		background: var(--backdrop);
		color: var(--ink);
		font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Vazirmatn', ui-sans-serif, system-ui,
			'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif;
		-webkit-font-smoothing: antialiased;
		text-rendering: optimizeLegibility;
	}
	:global(.dark) .auth-root {
		--sun-ink: oklch(0.82 0.1 78);
		--sunwash: oklch(0.5 0.09 70 / 0.14);

		--backdrop: var(--gray-950);
		--frame: var(--gray-900);
		--card: var(--gray-850);
		--ink: var(--gray-100);
		--muted: var(--gray-400);
		--faint: oklch(0.6 0 0);
		--placeholder: oklch(0.55 0 0);
		--border: oklch(1 0 0 / 0.1);
		--hairline: oklch(1 0 0 / 0.06);
		--hover: oklch(1 0 0 / 0.06);
		--gridline: oklch(1 0 0 / 0.05);
		--node: oklch(1 0 0 / 0.2);
		--wash: oklch(0.3 0.05 221.22 / 0.35);
		--accent: var(--brand-400);
		--mid: var(--brand-500);
		--cta: var(--brand-600);
		--cta-fg: #fff;
		--shadow-m: 0 1px 3px oklch(0 0 0 / 0.35), 0 8px 24px oklch(0 0 0 / 0.35);
	}

	h1,
	h2 {
		font-family: 'Archivo', 'Vazirmatn', sans-serif;
	}
	.icon {
		width: 1.125rem;
		height: 1.125rem;
		stroke: currentColor;
		fill: none;
		stroke-width: 1.5;
		stroke-linecap: round;
		stroke-linejoin: round;
		flex: none;
	}

	.auth-root :global(a:focus-visible),
	.auth-root :global(button:focus-visible) {
		outline: 2px solid var(--mid);
		outline-offset: 2px;
		border-radius: 0.6rem;
	}

	/* motion */
	@keyframes fadeUp {
		from {
			opacity: 0;
			transform: translateY(14px);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}
	@keyframes floaty {
		0%,
		100% {
			transform: translateY(0);
		}
		50% {
			transform: translateY(-7px);
		}
	}
	@keyframes draw {
		to {
			stroke-dashoffset: 0;
		}
	}
	@keyframes blip {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.35;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.auth-root :global(*),
		.auth-root :global(*)::before,
		.auth-root :global(*)::after {
			animation: none !important;
			transition: none !important;
		}
		.uline path {
			stroke-dashoffset: 0 !important;
		}
	}

	/* ---------- split canvas — centered card, backdrop shows around it ---------- */
	.split {
		width: min(100% - 2.4rem, 72rem);
		min-height: min(44rem, calc(100dvh - 2.4rem));
		margin: 1.2rem 0;
		display: grid;
		grid-template-columns: minmax(24rem, 42%) 1fr;
		gap: 0.9rem;
	}

	/* ---------- form pane (framed like the app canvas) ---------- */
	.pane.form-pane {
		position: relative;
		overflow: hidden;
		background: var(--frame);
		border: 1px solid var(--border);
		border-radius: 1.25rem;
		box-shadow: var(--shadow-m);
		display: flex;
		flex-direction: column;
		padding: 2rem 3rem;
	}
	/* blueprint lines + diamond nodes (same motif as home hero) */
	.form-pane .lines {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}
	.form-pane .lines i {
		position: absolute;
		background: var(--gridline);
	}
	.form-pane .lines i.h {
		left: 0;
		right: 0;
		height: 1px;
	}
	.form-pane .lines i.v {
		top: 0;
		bottom: 0;
		width: 1px;
	}
	.form-pane .lines s {
		position: absolute;
		width: 7px;
		height: 7px;
		border-radius: 2px;
		background: var(--frame);
		border: 1.5px solid var(--node);
		transform: translate(-50%, -50%) rotate(45deg);
	}
	/* dawn wash — teal top right, sun bottom left */
	.form-pane::after {
		content: '';
		position: absolute;
		inset: 0;
		pointer-events: none;
		background:
			radial-gradient(36rem 22rem at 96% 0%, var(--wash), transparent 62%),
			radial-gradient(30rem 20rem at 0% 104%, var(--sunwash), transparent 70%);
	}

	.brand {
		position: relative;
		z-index: 1;
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding-inline-start: 0.75rem;
		animation: fadeUp 0.5s cubic-bezier(0.22, 0.7, 0.3, 1) both;
	}
	.brand img {
		width: 2.1rem;
		height: 2.1rem;
		object-fit: contain;
		border-radius: 0.3rem;
	}
	:global(.dark) .brand img {
		filter: invert(1);
	}
	.brand b {
		font-family: 'Archivo', 'Vazirmatn', sans-serif;
		font-size: 0.9rem;
		font-weight: 550;
		letter-spacing: -0.005em;
	}
	.brand small {
		display: block;
		font-size: 0.62rem;
		color: var(--faint);
		margin-top: 0.05rem;
	}
	/* glowing glass toggle — sun knob + label (per reference) */
	.theme-switch {
		margin-inline-start: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.3rem;
		padding-inline-end: 0.95rem;
		border-radius: 999px;
		cursor: pointer;
		font: inherit;
		font-size: 0.74rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		border: 1px solid oklch(0.87 0.09 85 / 0.7);
		background: oklch(0.95 0.07 85 / 0.55);
		color: var(--sun-ink);
		backdrop-filter: blur(8px);
		transition:
			background 0.25s,
			border-color 0.25s,
			box-shadow 0.25s,
			color 0.25s;
	}
	.theme-switch .knob {
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 999px;
		display: grid;
		place-items: center;
		background: #fff;
		color: oklch(0.72 0.14 75);
		box-shadow: 0 1px 2px oklch(0 0 0 / 0.12);
		transition:
			background 0.25s,
			color 0.25s,
			box-shadow 0.25s;
	}
	.theme-switch .knob .icon {
		width: 1rem;
		height: 1rem;
	}
	.theme-switch.night {
		flex-direction: row-reverse;
		padding-inline-end: 0.3rem;
		padding-inline-start: 0.95rem;
		border-color: oklch(0.5 0.06 250 / 0.5);
		background: oklch(0.3 0.04 250 / 0.45);
		color: oklch(0.8 0.04 250);
	}
	.theme-switch.night .knob {
		background: oklch(0.28 0.03 260);
		color: oklch(0.85 0.06 250);
		box-shadow: 0 1px 2px oklch(0 0 0 / 0.3);
	}

	.form-wrap {
		position: relative;
		z-index: 1;
		margin: auto 0;
		width: 100%;
		max-width: 22.5rem;
		align-self: center;
		padding: 2.5rem 0;
	}
	.form-wrap > :global(*) {
		animation: fadeUp 0.55s cubic-bezier(0.22, 0.7, 0.3, 1) both;
	}
	.form-wrap > :global(*:nth-child(2)) {
		animation-delay: 0.06s;
	}
	.form-wrap > :global(*:nth-child(3)) {
		animation-delay: 0.12s;
	}
	.form-wrap > :global(*:nth-child(4)) {
		animation-delay: 0.18s;
	}
	.form-wrap > :global(*:nth-child(5)) {
		animation-delay: 0.24s;
	}
	.form-wrap > :global(*:nth-child(6)) {
		animation-delay: 0.3s;
	}
	.form-wrap > :global(*:nth-child(7)) {
		animation-delay: 0.36s;
	}

	.signing {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		font-size: 1.05rem;
		font-weight: 500;
		color: var(--ink);
	}

	.eyebrow {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.7rem;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--faint);
	}
	.eyebrow .icon {
		width: 0.85rem;
		height: 0.85rem;
		color: var(--sun-ink);
	}

	.form-wrap h1 {
		margin-top: 0.9rem;
		text-wrap: balance;
		font-size: clamp(1.7rem, 2.4vw, 2.1rem);
		font-weight: 400;
		letter-spacing: -0.01em;
		line-height: 1.2;
		color: var(--ink);
	}
	.form-wrap h1 .name {
		color: var(--accent);
		position: relative;
		display: inline-block;
	}
	/* hand-drawn warm underline, draws itself in (same as home v6) */
	.uline {
		position: absolute;
		left: -2%;
		right: -2%;
		bottom: -0.28em;
		width: 104%;
		height: 0.34em;
		overflow: visible;
	}
	.uline path {
		fill: none;
		stroke: url(#warmline-auth);
		stroke-width: 3.2;
		stroke-linecap: round;
		stroke-dasharray: 100;
		stroke-dashoffset: 100;
		animation: draw 0.8s 0.55s cubic-bezier(0.6, 0, 0.3, 1) forwards;
	}
	.form-wrap .sub {
		margin-top: 0.65rem;
		font-size: 0.88rem;
		color: var(--muted);
		line-height: 1.6;
	}

	/* ---------- fields ---------- */
	form {
		margin-top: 1.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}
	.field label {
		display: block;
		font-size: 0.74rem;
		font-weight: 600;
		color: var(--muted);
		margin-bottom: 0.4rem;
	}
	.field .box {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 0.8rem;
		padding: 0 0.9rem;
		height: 2.9rem;
		transition:
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.field .box:focus-within {
		border-color: color-mix(in srgb, var(--mid) 65%, var(--border));
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mid) 14%, transparent);
	}
	.field .box > .icon {
		width: 1rem;
		height: 1rem;
		color: var(--faint);
	}
	.field .box :global(input) {
		flex: 1;
		min-width: 0;
		border: none;
		outline: none;
		background: transparent;
		font: inherit;
		font-size: 0.88rem;
		color: var(--ink);
	}
	.field .box :global(input::placeholder) {
		color: var(--placeholder);
	}
	.field .box :global(.peek) {
		border: none;
		background: transparent;
		cursor: pointer;
		color: var(--faint);
		display: grid;
		place-items: center;
		padding: 0.2rem;
		border-radius: 0.4rem;
	}
	.field .box :global(.peek:hover) {
		color: var(--ink);
	}

	.cta {
		margin-top: 0.35rem;
		height: 2.9rem;
		border: none;
		border-radius: 999px;
		background: var(--cta);
		color: var(--cta-fg);
		font: inherit;
		font-size: 0.88rem;
		font-weight: 600;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		transition:
			opacity 0.15s,
			transform 0.15s;
	}
	.cta:hover {
		opacity: 0.92;
	}
	.cta:active {
		transform: scale(0.99);
	}
	.cta .icon {
		width: 0.95rem;
		height: 0.95rem;
		transition: transform 0.15s;
	}
	.cta:hover .icon {
		transform: translateX(3px);
	}

	/* ---------- divider + SSO ---------- */
	.divider {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		margin-top: 1.4rem;
		font-size: 0.72rem;
		font-weight: 500;
		color: var(--faint);
	}
	.divider::before,
	.divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background: var(--hairline);
	}

	.sso {
		margin-top: 1.4rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.sso button {
		height: 2.75rem;
		border-radius: 999px;
		cursor: pointer;
		border: 1px solid var(--border);
		background: var(--card);
		color: var(--ink);
		font: inherit;
		font-size: 0.84rem;
		font-weight: 500;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.65rem;
		transition:
			background 0.15s,
			border-color 0.15s;
	}
	.sso button:hover {
		background: var(--hover);
	}
	.sso button svg.mark {
		width: 1.05rem;
		height: 1.05rem;
		flex: none;
	}

	.alt {
		margin-top: 1.1rem;
		text-align: center;
		font-size: 0.78rem;
		color: var(--muted);
	}
	.alt button {
		border: none;
		background: transparent;
		padding: 0;
		cursor: pointer;
		font: inherit;
		color: var(--accent);
		font-weight: 600;
	}
	.alt button:hover {
		text-decoration: underline;
	}
	.ldap {
		margin-top: 0.55rem;
		text-align: center;
		font-size: 0.72rem;
	}
	.ldap button {
		border: none;
		background: transparent;
		padding: 0;
		cursor: pointer;
		font: inherit;
		color: var(--faint);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.ldap button:hover {
		color: var(--ink);
	}

	.login-footer {
		margin-top: 1.1rem;
		text-align: center;
		font-size: 0.7rem;
		color: var(--faint);
	}

	.form-foot {
		position: relative;
		z-index: 1;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		font-size: 0.7rem;
		color: var(--placeholder);
	}
	.form-foot .lock {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.form-foot .lock .icon {
		width: 0.78rem;
		height: 0.78rem;
	}

	/* ---------- art pane ---------- */
	.pane.art-pane {
		position: relative;
		overflow: hidden;
		border-radius: 1.25rem;
		border: 1px solid var(--border);
		box-shadow: var(--shadow-m);
		animation: fadeUp 0.7s 0.1s cubic-bezier(0.22, 0.7, 0.3, 1) both;
		background: #06222d;
	}
	.art-pane img.art {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: center 62%;
		opacity: 0;
		transition: opacity 1.2s ease;
	}
	.art-pane img.art.active {
		opacity: 1;
	}
	/* readable vignette top + bottom */
	.art-pane::after {
		content: '';
		position: absolute;
		inset: 0;
		pointer-events: none;
		background:
			linear-gradient(to bottom, oklch(0.18 0.03 230 / 0.55), transparent 26%),
			linear-gradient(to top, oklch(0.16 0.03 230 / 0.72), transparent 42%);
	}
	.art-copy {
		position: absolute;
		z-index: 1;
		inset-inline: 2.6rem;
		bottom: 2.4rem;
		color: oklch(0.97 0.005 90);
	}
	.art-copy h2 {
		font-size: clamp(1.35rem, 1.9vw, 1.8rem);
		font-weight: 450;
		letter-spacing: -0.01em;
		line-height: 1.3;
		text-wrap: balance;
		max-width: 24rem;
	}
	.art-copy h2 em {
		font-style: normal;
		color: #00a5ba;
	}
	.art-copy p {
		margin-top: 0.6rem;
		font-size: 0.82rem;
		line-height: 1.6;
		color: oklch(0.97 0.005 90 / 0.72);
		max-width: 26rem;
	}
	.art-chips {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 1.2rem;
	}
	.art-chips span {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.68rem;
		font-weight: 500;
		color: oklch(0.97 0.005 90 / 0.9);
		background: oklch(1 0 0 / 0.1);
		border: 1px solid oklch(1 0 0 / 0.16);
		backdrop-filter: blur(6px);
		border-radius: 999px;
		padding: 0.32rem 0.75rem;
	}
	.art-chips span i {
		width: 0.4rem;
		height: 0.4rem;
		border-radius: 999px;
		flex: none;
		background: oklch(0.75 0.11 130);
		animation: blip 2.4s ease-in-out infinite;
	}
	.art-chips span.soon i {
		background: oklch(0.8 0.1 78);
	}
	/* prev/next arrows — appear on hover over the art pane */
	.art-nav {
		position: absolute;
		z-index: 2;
		top: 50%;
		transform: translateY(-50%);
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 999px;
		display: grid;
		place-items: center;
		background: oklch(1 0 0 / 0.12);
		border: 1px solid oklch(1 0 0 / 0.2);
		backdrop-filter: blur(10px);
		color: oklch(0.97 0.005 90);
		cursor: pointer;
		opacity: 0;
		transition:
			opacity 0.2s,
			background 0.15s;
	}
	.art-nav.prev {
		inset-inline-start: 1.2rem;
	}
	.art-nav.next {
		inset-inline-end: 1.2rem;
	}
	.art-pane:hover .art-nav,
	.art-nav:focus-visible {
		opacity: 1;
	}
	.art-nav:hover {
		background: oklch(1 0 0 / 0.24);
	}
	.art-nav .icon {
		width: 1.1rem;
		height: 1.1rem;
	}

	/* floating status card over the art */
	.art-float {
		position: absolute;
		z-index: 1;
		top: 2.2rem;
		inset-inline-end: 2.2rem;
		display: flex;
		align-items: center;
		gap: 0.55rem;
		background: oklch(1 0 0 / 0.1);
		border: 1px solid oklch(1 0 0 / 0.18);
		backdrop-filter: blur(10px);
		border-radius: 0.85rem;
		padding: 0.55rem 0.85rem;
		color: oklch(0.97 0.005 90);
		font-size: 0.7rem;
		animation: floaty 9s ease-in-out infinite;
	}
	.art-float .mini {
		width: 1.6rem;
		height: 1.6rem;
		border-radius: 0.5rem;
		flex: none;
		background: oklch(1 0 0 / 0.14);
		display: grid;
		place-items: center;
	}
	.art-float .mini .icon {
		width: 0.85rem;
		height: 0.85rem;
	}
	.art-float b {
		display: block;
		font-size: 0.7rem;
		font-weight: 600;
	}
	.art-float small {
		font-size: 0.6rem;
		color: oklch(0.97 0.005 90 / 0.65);
	}

	@media (max-width: 1020px) {
		.split {
			grid-template-columns: 1fr;
			width: min(100% - 1.2rem, 30rem);
			min-height: 0;
			margin: 0.6rem 0;
		}
		.pane.art-pane {
			display: none;
		}
		.pane.form-pane {
			padding: 1.6rem 1.4rem;
		}
	}
</style>
