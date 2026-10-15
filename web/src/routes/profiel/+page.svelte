<script lang="ts">
	import LoginPrompt from '#lib/components/LoginPrompt.svelte';
	import { session } from '#lib/auth.js';
	import { ALERT_DEFAULTS } from '#lib/contracts.js';
	import {
		MAX_QUIVER_KITES,
		parseProfileForm,
		profileKnHints,
		profileToForm,
		type FieldErrors,
		type ProfileForm
	} from '#lib/forms.js';
	import { LEVEL_LABEL_NL } from '#lib/labels.js';
	import { LEVELS, type ProfileEditableColumn } from '#lib/types.js';
	import { updateProfile } from '#lib/user-data.js';
	import { loadProfilePage, type ProfilePageData } from '#lib/user-page-data.js';

	const userId = $derived($session ? $session.user.id : null);
	let page = $state<{ kind: 'idle' } | { kind: 'loading' } | ProfilePageData>({ kind: 'idle' });
	// /profiel only: form state (not rendered until page.kind === 'ok')
	let form = $state<ProfileForm>(
		profileToForm({
			weight_kg: null,
			level: null,
			quiver_m2: [],
			default_min_kn: null,
			default_max_kn: null
		})
	);
	let errors = $state<FieldErrors<ProfileEditableColumn>>({});
	let status = $state<'idle' | 'saving' | 'saved' | 'failed'>('idle');
	const saving = $derived(status === 'saving');
	const hints = profileKnHints(ALERT_DEFAULTS);
	let token = 0;

	function load(id: string) {
		const t = ++token;
		page = { kind: 'loading' };
		void loadProfilePage(id).then((r) => {
			if (t === token) {
				page = r;
				if (r.kind === 'ok') {
					form = profileToForm(r.profile);
					errors = {};
					status = 'idle';
				}
			}
		});
	}
	function retry() {
		if (userId !== null) load(userId);
	}
	$effect(() => {
		const id = userId;
		if (id === null) {
			token++;
			page = { kind: 'idle' };
			return;
		}
		load(id);
	});

	const describedBy = (field: string, hasHint: boolean, error: string | undefined) =>
		[hasHint ? `${field}-hint` : '', error ? `${field}-error` : ''].filter(Boolean).join(' ') ||
		undefined;

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		const id = userId;
		if (id === null) return;
		const r = parseProfileForm(form, ALERT_DEFAULTS);
		if (!r.ok) {
			errors = r.errors;
			status = 'idle';
			return;
		}
		errors = {};
		status = 'saving';
		try {
			const saved = await updateProfile(id, r.value);
			page = { kind: 'ok', profile: saved };
			form = profileToForm(saved);
			status = 'saved';
		} catch {
			status = 'failed';
		}
	}
</script>

<svelte:head><title>Profiel · Shakka</title></svelte:head>

<h1>Profiel</h1>

