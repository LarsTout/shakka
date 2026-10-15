<script lang="ts">
	import { untrack } from 'svelte';
	import { RIDES, type PublicRsvp, type RsvpUpdateInput } from '#lib/rsvp-types.js';
	import {
		RIDE_OPTION_LABEL_NL,
		isolateText,
		parseRsvpForm,
		type RsvpFormField,
		type RsvpFormMode,
		type RsvpFormValues
	} from '#lib/session-view.js';

	let {
		mode,
		initial,
		drivers,
		busy,
		onsubmit,
		oncancel
	}: {
		mode: RsvpFormMode;
		initial: RsvpFormValues;
		drivers: PublicRsvp[];
		busy: boolean;
		onsubmit: (value: RsvpUpdateInput) => void;
		oncancel?: () => void;
	} = $props();

	let values = $state<RsvpFormValues>(untrack(() => ({ ...initial })));
	let errors = $state<Partial<Record<RsvpFormField, string>>>({});
	const prefix = untrack(() => (mode === 'create' ? 'rsvp' : 'rsvp-edit'));

	function submit(e: SubmitEvent) {
		e.preventDefault();
		if (busy) return;
		const r = parseRsvpForm(values, mode, new Set(drivers.map((d) => d.id)));
		if (!r.ok) {
			errors = r.errors;
			return;
		}
		errors = {};
		onsubmit(r.value);
	}
</script>

<form novalidate onsubmit={submit} class="rsvp-form">
	<div class="form-field">
		<label for="{prefix}-name">Voornaam</label>
		<input
			id="{prefix}-name"
			name="first_name"
			type="text"
			autocomplete="given-name"
			bind:value={values.first_name}
			aria-invalid={errors.first_name ? 'true' : undefined}
			aria-describedby={errors.first_name ? `${prefix}-name-error` : undefined}
		/>
		{#if errors.first_name}<p id="{prefix}-name-error" class="error">{errors.first_name}</p>{/if}
	</div>
	<fieldset>
		<legend>Vervoer</legend>
		{#each RIDES as ride (ride)}
			<div>
				<input
					type="radio"
					id="{prefix}-ride-{ride}"
					name="{prefix}-ride"
					value={ride}
					bind:group={values.ride}
				/>
				<label for="{prefix}-ride-{ride}">{RIDE_OPTION_LABEL_NL[ride]}</label>
			</div>
		{/each}
		{#if errors.ride}<p class="error">{errors.ride}</p>{/if}
	</fieldset>
	{#if values.ride === 'offers_ride'}
		<div class="form-field">
			<label for="{prefix}-seats">Plekken over in je auto</label>
			<select id="{prefix}-seats" bind:value={values.seats}>
				<option value="">Weet ik nog niet</option>
				<option value="0">Geen (auto zit vol)</option>
				<option value="1">1 plek</option>
				{#each [2, 3, 4, 5, 6, 7, 8] as n (n)}<option value={String(n)}>{n} plekken</option>{/each}
			</select>
			{#if errors.seats}<p class="error">{errors.seats}</p>{/if}
		</div>
	{/if}
	{#if mode === 'edit' && values.ride === 'needs_ride'}
		<div class="form-field">
			<label for="{prefix}-rides-with">Rijd mee met</label>
			<select id="{prefix}-rides-with" bind:value={values.rides_with}>
				<option value="">Nog niemand: ik zoek een lift</option>
				{#each drivers as d (d.id)}<option value={d.id}>{isolateText(d.first_name)}</option>{/each}
			</select>
			{#if errors.rides_with}<p class="error">{errors.rides_with}</p>{/if}
		</div>
	{/if}
	{#if mode === 'create' && values.ride === 'needs_ride'}
		<p class="hint">
			Rijdt iemand al met een lege plek? Na het aanmelden kun je via Wijzigen kiezen met wie je
			meerijdt.
		</p>
	{/if}
	{#if mode === 'create'}
		<button type="submit" disabled={busy}>{busy ? 'Bezig…' : 'Ik ook'}</button>
	{:else}
		<button type="submit" disabled={busy}>{busy ? 'Bezig…' : 'Opslaan'}</button>
		<button type="button" disabled={busy} onclick={() => oncancel?.()}>Annuleren</button>
	{/if}
</form>
