<script lang="ts">
	import '../app.css';
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Attribution from '#lib/components/Attribution.svelte';
	import { session, initAuth, signOut, initialAuthRedirectError } from '#lib/auth.js';
	import { browserStorage } from '#lib/browser-storage.js';
	import { takeReturnTo } from '#lib/local-prefs.js';
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
		redirectError = initialAuthRedirectError();
		const stop = initAuth();
		void registerServiceWorker(navigator, import.meta.env.PROD);
		return stop;
	});
</script>

<header class="site-header">
	<a class="brand" href="/">Shakka</a>
	<nav aria-label="Hoofdmenu">
		<a href="/over">Over</a>
		{#if $session}
			<a href="/alerts">Alerts</a>
			<a href="/profiel">Profiel</a>
			<a href="/mijn-sessies">Mijn sessies</a>
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
<main>{@render children()}</main>
<footer class="site-footer">
	<Attribution compact />
	<p><a href="/over">Over Shakka en bronnen</a></p>
</footer>
