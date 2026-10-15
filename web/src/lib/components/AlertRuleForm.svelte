<script lang="ts">
	import { untrack } from 'svelte';
	import { ALERT_DEFAULTS, dirClassLabel } from '#lib/contracts.js';
	import {
		daysAheadOptions,
		parseAlertRuleForm,
		ruleHints,
		ruleToForm,
		timeOptions,
		type AlertRuleForm as AlertRuleFormValues,
		type FieldErrors,
		type RuleContext
	} from '#lib/forms.js';
	import { daysAheadText } from '#lib/labels.js';
	import { WEEKDAY_NL } from '#lib/time.js';
	import type { AlertRuleRow, Profile, RuleField, Spot } from '#lib/types.js';
	import { DataError } from '#lib/data.js';
	import { resetAlertRule, saveAlertRule } from '#lib/user-data.js';

	let {
		userId,
		spot,
		profile,
		row,
		onsaved
	}: {
		userId: string;
		spot: Spot;
		profile: Profile | null;
		row: AlertRuleRow | null;
		onsaved: (row: AlertRuleRow | null) => void;
	} = $props();

	// initial value only; submit/reset set form explicitly
	let form = $state<AlertRuleFormValues>(untrack(() => ruleToForm(row, ALERT_DEFAULTS)));
	let errors = $state<FieldErrors<RuleField>>({});
	let status = $state<'idle' | 'saving' | 'saved' | 'reset' | 'failed'>('idle');
	let failMessage = $state('');

	const ctx: RuleContext = $derived({ spot, profile, defaults: ALERT_DEFAULTS });
	const hints = $derived(ruleHints(form, ctx));

	const id = (field: string) => `${field}-${spot.id}`;
	const describedBy = (field: RuleField) =>
		errors[field] ? `${id(field)}-hint ${id(field)}-error` : `${id(field)}-hint`;
	const GENERIC_FAILURE = 'Opslaan is niet gelukt. Probeer het opnieuw.';

	function fail(e: unknown) {
		status = 'failed';
		failMessage =
			e instanceof DataError && e.code === '23503'
				? 'Deze spot staat niet meer in je favorieten. Herlaad de pagina.'
				: GENERIC_FAILURE;
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		const r = parseAlertRuleForm(form, ctx);
		if (!r.ok) {
			errors = r.errors;
			status = 'idle';
			return;
		}
		errors = {};
		status = 'saving';
		try {
			const saved = await saveAlertRule(userId, spot.id, r.value);
			form = ruleToForm(saved, ALERT_DEFAULTS);
			onsaved(saved);
			status = 'saved';
		} catch (err) {
			fail(err);
		}
	}

	async function reset() {
		try {
			await resetAlertRule(userId, spot.id);
			form = ruleToForm(null, ALERT_DEFAULTS);
			errors = {};
			onsaved(null);
			status = 'reset';
		} catch (err) {
			fail(err);
		}
	}
</script>

