<script lang="ts">
	import '../app.css';
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import Attribution from '#lib/components/Attribution.svelte';
	import { session, initAuth, signOut, initialAuthRedirectError } from '#lib/auth.js';
	import { registerServiceWorker } from '#lib/sw-register.js';

	let { children }: { children: Snippet } = $props();
	let redirectError = $state<string | null>(null);

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
			<span class="who">{$session.user.email}</span>
			<button type="button" onclick={() => signOut()}>Uitloggen</button>
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
