<script lang="ts">
	import '../app.css';
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Attribution from '#lib/components/Attribution.svelte';
	import { session, initAuth, signOut, initialAuthRedirectError } from '#lib/auth.js';
	import { browserStorage } from '#lib/browser-storage.js';
	import { pruneReturnTo, takeReturnTo } from '#lib/local-prefs.js';
	import { registerServiceWorker } from '#lib/sw-register.js';

	let { children }: { children: Snippet } = $props();
	let redirectError = $state<string | null>(null);
	let signingOut = $state(false);

	async function handleSignOut() {
		if (signingOut) return;
		signingOut = true;
		try {
			await signOut();
		} finally {
			signingOut = false;
		}
	}

	// Back to the /go link that was saved before logging in (A2). takeReturnTo always removes the key,
	// so a token refresh (a new session object) finds nothing and does nothing.
	$effect(() => {
		if (!$session) return;
		const path = takeReturnTo(browserStorage(), Date.now());
		if (path !== null) void goto(path, { replace: true });
	});

	onMount(() => {
		pruneReturnTo(browserStorage(), Date.now());
		redirectError = initialAuthRedirectError();
		const stop = initAuth();
		void registerServiceWorker(navigator, import.meta.env.PROD);
		return stop;
	});
</script>

<a class="skip-link" href="#main">Naar de inhoud</a>
<header class="site-header">
	<a class="brand" href="/">Shakka</a>
	<nav aria-label="Hoofdmenu">
		<a href="/over">Over</a>
		{#if $session}
			<span class="who">{$session.user.email}</span>
			<button type="button" disabled={signingOut} onclick={handleSignOut}>{signingOut ? 'Uitloggen…' : 'Uitloggen'}</button>
		{:else if $session === null}
			<a href="/login">Inloggen</a>
		{/if}
	</nav>
</header>
{#if redirectError}
	<div class="banner" role="alert">
		<p>{redirectError}</p>
		<a href="/login">Nieuwe inloglink</a>
		<button type="button" onclick={() => (redirectError = null)}>Sluiten</button>
	</div>
{/if}
<main id="main" tabindex="-1">{@render children()}</main>
<footer class="site-footer" class:has-tab-bar={!!$session}>
	<Attribution compact />
	<p><a href="/over">Over Shakka en bronnen</a> · <a href="/privacy">Privacy</a></p>
</footer>
{#if $session}
	<nav class="tab-bar" aria-label="Tabbalk">
		<a href="/">
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 15c3 0 3-3 6-3s3 3 6 3 3-3 6-3M3 9c3 0 3-3 6-3s3 3 6 3 3-3 6-3" /></svg>
			Spots
		</a>
		<a href="/alerts">
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5h4" /></svg>
			Alerts
		</a>
		<a href="/mijn-sessies">
			<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="1.5" /><path d="M4 10h16M9 3v4M15 3v4" /></svg>
			Mijn sessies
		</a>
		<a href="/profiel">
			<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c1-4 4-5.5 7-5.5s6 1.5 7 5.5" /></svg>
			Profiel
		</a>
	</nav>
{/if}
