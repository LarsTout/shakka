<script lang="ts">
	import { untrack } from 'svelte';
	import {
		parseQuietHours,
		quietHourOptions,
		quietHoursSummary,
		quietToForm,
		type QuietHoursForm
	} from '#lib/forms.js';
	import type { Profile } from '#lib/types.js';
	import { updateQuietHours } from '#lib/user-data.js';

	let {
		userId,
		profile,
		onsaved
	}: {
		userId: string;
		profile: Profile | null;
		onsaved: (profile: Profile) => void;
	} = $props();

	// initial value only; saving sets form explicitly
	let form = $state<QuietHoursForm>(untrack(() => quietToForm(profile)));
	let status = $state<'idle' | 'saving' | 'saved' | 'off' | 'failed'>('idle');
	let problem = $state('');

	const GENERIC_FAILURE = 'Opslaan is niet gelukt. Probeer het opnieuw.';

	async function write(values: { quiet_from: string | null; quiet_until: string | null }) {
		status = 'saving';
		problem = '';
		try {
			const saved = await updateQuietHours(userId, values);
			form = quietToForm(saved);
			onsaved(saved);
			status = values.quiet_from === null ? 'off' : 'saved';
		} catch {
			status = 'failed';
		}
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const r = parseQuietHours(form.from, form.until);
		if ('error' in r) {
			problem = r.error;
			status = 'idle';
			return;
		}
		void write(r);
	}

	function switchOff() {
		void write({ quiet_from: null, quiet_until: null });
	}
</script>

<section class="quiet-hours" aria-labelledby="quiet-hours-title">
	<h2 id="quiet-hours-title">Stille uren</h2>
	{#if profile === null}
		<p>Stille uren kun je instellen zodra je profiel is aangemaakt.</p>
	{:else}
		<p class="muted">
			In deze periode krijg je geen alerts, elke dag, in Nederlandse tijd. Verandert er intussen
			iets, dan krijg je na afloop binnen een uur alleen de actuele stand, geen reeks oude
			meldingen.
		</p>
		<p class="quiet-summary">{quietHoursSummary(profile)}</p>
		<form novalidate onsubmit={submit} class="quiet-form">
			<div class="form-field">
				<label for="quiet-from">Van</label>
				<select id="quiet-from" bind:value={form.from}>
					<option value="">–</option>
					{#each quietHourOptions(form.from) as t (t)}
						<option value={t}>{t}</option>
					{/each}
				</select>
			</div>
			<div class="form-field">
				<label for="quiet-until">Tot</label>
				<select id="quiet-until" bind:value={form.until}>
					<option value="">–</option>
					{#each quietHourOptions(form.until) as t (t)}
						<option value={t}>{t}</option>
					{/each}
				</select>
			</div>
			<button type="submit" disabled={status === 'saving'}>Opslaan</button>
			<button type="button" onclick={switchOff} disabled={status === 'saving'}>Uit</button>
		</form>
		{#if problem !== ''}
			<p role="alert" class="error">{problem}</p>
		{:else if status === 'failed'}
			<p role="alert" class="error">{GENERIC_FAILURE}</p>
		{:else if status === 'saved'}
			<p role="status">Opgeslagen.</p>
		{:else if status === 'off'}
			<p role="status">Stille uren staan uit.</p>
		{/if}
	{/if}
</section>