{#if $session === undefined}
	<p class="muted">Laden…</p>
{:else if $session === null}
	<LoginPrompt reason="je profiel te bewerken" />
{:else if page.kind === 'idle' || page.kind === 'loading'}
	<p class="muted">Laden…</p>
{:else if page.kind === 'error'}
	<div class="banner" role="alert">
		<p>Je profiel kon niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={retry}>Opnieuw proberen</button>
	</div>
{:else if page.kind === 'missing'}
	<div class="banner" role="alert">
		<p>
			Je profiel is niet gevonden. Log uit en weer in. Helpt dat niet, neem dan contact op met de
			beheerder.
		</p>
	</div>
{:else}
	<p class="muted">
		Shakka gebruikt deze gegevens voor je alerts en voor het kite-advies in je meldingen. Alles is
		optioneel.
	</p>
	<form novalidate onsubmit={submit}>
		<div class="form-field">
			<label for="weight_kg">Gewicht (kg)</label>
			<input
				type="text"
				inputmode="numeric"
				autocomplete="off"
				id="weight_kg"
				bind:value={form.weight_kg}
				aria-invalid={!!errors.weight_kg || undefined}
				aria-describedby={describedBy('weight_kg', true, errors.weight_kg)}
			/>
			<p class="hint" id="weight_kg-hint">Voor het kite-advies. Leeg = geen kite-advies.</p>
			{#if errors.weight_kg}<p class="error" id="weight_kg-error">{errors.weight_kg}</p>{/if}
		</div>

		<div class="form-field">
			<label for="level">Niveau</label>
			<select
				id="level"
				bind:value={form.level}
				aria-invalid={!!errors.level || undefined}
				aria-describedby={describedBy('level', false, errors.level)}
			>
				<option value="">Niet ingevuld</option>
				{#each LEVELS as l (l)}
					<option value={l}>{LEVEL_LABEL_NL[l]}</option>
				{/each}
			</select>
			{#if errors.level}<p class="error" id="level-error">{errors.level}</p>{/if}
		</div>

		<fieldset aria-describedby={describedBy('quiver', true, errors.quiver_m2)}>
			<legend>Quiver (kitematen in m²)</legend>
			{#each form.quiver as _, i (i)}
				<div class="form-field">
					<label for="quiver-{i}">Kite {i + 1} (m²)</label>
					<input
						id="quiver-{i}"
						type="text"
						inputmode="decimal"
						autocomplete="off"
						bind:value={form.quiver[i]}
						aria-invalid={!!errors.quiver_m2 || undefined}
					/>
					<button type="button" onclick={() => form.quiver.splice(i, 1)}>
						Verwijder kite {i + 1}
					</button>
				</div>
			{/each}
			<button
				type="button"
				disabled={form.quiver.length >= MAX_QUIVER_KITES}
				onclick={() => form.quiver.push('')}>Kite toevoegen</button
			>
			<p class="hint" id="quiver-hint">Maten van 3 tot 21 m², maximaal 10 kites.</p>
			{#if errors.quiver_m2}<p class="error" id="quiver-error">{errors.quiver_m2}</p>{/if}
		</fieldset>

		<div class="form-field">
			<label for="default_min_kn">Standaard minimale wind (kn)</label>
			<input
				type="text"
				inputmode="numeric"
				autocomplete="off"
				id="default_min_kn"
				bind:value={form.default_min_kn}
				aria-invalid={!!errors.default_min_kn || undefined}
				aria-describedby={describedBy('default_min_kn', true, errors.default_min_kn)}
			/>
			<p class="hint" id="default_min_kn-hint">{hints.default_min_kn}</p>
			{#if errors.default_min_kn}<p class="error" id="default_min_kn-error">
					{errors.default_min_kn}
				</p>{/if}
		</div>

		<div class="form-field">
			<label for="default_max_kn">Standaard maximale wind (kn)</label>
			<input
				type="text"
				inputmode="numeric"
				autocomplete="off"
				id="default_max_kn"
				bind:value={form.default_max_kn}
				aria-invalid={!!errors.default_max_kn || undefined}
				aria-describedby={describedBy('default_max_kn', true, errors.default_max_kn)}
			/>
			<p class="hint" id="default_max_kn-hint">{hints.default_max_kn}</p>
			{#if errors.default_max_kn}<p class="error" id="default_max_kn-error">
					{errors.default_max_kn}
				</p>{/if}
		</div>

		<button type="submit" disabled={saving}>Opslaan</button>

		{#if Object.keys(errors).length}
			<p role="alert" class="error">Niet opgeslagen: controleer de gemarkeerde velden.</p>
		{/if}
		{#if status === 'saved'}<p role="status">Opgeslagen.</p>{/if}
		{#if status === 'failed'}
			<p role="alert" class="error">Opslaan is niet gelukt. Probeer het opnieuw.</p>
		{/if}
	</form>
{/if}
