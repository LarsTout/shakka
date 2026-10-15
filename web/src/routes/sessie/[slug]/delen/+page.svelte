<script lang="ts">
	import { onMount } from 'svelte';
	import LoginPrompt from '#lib/components/LoginPrompt.svelte';
	import { session } from '#lib/auth.js';
	import { sessionPath } from '#lib/session-model.js';
	import { loadSharePage, type SharePageData } from '#lib/session-page-data.js';
	import { sessionUrl, shareText, whatsappUrl } from '#lib/sessions.js';
	import { formatWindowLocal } from '#lib/time.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const userId = $derived($session ? $session.user.id : null);
	let page = $state<{ kind: 'idle' } | { kind: 'loading' } | SharePageData>({ kind: 'idle' });
	let token = 0;
	let canShare = $state(false);
	let shareStatus = $state('');

	onMount(() => {
		canShare = typeof navigator.share === 'function';
	});

	function load() {
		const t = ++token;
		page = { kind: 'loading' };
		void loadSharePage(data.slug).then((r) => {
			if (t === token) page = r;
		});
	}
	function retry() {
		if (userId !== null) load();
	}
	$effect(() => {
		if (userId === null) {
			token++;
			page = { kind: 'idle' };
			return;
		}
		load();
	});

	async function share(text: string) {
		try {
			await navigator.share({ text });
			shareStatus = '';
		} catch (e) {
			shareStatus =
				(e as { name?: string } | null)?.name === 'AbortError'
					? ''
					: 'Delen is niet gelukt. Gebruik de WhatsApp-knop of kopieer de link.';
		}
	}

	async function copy(url: string) {
		try {
			await navigator.clipboard.writeText(url);
			shareStatus = 'Link gekopieerd.';
		} catch {
			shareStatus = 'Kopiëren is niet gelukt. Houd de link hierboven ingedrukt om hem te kopiëren.';
		}
	}
</script>

<svelte:head><title>Sessie delen · Shakka</title></svelte:head>

<h1>Sessie delen</h1>

{#if $session === undefined}
	<p class="muted">Laden…</p>
{:else if $session === null}
	<LoginPrompt reason="deze sessie te delen" />
{:else if page.kind === 'idle' || page.kind === 'loading'}
	<p class="muted">Laden…</p>
{:else if page.kind === 'error'}
	<div class="banner" role="alert">
		<p>De sessie kon niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={retry}>Opnieuw proberen</button>
	</div>
{:else if page.kind === 'not_found'}
	<p>Deze sessie bestaat niet, of je bent niet de organisator.</p>
	<p><a href="/mijn-sessies">Naar mijn sessies</a></p>
{:else}
	{@const s = page.session}
	{@const url = sessionUrl(data.origin, s.slug)}
	{@const text = shareText(s, page.spotName, url)}
	<p class="session-summary">
		<strong>{page.spotName}</strong> · {formatWindowLocal(new Date(s.starts_at), new Date(s.ends_at))}
	</p>
	{#if s.cancelled_at !== null}
		<div class="banner warning" role="note"><p>Deze sessie is geannuleerd.</p></div>
	{:else}
		<div class="form-field">
			<label for="share-url">Link naar de sessie</label>
			<input id="share-url" type="text" readonly value={url} />
		</div>
		<div class="share-actions">
			<a class="share-button" href={whatsappUrl(text)} target="_blank" rel="noopener noreferrer"
				>Deel via WhatsApp</a
			>
			{#if canShare}<button type="button" onclick={() => share(text)}>Delen…</button>{/if}
			<button type="button" onclick={() => copy(url)}>Kopieer link</button>
		</div>
		{#if shareStatus}<p role="status">{shareStatus}</p>{/if}
		<details>
			<summary>Voorbeeld van het bericht</summary>
			<p class="prewrap share-preview">{text}</p>
		</details>
	{/if}
	<p><a href={sessionPath(s.slug)}>Bekijk de sessiepagina</a> · <a href="/mijn-sessies">Mijn sessies</a></p>
{/if}

<style>
	.share-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0.75rem 0;
	}
	.share-button {
		display: inline-flex;
		align-items: center;
		min-height: 2.75rem;
		padding: 0.4rem 0.75rem;
		border-radius: 0.25rem;
		background: #0b5e8a;
		color: #fff;
		font-weight: 600;
		text-decoration: none;
	}
	.share-actions button {
		min-height: 2.75rem;
	}
</style>
