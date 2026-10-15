<script lang="ts">
	import { tick } from 'svelte';
	import { cleanUpAfterAccountDeletion, deleteMyAccount } from '#lib/account.js';
	import { browserStorage } from '#lib/browser-storage.js';

	let { ondeleted }: { ondeleted: () => void } = $props();

	let mode = $state<'idle' | 'confirm'>('idle');
	let busy = $state(false);
	let error = $state<string | null>(null);
	let askButton = $state<HTMLButtonElement | null>(null);
	let confirmTitle = $state<HTMLParagraphElement | null>(null);

	async function ask() {
		error = null;
		mode = 'confirm';
		await tick();
		confirmTitle?.focus();
	}

	async function cancel() {
		mode = 'idle';
		await tick();
		askButton?.focus();
	}

	async function confirm() {
		if (busy) return;
		busy = true;
		error = null;
		const r = await deleteMyAccount();
		if (!r.ok) {
			error = r.error;
			busy = false;
			return;
		}
		// The component is usually unmounted after ondeleted(); nothing below writes state.
		ondeleted();
		await cleanUpAfterAccountDeletion(browserStorage());
	}
</script>

<section class="delete-account" aria-labelledby="delete-account-heading">
	<h2 id="delete-account-heading">Account verwijderen</h2>
	{#if mode === 'idle'}
		<p>
			Hiermee verwijder je je account en alle gegevens die eraan vastzitten. In de
			<a href="/privacy">privacyverklaring</a> staat precies welke.
		</p>
		<button type="button" bind:this={askButton} onclick={ask}>Account verwijderen…</button>
	{:else}
		<div class="banner warning" role="group" aria-labelledby="delete-confirm-title">
			<p id="delete-confirm-title" tabindex="-1" bind:this={confirmTitle}><strong>Weet je het zeker?</strong></p>
			<p>
				Dit verwijdert direct en definitief: je e-mailadres en login, je profiel, je favorieten en
				alertinstellingen, de meldingen op al je apparaten, en de sessies die je organiseert, met de
				aanmeldingen van anderen daarvoor. Dit kun je niet ongedaan maken.
			</p>
			<button type="button" class="danger" disabled={busy} onclick={confirm}>
				{busy ? 'Bezig met verwijderen…' : 'Ja, verwijder mijn account'}
			</button>
			<button type="button" disabled={busy} onclick={cancel}>Annuleren</button>
		</div>
	{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
