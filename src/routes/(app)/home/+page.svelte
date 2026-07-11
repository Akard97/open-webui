<script lang="ts">
	import { onMount, onDestroy, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { user } from '$lib/stores';

	import osoolMark from '$lib/assets/favicon.png';
	import osoolMarkDark from '$lib/assets/favicon-dark.png';
	import osoolAiLogoBlack from '$lib/assets/osool-ai-logo-black-transparent.png';
	import osoolAiLogoWhite from '$lib/assets/osool-ai-logo-whitish-transparent.png';
	import workosLogoDark from '$lib/components/workos/assets/workos-logo-dark.png';
	import workosLogoLight from '$lib/components/workos/assets/workos-logo-light.png';

	import { greetingForHour, daymarkForHour, wishForHour } from './greeting';

	const i18n = getContext<any>('i18n');

	// Computed once on load, like the mockup.
	const now = new Date();
	const h = now.getHours();
	const daymark = daymarkForHour(h);

	$: weekday = now.toLocaleDateString($i18n.language, { weekday: 'long' });
	$: dateText = now.toLocaleDateString($i18n.language, {
		weekday: 'long',
		month: 'long',
		day: 'numeric'
	});

	$: greetingText = {
		morning: $i18n.t('Good morning'),
		afternoon: $i18n.t('Good afternoon'),
		evening: $i18n.t('Good evening')
	}[greetingForHour(h)];

	$: wishText = {
		bright: $i18n.t('have a bright {{weekday}}', { weekday }),
		rest: $i18n.t('enjoy the rest of your {{weekday}}', { weekday }),
		calm: $i18n.t('have a calm evening')
	}[wishForHour(h)];

	$: firstName = ($user?.name ?? '').trim().split(/\s+/)[0] ?? '';

	const notifyMe = () => {
		toast.success($i18n.t("We'll let you know when it's ready."));
	};

	let pageEl: HTMLElement;
	let io: IntersectionObserver | undefined;

	onMount(() => {
		io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (e.isIntersecting) {
						e.target.classList.add('in');
						io?.unobserve(e.target);
					}
				}
			},
			{ threshold: 0.12 }
		);
		pageEl.querySelectorAll('.reveal').forEach((el) => io?.observe(el));
	});

	onDestroy(() => {
		io?.disconnect();
	});
</script>