{#snippet numField(field: 'min_kn' | 'max_kn' | 'min_go_hours')}
	<div class="form-field">
		<label for={id(field)}>{ALERT_DEFAULTS[field].label_nl}</label>
		<input
			type="text"
			inputmode="numeric"
			autocomplete="off"
			id={id(field)}
			bind:value={form[field]}
			aria-invalid={!!errors[field] || undefined}
			aria-describedby={describedBy(field)}
		/>
		<p class="hint" id="{id(field)}-hint">{hints[field] ?? ''}</p>
		{#if errors[field]}<p class="error" id="{id(field)}-error">{errors[field]}</p>{/if}
	</div>
{/snippet}

{#snippet timeField(field: 'earliest_local' | 'latest_local', none: string)}
	<div class="form-field">
		<label for={id(field)}>{ALERT_DEFAULTS[field].label_nl}</label>
		<select
			id={id(field)}
			bind:value={form[field]}
			aria-invalid={!!errors[field] || undefined}
			aria-describedby={describedBy(field)}
		>
			<option value="">{none}</option>
			{#each timeOptions(form[field]) as t (t)}
				<option value={t}>{t}</option>
			{/each}
		</select>
		<p class="hint" id="{id(field)}-hint">{hints[field] ?? ''}</p>
		{#if errors[field]}<p class="error" id="{id(field)}-error">{errors[field]}</p>{/if}
	</div>
{/snippet}

<form novalidate onsubmit={submit} class="rule-form">
	<div class="form-field checkbox-row">
		<input type="checkbox" id={id('enabled')} bind:checked={form.enabled} />
		<label for={id('enabled')}>Alert aan</label>
	</div>

	{@render numField('min_kn')}
	{@render numField('max_kn')}

	<fieldset aria-describedby={describedBy('dir_classes')}>
		<legend>{ALERT_DEFAULTS.dir_classes.label_nl}</legend>
		{#each ALERT_DEFAULTS.dir_classes.allowed as code (code)}
			<input
				type="checkbox"
				name="dir_classes-{spot.id}"
				value={code}
				bind:group={form.dir_classes}
				id="dir-{code}-{spot.id}"
			/>
			<label for="dir-{code}-{spot.id}">{dirClassLabel(code)}</label>
		{/each}
		<p class="hint">
			Aflandige en schuin aflandige wind zijn nooit kitebaar en staan hier daarom niet tussen.
		</p>
		<p class="hint" id="{id('dir_classes')}-hint">{hints.dir_classes ?? ''}</p>
		{#if errors.dir_classes}<p class="error" id="{id('dir_classes')}-error">{errors.dir_classes}</p>{/if}
	</fieldset>

	<fieldset aria-describedby={describedBy('weekdays')}>
		<legend>{ALERT_DEFAULTS.weekdays.label_nl}</legend>
		{#each ALERT_DEFAULTS.weekdays.allowed as d (d)}
			<input
				type="checkbox"
				name="weekdays-{spot.id}"
				value={d}
				bind:group={form.weekdays}
				id="weekday-{d}-{spot.id}"
			/>
			<label for="weekday-{d}-{spot.id}">{WEEKDAY_NL[d - 1]}</label>
		{/each}
		<p class="hint" id="{id('weekdays')}-hint">{hints.weekdays ?? ''}</p>
		{#if errors.weekdays}<p class="error" id="{id('weekdays')}-error">{errors.weekdays}</p>{/if}
	</fieldset>

	{@render timeField('earliest_local', 'Geen ondergrens')}
	{@render timeField('latest_local', 'Geen bovengrens')}

	{@render numField('min_go_hours')}

	<div class="form-field">
		<label for={id('days_ahead')}>{ALERT_DEFAULTS.days_ahead.label_nl}</label>
		<select
			id={id('days_ahead')}
			bind:value={form.days_ahead}
			aria-invalid={!!errors.days_ahead || undefined}
			aria-describedby={describedBy('days_ahead')}
		>
			<option value="">Standaard</option>
			{#each daysAheadOptions(form.days_ahead) as n (n)}
				<option value={n}>{n} ({daysAheadText(Number(n))})</option>
			{/each}
		</select>
		<p class="hint">Dagen ná vandaag: 3 betekent vandaag plus drie dagen.</p>
		<p class="hint" id="{id('days_ahead')}-hint">{hints.days_ahead ?? ''}</p>
		{#if errors.days_ahead}<p class="error" id="{id('days_ahead')}-error">{errors.days_ahead}</p>{/if}
	</div>

	<button type="submit" disabled={status === 'saving'}>Opslaan</button>
	{#if row !== null}
		<button type="button" onclick={reset}>Standaardinstellingen</button>
	{/if}

	{#if Object.keys(errors).length}
		<p role="alert" class="error">Niet opgeslagen: controleer de gemarkeerde velden.</p>
	{/if}
	{#if status === 'saved'}<p role="status">Opgeslagen.</p>{/if}
	{#if status === 'reset'}<p role="status">Standaardinstellingen hersteld.</p>{/if}
	{#if status === 'failed'}<p role="alert" class="error">{failMessage}</p>{/if}
</form>
