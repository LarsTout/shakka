<script lang="ts">
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import LoginPrompt from '#lib/components/LoginPrompt.svelte';
	import SessionForm from '#lib/components/SessionForm.svelte';
	import { session } from '#lib/auth.js';
	import { browserStorage } from '#lib/browser-storage.js';
	import { readOrganizerName, writeOrganizerName } from '#lib/local-prefs.js';
	import { prefillSessionForm, withKnownSpot } from '#lib/session-form.js';
	import type { NewSession } from '#lib/session-model.js';
	import { loadNewSessionPage, type NewSessionPageData } from '#lib/session-page-data.js';
	import { createSession, sessionErrorMessage } from '#lib/sessions.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// initial value only: the form is prefilled once, from the link
	const prefill = untrack(() =>
		prefillSessionForm(data.params, readOrganizerName(browserStorage()), new Date())
	);

	const userId = $derived($session ? $session.user.id : null);
	let page = $state<{ kind: 'idle' } | { kind: 'loading' } | NewSessionPageData>({ kind: 'idle' });
	let token = 0;

	function load() {
		const t = ++token;
		page = { kind: 'loading' };
		void loadNewSessionPage().then((r) => {
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

	async function onsave(v: NewSession): Promise<string | null> {
		try {
			const { slug } = await createSession(v);
			writeOrganizerName(browserStorage(), v.organizer_name);
			await goto(`/sessie/${slug}/delen`, { replace: true });
			return null;
		} catch (e) {
			return sessionErrorMessage(e);
		}
	}
</script>

<svelte:head><title>Sessie aanmaken · Shakka</title></svelte:head>

<h1>Sessie aanmaken</h1>

{#if $session === undefined}
	<p class="muted">Laden…</p>
{:else if $session === null}
	<LoginPrompt reason="een sessie aan te maken" />
{:else if page.kind === 'idle' || page.kind === 'loading'}
	<p class="muted">Laden…</p>
{:else if page.kind === 'error'}
	<div class="banner" role="alert">
		<p>De spots konden niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={retry}>Opnieuw proberen</button>
	</div>
{:else}
	{@const p = withKnownSpot(prefill, page.spots)}
	<p class="muted">
		Iedereen met de link ziet je voornaam, het tijdvenster, de notitie, het vertrekpunt en de
		Tikkie-link.
	</p>
	{#each p.notices as n (n)}
		<p class="notice" role="status">{n}</p>
	{/each}
	<SessionForm
		mode="create"
		idPrefix="new"
		spots={page.spots}
		initial={p.form}
		preferred={p.preferred}
		{onsave}
	/>
{/if}