<div class="home-root" bind:this={pageEl}>
	<svg width="0" height="0" style="position:absolute">
		<defs>
			<!-- warm underline gradient: amber melting into brand teal -->
			<linearGradient id="warmline" x1="0" y1="0" x2="1" y2="0">
				<stop offset="0" stop-color="#e0a13f" />
				<stop offset="1" stop-color="#3d94a8" />
			</linearGradient>
		</defs>
		<symbol id="i-home" viewBox="0 0 24 24"><path d="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"/></symbol>
		<symbol id="i-sparkles" viewBox="0 0 24 24"><path d="M9.813 15.904 9.5 16.938l-.313-1.034a3.75 3.75 0 0 0-2.466-2.466L5.687 13.5l1.034-.313a3.75 3.75 0 0 0 2.466-2.466L9.5 9.688l.313 1.034a3.75 3.75 0 0 0 2.466 2.466l1.034.312-1.034.313a3.75 3.75 0 0 0-2.466 2.466ZM18.259 8.715 18 9.75l-.259-1.035a2.625 2.625 0 0 0-1.956-1.956L14.75 6.5l1.035-.259a2.625 2.625 0 0 0 1.956-1.956L18 3.25l.259 1.035a2.625 2.625 0 0 0 1.956 1.956l1.035.259-1.035.259a2.625 2.625 0 0 0-1.956 1.956ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"/></symbol>
		<symbol id="i-clipboard" viewBox="0 0 24 24"><path d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z"/></symbol>
		<symbol id="i-note" viewBox="0 0 24 24"><path d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"/></symbol>
		<symbol id="i-cube" viewBox="0 0 24 24"><path d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"/></symbol>
		<symbol id="i-doccheck" viewBox="0 0 24 24"><path d="M10.125 2.25h-4.5c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125v-9M10.125 2.25h.375a9 9 0 0 1 9 9v.375M10.125 2.25A3.375 3.375 0 0 1 13.5 5.625v1.5c0 .621.504 1.125 1.125 1.125h1.5a3.375 3.375 0 0 1 3.375 3.375M9 15l2.25 2.25L15 12"/></symbol>
		<symbol id="i-users" viewBox="0 0 24 24"><path d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z"/></symbol>
		<symbol id="i-arrow" viewBox="0 0 24 24"><path d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"/></symbol>
		<symbol id="i-check" viewBox="0 0 24 24"><path d="m4.5 12.75 6 6 9-13.5"/></symbol>
		<symbol id="i-book" viewBox="0 0 24 24"><path d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"/></symbol>
		<symbol id="i-present" viewBox="0 0 24 24"><path d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.25m0 0-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6"/></symbol>
		<symbol id="i-chart" viewBox="0 0 24 24"><path d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"/></symbol>
		<symbol id="i-bell" viewBox="0 0 24 24"><path d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"/></symbol>
		<symbol id="i-at" viewBox="0 0 24 24"><path d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z"/></symbol>
		<symbol id="i-search" viewBox="0 0 24 24"><path d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"/></symbol>
		<symbol id="i-sun" viewBox="0 0 24 24"><path d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z"/></symbol>
		<symbol id="i-moon" viewBox="0 0 24 24"><path d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"/></symbol>
	</svg>

	<div class="wrap">
		<div class="frame">
			<!-- ================= HERO ================= -->
			<section class="hero">
				<div class="lines" aria-hidden="true">
					<i class="h" style="top:16%"></i>
					<i class="h" style="top:78%"></i>
					<i class="v" style="left:8%"></i>
					<i class="v" style="left:52%"></i>
					<i class="v" style="left:92%"></i>
					<s style="left:8%; top:16%"></s>
					<s style="left:52%; top:16%"></s>
					<s style="left:92%; top:78%"></s>
					<s style="left:8%; top:78%"></s>
				</div>

				<div class="container hero-inner">
					<div class="hero-copy">
						<span class="eyebrow"
							><svg class="icon"><use href={daymark === 'moon' ? '#i-moon' : '#i-sun'} /></svg><span
								>{dateText}</span
							></span
						>
						<h1>
							{greetingText}{#if firstName},
								<span class="name"
									>{firstName}<svg
										class="uline"
										viewBox="0 0 120 12"
										preserveAspectRatio="none"
										aria-hidden="true"
										><path d="M3 9 C 28 3.5, 62 3, 117 6.5" pathLength="100" /></svg
									></span
								>{/if}
						</h1>
						<p class="sub">{$i18n.t("Everything you need is right here — let's make today count.")}</p>
					</div>

					<div class="viz" aria-hidden="true">
						<svg class="wires" viewBox="0 0 500 424" preserveAspectRatio="none">
							<path d="M 92 74 C 150 100, 190 130, 230 160" />
							<path d="M 400 60 C 355 95, 320 125, 285 158" />
							<path d="M 442 200 C 395 195, 350 190, 300 186" />
							<path d="M 70 240 C 130 220, 175 205, 215 195" />
							<path d="M 250 210 C 260 260, 275 300, 300 340" />
							<path d="M 160 350 C 190 320, 210 290, 228 250" />
							<circle class="dot" cx="92" cy="74" r="3" />
							<circle class="dot" cx="400" cy="60" r="3" />
							<circle class="dot" cx="442" cy="200" r="3" />
							<circle class="dot" cx="70" cy="240" r="3" />
							<circle class="dot" cx="300" cy="340" r="3" />
							<circle class="dot" cx="160" cy="350" r="3" />
						</svg>

						<div class="core">
							<img class="light-only" src={osoolMark} alt={$i18n.t('Osool Intelligence Hub')} />
							<img class="dark-only" src={osoolMarkDark} alt={$i18n.t('Osool Intelligence Hub')} />
						</div>

						<div class="sat" style="left:10%; top:4%">
							<div class="tile">
								<img class="light-only" src={osoolAiLogoBlack} alt="" />
								<img class="dark-only" src={osoolAiLogoWhite} alt="" />
							</div>
							<span class="lbl">{$i18n.t('Osool AI')}</span>
						</div>
						<div class="sat" style="left:72%; top:2%">
							<div class="tile">
								<img class="light-only" src={workosLogoDark} alt="" />
								<img class="dark-only" src={workosLogoLight} alt="" />
							</div>
							<span class="lbl">{$i18n.t('WorkOS')}</span>
						</div>
						<div class="sat" style="left:84%; top:40%">
							<div class="tile"><svg class="icon"><use href="#i-book" /></svg></div>
							<span class="lbl">{$i18n.t('Knowledge')}</span>
						</div>
						<div class="sat" style="left:4%; top:48%">
							<div class="tile"><svg class="icon"><use href="#i-bell" /></svg></div>
							<span class="lbl">{$i18n.t('Notifications')}</span>
						</div>
						<div class="sat" style="left:54%; top:74%">
							<div class="tile"><svg class="icon"><use href="#i-doccheck" /></svg></div>
							<span class="lbl">{$i18n.t('Policies')}</span>
						</div>

						<div
							class="pav"
							style="left:38%; top:6%; background:linear-gradient(135deg,#f3c98b,#d98352); animation-delay:-2s"
						></div>
						<div
							class="pav"
							style="left:92%; top:18%; background:linear-gradient(135deg,#a9c6f5,#5a7dc4); animation-delay:-5s"
						></div>
						<div
							class="pav"
							style="left:18%; top:76%; background:linear-gradient(135deg,#b8e0c8,#5f9c78); animation-delay:-7.5s"
						></div>

						<span class="tinychip amber" style="left:30%; top:26%; animation-delay:-3s"
							>{$i18n.t('Due Sun')}</span
						>
						<span class="tinychip teal" style="left:62%; top:56%; animation-delay:-6s"
							>{$i18n.t('@ahmed')}</span
						>
						<span class="tinychip" style="left:8%; top:30%; animation-delay:-9s">HR-POL-014</span>
					</div>
				</div>
			</section>

			<!-- ================= TOOLS : live + coming soon ================= -->
			<section class="feature">
				<div class="container">
					<div class="tools">
						<!-- Osool AI (live) -->
						<div class="tool-col reveal">
							<div class="tool-head">
								<img
									class="brandmark ai-mark light-only"
									src={osoolAiLogoBlack}
									alt="Osool AI"
								/>
								<img
									class="brandmark ai-mark dark-only"
									src={osoolAiLogoWhite}
									alt="Osool AI"
								/>
								<span class="t"><b>{$i18n.t('Osool AI')}</b></span>
								<a class="go" href="/">{$i18n.t('Open')} <svg class="icon"><use href="#i-arrow" /></svg></a>
							</div>

							<div class="showcase">
								<div class="appcard">
									<div class="apphead">
										<span class="ai logo">
											<img class="light-only" src={osoolAiLogoBlack} alt="" />
											<img class="dark-only" src={osoolAiLogoWhite} alt="" />
										</span>
										<span
											><b>{$i18n.t('Osool AI')}</b><small
												>{$i18n.t('Connected to company knowledge')}</small
											></span
										>
										<span class="live"><i></i> {$i18n.t('Online')}</span>
									</div>
									<div class="chat">
										<div class="msg q">{$i18n.t("What's our remote work policy?")}</div>
										<div class="msg a">
											{$i18n.t('Remote work is allowed up to')}
											<b>{$i18n.t('3 days per week')}</b>
											{$i18n.t('with manager approval…')}
											<div class="srcs">
												<span class="src"
													><svg class="icon" style="width:.62rem;height:.62rem"
														><use href="#i-doccheck" /></svg
													> HR-POL-014</span
												>
												<span class="src"
													><svg class="icon" style="width:.62rem;height:.62rem"
														><use href="#i-book" /></svg
													> {$i18n.t('Handbook §4')}</span
												>
											</div>
										</div>
										<div class="inbar">
											<span>{$i18n.t('Ask anything…')}</span>
											<button type="button" class="snd" tabindex="-1" aria-label={$i18n.t('Send')}
												><svg class="icon"><use href="#i-arrow" /></svg></button
											>
										</div>
									</div>
								</div>

								<div class="float-chip" style="bottom:-0.9rem; inset-inline-end:0.7rem">
									<span class="mini" style="background:var(--tint); color:var(--accent)"
										><svg class="icon" style="width:.8rem;height:.8rem"><use href="#i-book" /></svg></span
									>
									<span
										><b>{$i18n.t('2 sources cited')}</b><small
											>{$i18n.t('From your knowledge base')}</small
										></span
									>
								</div>
							</div>
						</div>

						<!-- WorkOS (live) -->
						<div class="tool-col reveal">
							<div class="tool-head">
								<img class="brandmark light-only" src={workosLogoDark} alt="WorkOS" />
								<img class="brandmark dark-only" src={workosLogoLight} alt="WorkOS" />
								<span class="t"><b>{$i18n.t('WorkOS')}</b></span>
								<a class="go" href="/workos">{$i18n.t('Open')} <svg class="icon"><use href="#i-arrow" /></svg></a>
							</div>

							<div class="showcase warmglow">
								<div class="appcard">
									<div class="apphead">
										<span class="ai"><svg class="icon"><use href="#i-clipboard" /></svg></span>
										<span
											><b>{$i18n.t('Marketing Q3')}</b><small
												>{$i18n.t('Board • 3 workstreams')}</small
											></span
										>
										<span class="live"><i></i> {$i18n.t('4 online')}</span>
									</div>
									<div class="kb">
										<div class="col">
											<div class="colh">
												<i style="background:oklch(0.69 0 0)"></i> {$i18n.t('To do')}
												<span class="n">3</span>
											</div>
											<div class="tk">
												<b>{$i18n.t('Vendor contract renewal')}</b>
												<div class="row">
													<span
														class="pl"
														style="background:oklch(0.9 0.06 60);color:oklch(0.45 0.1 60)"
														>{$i18n.t('Medium')}</span
													><span
														class="av"
														style="background:linear-gradient(135deg,#f3c98b,#d98352)"
													></span>
												</div>
											</div>
											<div class="tk">
												<b>{$i18n.t('Onboarding checklist v2')}</b>
												<div class="row">
													<span class="pl" style="background:var(--hairline);color:var(--faint)"
														>{$i18n.t('Low')}</span
													><span
														class="av"
														style="background:linear-gradient(135deg,#a9c6f5,#5a7dc4)"
													></span>
												</div>
											</div>
										</div>
										<div class="col">
											<div class="colh">
												<i style="background:var(--mid)"></i> {$i18n.t('Doing')}
												<span class="n">2</span>
											</div>
											<div class="tk lift">
												<b>{$i18n.t('Q3 policy audit')}</b>
												<div class="row">
													<span
														class="pl"
														style="background:oklch(0.9 0.09 30);color:oklch(0.5 0.15 30)"
														>{$i18n.t('High')}</span
													><span
														class="av"
														style="background:linear-gradient(135deg,#b8e0c8,#5f9c78)"
													></span>
												</div>
												<div class="prog"><i style="width:65%"></i></div>
											</div>
											<div class="slot"></div>
										</div>
									</div>
								</div>

								<div class="float-chip" style="top:-0.9rem; inset-inline-end:0.7rem">
									<span class="mini" style="background:var(--sun-tint); color:var(--sun-ink)"
										><svg class="icon" style="width:.8rem;height:.8rem"><use href="#i-at" /></svg></span
									>
									<span
										><b>{$i18n.t('Sarah mentioned you')}</b><small
											>{$i18n.t('"@ahmed can you review this?"')}</small
										></span
									>
								</div>
							</div>
						</div>

						<!-- Coming soon (blueprint stack) -->
						<div class="tool-col soon-col reveal">
							<div class="tool-head">
								<span class="soon-title"><i></i> {$i18n.t('Coming soon')}</span>
								<span class="head-note"
									><svg class="icon"><use href="#i-chart" /></svg> {$i18n.t('+ Intelligence Survey')}</span
								>
							</div>

							<div class="soon-stack">
								<!-- Presentation Maker (warm — still in design) -->
								<div class="sooncard warm">
									<div class="soon-top">
										<span class="si"><svg class="icon"><use href="#i-present" /></svg></span>
										<span class="t"
											><b>{$i18n.t('Presentation Maker')}</b><small
												>{$i18n.t('On-brand decks by AI')}</small
											></span
										>
										<span class="s"><i></i>{$i18n.t('Soon')}</span>
									</div>
									<div class="ghost" aria-hidden="true">
										<span class="sk" style="width:55%; height:0.5rem"></span>
										<div class="gstrip">
											<span class="sk box lead"></span>
											<span class="sk box" style="animation-delay:-0.7s"></span>
											<span class="sk box" style="animation-delay:-1.4s"></span>
										</div>
									</div>
									<div class="soon-foot">
										<span class="buildbar"><i style="width:40%"></i></span>
										<span class="bt">{$i18n.t('In design')}</span>
										<button type="button" class="notify" on:click={notifyMe}
											><svg class="icon"><use href="#i-bell" /></svg> {$i18n.t('Notify me')}</button
										>
									</div>
								</div>

								<!-- Policies Library -->
								<div class="sooncard">
									<div class="soon-top">
										<span class="si"><svg class="icon"><use href="#i-book" /></svg></span>
										<span class="t"
											><b>{$i18n.t('Policies Library')}</b><small
												>{$i18n.t('Search & acknowledge')}</small
											></span
										>
										<span class="s"><i></i>{$i18n.t('Soon')}</span>
									</div>
									<div class="ghost" aria-hidden="true">
										<div class="grow">
											<span class="gi"><svg class="icon"><use href="#i-search" /></svg></span>
											<span class="sk" style="flex:1; height:0.5rem"></span>
										</div>
										<div class="grow">
											<span class="gi"><svg class="icon"><use href="#i-doccheck" /></svg></span>
											<span class="gl"
												><span class="sk" style="width:72%"></span><span
													class="sk"
													style="width:45%; animation-delay:-0.6s"
												></span></span
											>
										</div>
									</div>
									<div class="soon-foot">
										<span class="buildbar"><i style="width:70%"></i></span>
										<span class="bt">{$i18n.t('In development')}</span>
										<button type="button" class="notify" on:click={notifyMe}
											><svg class="icon"><use href="#i-bell" /></svg> {$i18n.t('Notify me')}</button
										>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</section>

			<footer>
				{$i18n.t('Osool Intelligence Hub — internal platform')} ·
				<span class="wish">{wishText}</span>
			</footer>
		</div>
	</div>
</div>

<style>
	.home-root {
		/* ramps come from src/tailwind.css */
		--gray-50: var(--color-gray-50);
		--gray-100: var(--color-gray-100);
		--gray-200: var(--color-gray-200);
		--gray-300: var(--color-gray-300);
		--gray-400: var(--color-gray-400);
		--gray-500: var(--color-gray-500);
		--gray-600: var(--color-gray-600);
		--gray-700: var(--color-gray-700);
		--gray-800: var(--color-gray-800);
		--gray-850: var(--color-gray-850);
		--gray-900: var(--color-gray-900);
		--gray-950: var(--color-gray-950);

		--brand-100: var(--color-brand-100);
		--brand-200: var(--color-brand-200);
		--brand-300: var(--color-brand-300);
		--brand-400: var(--color-brand-400);
		--brand-500: var(--color-brand-500);
		--brand-600: var(--color-brand-600);
		--brand-700: var(--color-brand-700);
		--brand-900: var(--color-brand-900);
		--success: var(--color-success);

		/* v6 — warm layer (sand / amber, sits beside the teal, never replaces it) */
		--sun-300: oklch(0.87 0.07 78);
		--sun-500: oklch(0.75 0.125 70);
		--sun-700: oklch(0.58 0.115 62);
		--sun-tint: oklch(0.945 0.045 82);
		--sun-ink: oklch(0.52 0.115 62);
		--sunwash: oklch(0.9 0.07 80 / 0.26);

		--backdrop: var(--gray-50);
		--frame: #ffffff;
		--card: #ffffff;
		--card-2: var(--gray-50);
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
		--tint: var(--brand-100);
		--cta: #00313f;
		--cta-fg: #fff;
		--shadow-s: 0 1px 2px oklch(0 0 0 / 0.04), 0 3px 10px oklch(0 0 0 / 0.04);
		--shadow-m: 0 1px 3px oklch(0 0 0 / 0.05), 0 8px 24px oklch(0 0 0 / 0.06);

		/* layout (replaces the mockup's body responsibilities) */
		min-height: 100%;
		background: var(--backdrop);
		color: var(--ink);
		font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Vazirmatn', ui-sans-serif, system-ui,
			'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif;
		-webkit-font-smoothing: antialiased;
		text-rendering: optimizeLegibility;
	}
	:global(.dark) .home-root {
		--sun-tint: oklch(0.31 0.055 70);
		--sun-ink: oklch(0.82 0.1 78);
		--sunwash: oklch(0.5 0.09 70 / 0.14);

		--backdrop: var(--gray-950);
		--frame: var(--gray-900);
		--card: var(--gray-850);
		--card-2: oklch(0.23 0 0);
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
		--tint: oklch(0.3 0.05 221.22);
		--cta: var(--brand-600);
		--cta-fg: #fff;
		--shadow-s: 0 1px 2px oklch(0 0 0 / 0.3), 0 3px 10px oklch(0 0 0 / 0.25);
		--shadow-m: 0 1px 3px oklch(0 0 0 / 0.35), 0 8px 24px oklch(0 0 0 / 0.35);
	}

	/* .font-primary in the app (only h1 is present on this page) */
	h1 {
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

	a:focus-visible,
	button:focus-visible {
		outline: 2px solid var(--mid);
		outline-offset: 2px;
		border-radius: 0.6rem;
	}

	/* light/dark asset swap */
	:global(html:not(.dark)) .dark-only {
		display: none !important;
	}
	:global(.dark) .light-only {
		display: none !important;
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
	@keyframes floatyCore {
		0%,
		100% {
			transform: translate(-50%, -50%);
		}
		50% {
			transform: translate(-50%, -50%) translateY(-5px);
		}
	}
	@keyframes dashmove {
		to {
			stroke-dashoffset: -60;
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
	@keyframes shimmer {
		to {
			background-position: -200% 0;
		}
	}
	@keyframes stripes {
		to {
			background-position: 1.2rem 0;
		}
	}
	@keyframes draw {
		to {
			stroke-dashoffset: 0;
		}
	}
	.reveal {
		opacity: 0;
		transform: translateY(14px);
		transition: opacity 0.6s cubic-bezier(0.22, 0.7, 0.3, 1),
			transform 0.6s cubic-bezier(0.22, 0.7, 0.3, 1);
	}
	.reveal:global(.in) {
		opacity: 1;
		transform: none;
	}
	.tool-col.reveal:nth-child(2) {
		transition-delay: 0.08s;
	}
	.tool-col.reveal:nth-child(3) {
		transition-delay: 0.16s;
	}
	@media (prefers-reduced-motion: reduce) {
		*,
		::before,
		::after {
			animation: none !important;
			transition: none !important;
		}
		.reveal {
			opacity: 1;
			transform: none;
		}
		.uline path {
			stroke-dashoffset: 0 !important;
		}
	}

	/* ---------- framed page canvas ---------- */
	.wrap {
		padding: 0.9rem;
	}
	.frame {
		background: var(--frame);
		border: 1px solid var(--border);
		border-radius: 1.25rem;
		box-shadow: var(--shadow-s);
		overflow: hidden;
		min-height: calc(100vh - 1.8rem);
	}
	.container {
		max-width: 70rem;
		margin: 0 auto;
		padding: 0 3rem;
	}

	/* ---------- hero ---------- */
	.hero {
		position: relative;
		border-bottom: 1px solid var(--hairline);
		overflow: hidden;
	}
	.hero .lines {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}
	.hero .lines i {
		position: absolute;
		background: var(--gridline);
	}
	.hero .lines i.h {
		left: 0;
		right: 0;
		height: 1px;
	}
	.hero .lines i.v {
		top: 0;
		bottom: 0;
		width: 1px;
	}
	.hero .lines s {
		position: absolute;
		width: 7px;
		height: 7px;
		border-radius: 2px;
		background: var(--frame);
		border: 1.5px solid var(--node);
		transform: translate(-50%, -50%) rotate(45deg);
	}
	/* dawn wash — teal from the top right, sun from the top left */
	.hero::after {
		content: '';
		position: absolute;
		inset: 0;
		pointer-events: none;
		background: radial-gradient(42rem 24rem at 88% 0%, var(--wash), transparent 62%),
			radial-gradient(34rem 22rem at 4% -8%, var(--sunwash), transparent 70%),
			radial-gradient(26rem 18rem at 0% 100%, var(--wash), transparent 68%);
	}
	.hero-inner {
		position: relative;
		z-index: 1;
		display: grid;
		grid-template-columns: 1.02fr 0.98fr;
		gap: 2.5rem;
		align-items: center;
		padding: 3.6rem 0 3.4rem;
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
	/* .eyebrow::before { content: ''; width: 1.6rem; height: 1px; background: var(--faint); opacity: 0.6; border-radius: 999px; } */
	.eyebrow .icon {
		width: 0.85rem;
		height: 0.85rem;
		color: var(--sun-ink);
	}
	/* Greeting — same voice as the in-app greeting (ChatPlaceholder: text-3xl, font-primary, gray-800) */
	.hero h1 {
		margin-top: 1rem;
		text-wrap: balance;
		font-size: clamp(2rem, 3vw, 2.6rem);
		font-weight: 400;
		letter-spacing: -0.01em;
		line-height: 1.2;
		color: var(--ink);
	}
	.hero h1 .name {
		color: var(--accent);
		position: relative;
		display: inline-block;
	}
	/* hand-drawn warm underline, draws itself in */
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
		stroke: url(#warmline);
		stroke-width: 3.2;
		stroke-linecap: round;
		stroke-dasharray: 100;
		stroke-dashoffset: 100;
		animation: draw 0.8s 0.55s cubic-bezier(0.6, 0, 0.3, 1) forwards;
	}
	.hero .sub {
		margin-top: 0.7rem;
		font-size: 0.95rem;
		color: var(--muted);
		max-width: 28rem;
		line-height: 1.6;
	}

	.hero-copy > * {
		animation: fadeUp 0.6s cubic-bezier(0.22, 0.7, 0.3, 1) both;
	}
	.hero-copy > *:nth-child(2) {
		animation-delay: 0.08s;
	}
	.hero-copy > *:nth-child(3) {
		animation-delay: 0.14s;
	}
	.hero-copy > *:nth-child(4) {
		animation-delay: 0.2s;
	}
	.hero-copy > *:nth-child(5) {
		animation-delay: 0.28s;
	}

	/* ---------- hero visual : app constellation ---------- */
	.viz {
		position: relative;
		height: 26rem;
		animation: fadeUp 0.75s 0.2s cubic-bezier(0.22, 0.7, 0.3, 1) both;
	}
	/* soft sun behind the constellation */
	.viz::before {
		content: '';
		position: absolute;
		width: 17rem;
		height: 17rem;
		left: -4.5rem;
		top: -5.5rem;
		background: radial-gradient(closest-side, var(--sunwash), transparent 72%);
		pointer-events: none;
	}
	.viz svg.wires {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}
	.viz svg.wires path {
		fill: none;
		stroke: var(--gray-400);
		stroke-opacity: 0.5;
		stroke-width: 1.2;
		stroke-dasharray: 2.5 5;
		animation: dashmove 14s linear infinite;
	}
	:global(.dark) .viz svg.wires path {
		stroke: var(--gray-600);
	}
	.viz svg.wires circle.dot {
		fill: var(--faint);
	}
	.core {
		position: absolute;
		left: 47%;
		top: 44%;
		transform: translate(-50%, -50%);
		width: 7rem;
		height: 7rem;
		border-radius: 1.5rem;
		background: var(--card);
		border: 1px solid var(--border);
		box-shadow: var(--shadow-m);
		display: grid;
		place-items: center;
		z-index: 3;
		animation: floatyCore 8s ease-in-out infinite;
	}
	.core::before {
		content: '';
		position: absolute;
		inset: -0.6rem;
		border-radius: 1.9rem;
		border: 1px solid var(--border);
		opacity: 0.7;
	}
	.core img {
		width: 3.4rem;
		height: 3.4rem;
		object-fit: contain;
	}
	.sat {
		position: absolute;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		z-index: 2;
		animation: floaty 7s ease-in-out infinite;
	}
	.viz > .sat:nth-of-type(1) {
		animation-delay: -1s;
	}
	.viz > .sat:nth-of-type(2) {
		animation-delay: -2.5s;
	}
	.viz > .sat:nth-of-type(3) {
		animation-delay: -4s;
	}
	.viz > .sat:nth-of-type(4) {
		animation-delay: -5.5s;
	}
	.viz > .sat:nth-of-type(5) {
		animation-delay: -6.5s;
	}
	.sat .tile {
		width: 3.4rem;
		height: 3.4rem;
		border-radius: 0.9rem;
		background: var(--card);
		border: 1px solid var(--border);
		box-shadow: var(--shadow-s);
		display: grid;
		place-items: center;
		color: var(--mid);
	}
	.sat .tile .icon {
		width: 1.25rem;
		height: 1.25rem;
	}
	.sat .tile img {
		width: 2rem;
		height: 2rem;
		object-fit: contain;
	}
	.sat .lbl {
		font-size: 0.7rem;
		font-weight: 500;
		color: var(--muted);
	}
	.pav {
		position: absolute;
		width: 2rem;
		height: 2rem;
		border-radius: 999px;
		border: 2.5px solid var(--frame);
		box-shadow: var(--shadow-s);
		z-index: 2;
		animation: floaty 9s ease-in-out infinite;
	}
	.tinychip {
		position: absolute;
		z-index: 2;
		font-size: 0.62rem;
		font-weight: 500;
		color: var(--muted);
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 0.24rem 0.6rem;
		box-shadow: var(--shadow-s);
		animation: floaty 11s ease-in-out infinite;
	}
	.tinychip.teal {
		color: var(--accent);
		background: var(--tint);
		border-color: transparent;
	}
	.tinychip.amber {
		color: var(--sun-ink);
		background: var(--sun-tint);
		border-color: transparent;
	}

	/* ---------- tools row : 2 live + 2 coming soon ---------- */
	.feature {
		padding: 2.6rem 0 3.2rem;
	}
	.tools {
		display: grid;
		grid-template-columns: 1.08fr 1.08fr 0.84fr;
		gap: 3.5rem;
		align-items: stretch;
	}
	.tool-col {
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.tool-head {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin-bottom: 0.85rem;
		min-height: 2.1rem;
	}
	.tool-head .brandmark {
		height: 1.55rem;
		width: auto;
		display: block;
	}
	.tool-head .brandmark.ai-mark {
		height: 1.75rem;
	}
	.tool-head .t b {
		display: block;
		font-family: 'Archivo', 'Vazirmatn', sans-serif;
		font-size: 0.95rem;
		font-weight: 550;
		letter-spacing: -0.005em;
	}
	.tool-head .go {
		margin-inline-start: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.76rem;
		font-weight: 500;
		color: var(--muted);
		text-decoration: none;
		white-space: nowrap;
		border: 1px solid var(--border);
		background: var(--card);
		border-radius: 999px;
		padding: 0.32rem 0.8rem;
		transition: 0.15s;
	}
	.tool-head .go .icon {
		width: 0.8rem;
		height: 0.8rem;
		transition: transform 0.15s;
	}
	.tool-head .go:hover {
		background: var(--hover);
		color: var(--ink);
	}
	.tool-head .go:hover .icon {
		transform: translateX(3px);
	}
	.tool-head .soon-title {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-family: 'Archivo', 'Vazirmatn', sans-serif;
		font-size: 0.95rem;
		font-weight: 550;
		letter-spacing: -0.005em;
	}
	.tool-head .soon-title i {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 999px;
		flex: none;
		background: var(--mid);
		animation: blip 2.4s ease-in-out infinite;
	}
	.tool-head .head-note {
		margin-inline-start: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.64rem;
		font-weight: 500;
		color: var(--faint);
		white-space: nowrap;
	}
	.tool-head .head-note .icon {
		width: 0.75rem;
		height: 0.75rem;
	}

	/* showcase cards */
	.showcase {
		position: relative;
		flex: 1;
		display: flex;
	}
	.showcase::before {
		content: '';
		position: absolute;
		inset: -1.6rem;
		background: radial-gradient(60% 60% at 50% 50%, var(--wash), transparent 75%);
		pointer-events: none;
		opacity: 0.85;
		transition: opacity 0.3s;
	}
	.showcase.warmglow::before {
		background: radial-gradient(55% 55% at 30% 60%, var(--wash), transparent 75%),
			radial-gradient(45% 45% at 78% 20%, var(--sunwash), transparent 75%);
	}
	.showcase:hover::before {
		opacity: 1;
	}
	.appcard {
		position: relative;
		flex: 1;
		display: flex;
		flex-direction: column;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 1.1rem;
		box-shadow: var(--shadow-s);
		overflow: hidden;
		transition: transform 0.25s ease, box-shadow 0.25s ease;
	}
	.showcase:hover .appcard {
		transform: translateY(-3px);
		box-shadow: var(--shadow-m);
	}
	.appcard .apphead {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.6rem 0.9rem;
		border-bottom: 1px solid var(--hairline);
	}
	.appcard .apphead .ai {
		width: 1.55rem;
		height: 1.55rem;
		border-radius: 0.45rem;
		flex: none;
		background: var(--card-2);
		border: 1px solid var(--hairline);
		color: var(--muted);
		display: grid;
		place-items: center;
		overflow: hidden;
	}
	.appcard .apphead .ai.logo {
		border-radius: 999px;
		background: var(--card);
	}
	.appcard .apphead .ai img {
		width: 100%;
		height: 100%;
		object-fit: contain;
		padding: 0.12rem;
	}
	.appcard .apphead .ai .icon {
		width: 0.85rem;
		height: 0.85rem;
	}
	.appcard .apphead b {
		font-size: 0.75rem;
		font-weight: 600;
	}
	.appcard .apphead small {
		font-size: 0.62rem;
		color: var(--faint);
		display: block;
		margin-top: 0.05rem;
	}
	.appcard .apphead .live {
		margin-inline-start: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.32rem;
		font-size: 0.6rem;
		font-weight: 600;
		color: var(--success);
	}
	.appcard .apphead .live i {
		width: 0.4rem;
		height: 0.4rem;
		border-radius: 999px;
		background: var(--success);
		animation: blip 2.4s ease-in-out infinite;
	}

	/* kanban visual (compact — 2 columns) */
	.kb {
		flex: 1;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.55rem;
		padding: 0.8rem;
		background: var(--card-2);
	}
	.kb .col {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
	}
	.kb .colh {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.57rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--faint);
		padding: 0.1rem 0.1rem;
	}
	.kb .colh i {
		width: 0.42rem;
		height: 0.42rem;
		border-radius: 999px;
		flex: none;
	}
	.kb .colh .n {
		margin-inline-start: auto;
		font-weight: 500;
		color: var(--faint);
		background: var(--card);
		border: 1px solid var(--hairline);
		border-radius: 999px;
		padding: 0.05rem 0.38rem;
	}
	.tk {
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 0.65rem;
		padding: 0.52rem 0.58rem;
	}
	.tk b {
		display: block;
		font-size: 0.66rem;
		font-weight: 600;
		line-height: 1.35;
	}
	.tk .row {
		margin-top: 0.45rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.tk .pl {
		font-size: 0.55rem;
		font-weight: 600;
		padding: 0.12rem 0.42rem;
		border-radius: 999px;
	}
	.tk .av {
		width: 1rem;
		height: 1rem;
		border-radius: 999px;
		border: 1.5px solid var(--card);
	}
	.tk .prog {
		margin-top: 0.45rem;
		height: 0.24rem;
		border-radius: 999px;
		background: var(--hairline);
		overflow: hidden;
	}
	.tk .prog i {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: var(--mid);
	}
	.tk.lift {
		box-shadow: var(--shadow-m);
		border-color: color-mix(in srgb, var(--mid) 45%, var(--border));
		transform: rotate(-2deg);
	}
	.kb .slot {
		border: 1.5px dashed color-mix(in srgb, var(--mid) 45%, transparent);
		border-radius: 0.65rem;
		background: color-mix(in srgb, var(--mid) 6%, transparent);
		height: 3.1rem;
		flex: none;
	}

	/* floating accessory chips on showcases */
	.float-chip {
		position: absolute;
		z-index: 2;
		display: flex;
		align-items: center;
		gap: 0.45rem;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 0.7rem;
		box-shadow: var(--shadow-m);
		padding: 0.45rem 0.7rem;
		font-size: 0.66rem;
		font-weight: 500;
		transition: transform 0.25s ease;
	}
	.showcase:hover .float-chip {
		transform: translateY(-2px) rotate(-1deg);
	}
	.float-chip .mini {
		width: 1.35rem;
		height: 1.35rem;
		border-radius: 0.45rem;
		display: grid;
		place-items: center;
		flex: none;
	}
	.float-chip b {
		font-size: 0.66rem;
		font-weight: 600;
		display: block;
	}
	.float-chip small {
		font-size: 0.58rem;
		color: var(--faint);
	}

	/* chat visual (compact) */
	.chat {
		flex: 1;
		padding: 0.9rem;
		background: var(--card-2);
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}
	.msg {
		max-width: 90%;
		border-radius: 0.85rem;
		padding: 0.58rem 0.75rem;
		font-size: 0.7rem;
		line-height: 1.55;
	}
	.msg.q {
		align-self: flex-end;
		background: var(--cta);
		color: var(--cta-fg);
		border-end-end-radius: 0.25rem;
	}
	.msg.a {
		align-self: flex-start;
		background: var(--card);
		border: 1px solid var(--border);
		color: var(--muted);
		border-end-start-radius: 0.25rem;
	}
	.msg.a b {
		color: var(--ink);
	}
	.msg .srcs {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
		margin-top: 0.45rem;
	}
	.msg .src {
		display: inline-flex;
		align-items: center;
		gap: 0.28rem;
		font-size: 0.58rem;
		font-weight: 600;
		color: var(--accent);
		background: var(--tint);
		padding: 0.2rem 0.5rem;
		border-radius: 999px;
	}
	.chat .inbar {
		margin-top: auto;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 0.48rem 0.55rem 0.48rem 0.9rem;
	}
	.chat .inbar span {
		flex: 1;
		font-size: 0.68rem;
		color: var(--placeholder);
	}
	.chat .inbar .snd {
		width: 1.6rem;
		height: 1.6rem;
		border-radius: 999px;
		border: none;
		background: var(--cta);
		color: var(--cta-fg);
		display: grid;
		place-items: center;
		cursor: pointer;
		transition: opacity 0.15s;
	}
	.chat .inbar .snd:hover {
		opacity: 0.9;
	}
	.chat .inbar .snd .icon {
		width: 0.78rem;
		height: 0.78rem;
	}

	/* ---------- coming soon : blueprint cards ---------- */
	.soon-stack {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}
	.sooncard {
		position: relative;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		padding: 0.7rem 0.8rem;
		border: 1.5px dashed color-mix(in srgb, var(--mid) 38%, var(--border));
		border-radius: 1.1rem;
		/* blueprint grid paper */
		background: linear-gradient(var(--gridline) 1px, transparent 1px),
			linear-gradient(90deg, var(--gridline) 1px, transparent 1px), var(--card);
		background-size: 16px 16px, 16px 16px, auto;
		transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease,
			background-color 0.25s ease;
	}
	.sooncard:hover {
		transform: translateY(-3px);
		box-shadow: var(--shadow-m);
		border-color: color-mix(in srgb, var(--mid) 70%, var(--border));
		border-style: solid;
	}
	.soon-top {
		display: flex;
		align-items: center;
		gap: 0.55rem;
	}
	.soon-top .si {
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 0.5rem;
		flex: none;
		background: var(--tint);
		color: var(--accent);
		display: grid;
		place-items: center;
	}
	.soon-top .si .icon {
		width: 0.9rem;
		height: 0.9rem;
	}
	.soon-top .t {
		min-width: 0;
	}
	.soon-top .t b {
		display: block;
		font-size: 0.78rem;
		font-weight: 600;
		line-height: 1.3;
	}
	.soon-top .t small {
		display: block;
		font-size: 0.62rem;
		color: var(--faint);
		margin-top: 0.1rem;
		line-height: 1.4;
	}
	.soon-top .s {
		margin-inline-start: auto;
		flex: none;
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.56rem;
		font-weight: 600;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--accent);
		background: var(--tint);
		border-radius: 999px;
		padding: 0.22rem 0.55rem;
	}
	.soon-top .s i {
		width: 0.36rem;
		height: 0.36rem;
		border-radius: 999px;
		background: var(--accent);
		animation: blip 2.4s ease-in-out infinite;
	}

	/* warm variant — the design-stage card runs on amber */
	.sooncard.warm {
		border-color: color-mix(in srgb, var(--sun-500) 42%, var(--border));
	}
	.sooncard.warm:hover {
		border-color: color-mix(in srgb, var(--sun-500) 72%, var(--border));
	}
	.sooncard.warm .si {
		background: var(--sun-tint);
		color: var(--sun-ink);
	}
	.sooncard.warm .s {
		background: var(--sun-tint);
		color: var(--sun-ink);
	}
	.sooncard.warm .s i {
		background: var(--sun-ink);
	}
	.sooncard.warm .gstrip .sk.box.lead {
		border-color: color-mix(in srgb, var(--sun-500) 50%, var(--border));
	}
	.sooncard.warm .buildbar i {
		background: repeating-linear-gradient(
			-55deg,
			var(--sun-500) 0 0.3rem,
			color-mix(in srgb, var(--sun-500) 55%, var(--card)) 0.3rem 0.6rem
		);
	}
	.sooncard.warm .notify {
		color: var(--sun-ink);
	}
	.sooncard.warm .notify:hover {
		background: var(--sun-tint);
	}

	/* ghost UI — shimmering skeleton preview of the future tool */
	.ghost {
		position: relative;
		border: 1px solid var(--hairline);
		border-radius: 0.6rem;
		background: color-mix(in srgb, var(--card-2) 60%, transparent);
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		overflow: hidden;
	}
	.sk {
		display: block;
		border-radius: 999px;
		height: 0.4rem;
		background: linear-gradient(
			90deg,
			var(--hairline) 25%,
			color-mix(in srgb, var(--mid) 14%, var(--hairline)) 37%,
			var(--hairline) 63%
		);
		background-size: 200% 100%;
		animation: shimmer 2.6s linear infinite;
	}
	.sooncard.warm .sk {
		background: linear-gradient(
			90deg,
			var(--hairline) 25%,
			color-mix(in srgb, var(--sun-500) 16%, var(--hairline)) 37%,
			var(--hairline) 63%
		);
		background-size: 200% 100%;
	}
	.sk.box {
		border-radius: 0.4rem;
		height: auto;
	}
	.grow {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.grow .gi {
		width: 1.15rem;
		height: 1.15rem;
		border-radius: 0.35rem;
		flex: none;
		border: 1px dashed color-mix(in srgb, var(--mid) 45%, var(--border));
		display: grid;
		place-items: center;
		color: color-mix(in srgb, var(--mid) 75%, var(--faint));
	}
	.grow .gi .icon {
		width: 0.62rem;
		height: 0.62rem;
	}
	.grow .gl {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		min-width: 0;
	}
	/* presentation ghost: filmstrip of slides */
	.gstrip {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.4rem;
	}
	.gstrip .sk.box {
		height: 1.35rem;
	}
	.gstrip .sk.box.lead {
		border: 1px dashed color-mix(in srgb, var(--mid) 45%, var(--border));
	}

	.soon-foot {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: auto;
	}
	.buildbar {
		width: 3.6rem;
		height: 0.32rem;
		border-radius: 999px;
		overflow: hidden;
		background: var(--hairline);
		flex: none;
	}
	.buildbar i {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: repeating-linear-gradient(
			-55deg,
			var(--mid) 0 0.3rem,
			color-mix(in srgb, var(--mid) 55%, var(--card)) 0.3rem 0.6rem
		);
		animation: stripes 1.2s linear infinite;
	}
	.soon-foot .bt {
		font-size: 0.6rem;
		font-weight: 500;
		color: var(--faint);
	}
	.notify {
		margin-inline-start: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.32rem;
		font-size: 0.64rem;
		font-weight: 600;
		color: var(--accent);
		text-decoration: none;
		padding: 0.28rem 0.6rem;
		border-radius: 999px;
		transition: 0.15s;
		background: transparent;
		border: none;
		cursor: pointer;
		font: inherit;
	}
	.notify .icon {
		width: 0.72rem;
		height: 0.72rem;
	}
	.notify:hover {
		background: var(--tint);
	}

	footer {
		padding: 0 0 2.2rem;
		color: var(--placeholder);
		font-size: 0.74rem;
		text-align: center;
	}
	footer .wish {
		color: var(--sun-ink);
	}

	@media (max-width: 1020px) {
		.container {
			padding: 0 1.4rem;
		}
		.wrap {
			padding: 0.6rem;
		}
		.tools {
			grid-template-columns: 1fr 1fr;
		}
		.tool-col.soon-col {
			grid-column: 1 / -1;
		}
		.soon-stack {
			flex-direction: row;
		}
	}
	@media (max-width: 760px) {
		.hero-inner {
			grid-template-columns: 1fr;
		}
		.viz {
			display: none;
		}
		.tools {
			grid-template-columns: 1fr;
		}
		.soon-stack {
			flex-direction: column;
		}
	}
</style>
