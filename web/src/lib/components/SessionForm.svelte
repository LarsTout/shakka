<script lang="ts">
	import { untrack } from 'svelte';
	import type { FieldErrors } from '#lib/forms.js';
	import {
		SESSION_FORM_MESSAGES,
		parseSessionForm,
		sessionDateBounds,
		type PreferredWindow,
		type SessionFormField,
		type SessionFormValues
	} from '#lib/session-form.js';
	import type { NewSession } from '#lib/session-model.js';
	import type { Spot } from '#lib/types.js';

	let {
		mode,
		idPrefix,
		spots,
		initial,
		preferred,
		onsave
	}: {
		mode: 'create' | 'edit';
		idPrefix: string;
		spots: Spot[];
		initial: SessionFormValues;
		preferred: PreferredWindow | null;
		onsave: (value: NewSession) => Promise<string | null>;
	} = $props();

	// initial value only
	let form = $state<SessionFormValues>(untrack(() => ({ ...initial })));
	let errors = $state<FieldErrors<SessionFormField>>({});
	let status = $state<'idle' | 'saving' | 'saved' | 'failed'>('idle');
	let failMessage = $state('');

	const bounds = sessionDateBounds(new Date());
	const id = (field: SessionFormField) => `${idPrefix}-${field}`;
	const describedBy = (field: SessionFormField, hint: boolean) =>
		[hint ? `${id(field)}-hint` : '', errors[field] ? `${id(field)}-error` : '']
			.filter(Boolean)
			.join(' ') || undefined;

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (status === 'saving') return;
		const r = parseSessionForm(form, {
			now: new Date(),
			spotIds: new Set(spots.map((s) => s.id)),
			preferred
		});
		if (!r.ok) {
			errors = r.errors;
			status = 'idle';
			return;
		}
		errors = {};
		status = 'saving';
		const msg = await onsave(r.value);
		if (msg === null) {
			status = 'saved';
		} else {
			status = 'failed';
			failMessage = msg;
		}
	}
</script>

{#snippet errorLine(field: SessionFormField)}
	{#if errors[field]}<p class="error" id="{id(field)}-error">{errors[field]}</p>{/if}
{/snippet}

<form novalidate onsubmit={submit} class="session-form">
	<div class="form-field">
		<label for={id('spot_id')}>Spot</label>
		<select
			id={id('spot_id')}
			bind:value={form.spot_id}
			aria-invalid={!!errors.spot_id || undefined}
			aria-describedby={describedBy('spot_id', false)}
		>
			<option value="">Kies een spot</option>
			{#each spots as s (s.id)}
				<option value={s.id}>{s.name}{s.verified ? '' : ' (niet geverifieerd)'}</option>
			{/each}
		</select>
		{@render errorLine('spot_id')}
	</div>

	<div class="form-field">
		<label for={id('date')}>Datum</label>
		<input
			type="date"
			id={id('date')}
			min={bounds.min}
			max={bounds.max}
			bind:value={form.date}
			aria-invalid={!!errors.date || undefined}
			aria-describedby={describedBy('date', false)}
		/>
		{@render errorLine('date')}
	</div>

	<div class="form-field">
		<label for={id('start_time')}>Van</label>
		<input
			type="time"
			id={id('start_time')}
			bind:value={form.start_time}
			aria-invalid={!!errors.start_time || undefined}
			aria-describedby={describedBy('start_time', false)}
		/>
		{@render errorLine('start_time')}
	</div>

	<div class="form-field">
		<label for={id('end_time')}>Tot</label>
		<input
			type="time"
			id={id('end_time')}
			bind:value={form.end_time}
			aria-invalid={!!errors.end_time || undefined}
			aria-describedby={describedBy('end_time', true)}
		/>
		<p class="hint" id="{id('end_time')}-hint">Tijden in Nederlandse tijd.</p>
		{@render errorLine('end_time')}
	</div>

	<div class="form-field">
		<label for={id('organizer_name')}>Je voornaam</label>
		<input
			type="text"
			autocomplete="given-name"
			id={id('organizer_name')}
			bind:value={form.organizer_name}
			aria-invalid={!!errors.organizer_name || undefined}
			aria-describedby={describedBy('organizer_name', true)}
		/>
		<p class="hint" id="{id('organizer_name')}-hint">
			Alleen je voornaam. Shakka onthoudt hem op dit apparaat.
		</p>
		{@render errorLine('organizer_name')}
	</div>

	<div class="form-field">
		<label for={id('note')}>Notitie (optioneel)</label>
		<textarea
			rows="3"
			id={id('note')}
			bind:value={form.note}
			aria-invalid={!!errors.note || undefined}
			aria-describedby={describedBy('note', true)}
		></textarea>
		<p class="hint" id="{id('note')}-hint">Hoogstens 280 tekens.</p>
		{@render errorLine('note')}
	</div>

	<div class="form-field">
		<label for={id('seats_free')}>Vrije plekken in je auto (optioneel)</label>
		<input
			type="text"
			inputmode="numeric"
			autocomplete="off"
			id={id('seats_free')}
			bind:value={form.seats_free}
			aria-invalid={!!errors.seats_free || undefined}
			aria-describedby={describedBy('seats_free', true)}
		/>
		<p class="hint" id="{id('seats_free')}-hint">0 tot 8. Leeg als je niet rijdt.</p>
		{@render errorLine('seats_free')}
	</div>

	<div class="form-field">
		<label for={id('departure_point')}>Vertrekpunt (optioneel)</label>
		<input
			type="text"
			id={id('departure_point')}
			bind:value={form.departure_point}
			aria-invalid={!!errors.departure_point || undefined}
			aria-describedby={describedBy('departure_point', true)}
		/>
		<p class="hint" id="{id('departure_point')}-hint">Bijvoorbeeld Utrecht CS.</p>
		{@render errorLine('departure_point')}
	</div>

	<div class="form-field">
		<label for={id('tikkie_url')}>Tikkie-link (optioneel)</label>
		<input
			type="url"
			inputmode="url"
			autocomplete="off"
			id={id('tikkie_url')}
			bind:value={form.tikkie_url}
			aria-invalid={!!errors.tikkie_url || undefined}
			aria-describedby={describedBy('tikkie_url', true)}
		/>
		<p class="hint" id="{id('tikkie_url')}-hint">
			Een link uit de Tikkie-app (https://tikkie.me/…). Deelnemers zien deze link.
		</p>
		{@render errorLine('tikkie_url')}
	</div>

	{#if mode === 'edit'}
		<p class="hint">Deelnemers krijgen geen bericht van een wijziging. Laat het ze zelf weten.</p>
	{/if}

	<button type="submit" disabled={status === 'saving'}>
		{mode === 'create' ? 'Sessie aanmaken' : 'Wijzigingen opslaan'}
	</button>

	{#if Object.keys(errors).length > 0}
		<p role="alert" class="error">{SESSION_FORM_MESSAGES.summary}</p>
	{/if}
	{#if status === 'saved' && mode === 'edit'}<p role="status">Opgeslagen.</p>{/if}
	{#if status === 'failed'}<p role="alert" class="error">{failMessage}</p>{/if}
</form>
