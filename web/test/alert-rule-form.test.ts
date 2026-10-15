import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { writeCalls } from './helpers/fake-supabase.js';
import { SPOT_VERIFIED } from './fixtures/spot-data.js';
import { PROFILE_FULL, ruleRow } from './fixtures/user-data.js';
import { USER_ID } from './helpers/fake-session.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});

import AlertRuleForm from '../src/lib/components/AlertRuleForm.svelte';
import { ALERT_RULE_COLUMNS, type AlertRuleRow } from '../src/lib/types.js';

const onsaved = vi.fn();
const draw = (row: AlertRuleRow | null = null) =>
	render(AlertRuleForm, { userId: USER_ID, spot: SPOT_VERIFIED, profile: PROFILE_FULL, row, onsaved });
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const optionValues = (select: HTMLElement) =>
	[...select.querySelectorAll('option')].map((o) => (o as HTMLOptionElement).value);

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
});

describe('AlertRuleForm', () => {
	it('AC-3: only the three ridable directions are offered', () => {
		const { container } = draw();
		const group = screen.getByRole('group', { name: 'Windrichtingen' });
		const boxes = within(group).getAllByRole('checkbox') as HTMLInputElement[];
		expect(boxes.map((b) => b.value)).toEqual(['onshore', 'side_onshore', 'sideshore']);
		expect(boxes.map((b) => b.id)).toHaveLength(3);
		expect(within(group).getByRole('checkbox', { name: 'Aanlandig' })).toBeInTheDocument();
		expect(within(group).getByRole('checkbox', { name: 'Schuin aanlandig' })).toBeInTheDocument();
		expect(within(group).getByRole('checkbox', { name: 'Sideshore (langs de kust)' })).toBeInTheDocument();
		const all = [...container.querySelectorAll('input[type=checkbox]')] as HTMLInputElement[];
		expect(all.some((b) => b.value === 'side_offshore' || b.value === 'offshore')).toBe(false);
		expect(screen.queryByLabelText('Aflandig')).toBeNull();
		expect(screen.queryByLabelText('Schuin aflandig')).toBeNull();
	});

	it('AC-4: min 20 / max 15 is refused without a write', async () => {
		draw();
		const user = userEvent.setup();
		await user.type(field('Minimale wind (kn)'), '20');
		await user.type(field('Maximale wind (kn)'), '15');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByText('De maximale wind moet hoger zijn dan de minimale wind.')).toBeInTheDocument();
		expect(field('Maximale wind (kn)')).toHaveAttribute('aria-invalid', 'true');
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});

	it('AC-4: a conflict with the profile is refused', async () => {
		draw();
		const user = userEvent.setup();
		await user.type(field('Minimale wind (kn)'), '30');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByText(/je profiel/, { selector: 'p.error' })).toBeInTheDocument();
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});

	it('no directions selected is refused', async () => {
		draw();
		const user = userEvent.setup();
		for (const name of ['Aanlandig', 'Schuin aanlandig', 'Sideshore (langs de kust)']) {
			await user.click(screen.getByRole('checkbox', { name }));
		}
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByText('Kies minstens één windrichting.')).toBeInTheDocument();
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});

	it('saves a valid rule with one upsert', async () => {
		const saved = ruleRow('test-meer', {
			min_kn: 14,
			weekdays: [6, 7],
			earliest_local: '17:00:00'
		});
		fake.current.respond('alert_rules', { data: saved, error: null });
		draw();
		const user = userEvent.setup();
		await user.type(field('Minimale wind (kn)'), '14');
		for (const d of ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag']) {
			await user.click(screen.getByRole('checkbox', { name: d }));
		}
		await user.selectOptions(field('Vanaf (lokale tijd)'), '17:00');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByText('Opgeslagen.')).toBeInTheDocument();
		expect(fake.current.calls).toHaveLength(1);
		expect(fake.current.calls[0]).toEqual({
			table: 'alert_rules',
			ops: [
				[
					'upsert',
					{
						user_id: USER_ID,
						spot_id: 'test-meer',
						enabled: true,
						min_kn: 14,
						max_kn: null,
						dir_classes: null,
						weekdays: [6, 7],
						earliest_local: '17:00:00',
						latest_local: null,
						min_go_hours: null,
						days_ahead: null
					},
					{ onConflict: 'user_id,spot_id' }
				],
				['select', ALERT_RULE_COLUMNS.join(',')],
				['single']
			]
		});
		expect(onsaved).toHaveBeenCalledWith(saved);
	});

	it('shows the profile hint in empty fields', () => {
		draw();
		expect(screen.getByText('standaard: 14 kn (je profiel)')).toBeInTheDocument();
	});

	it('offers no 00:00 or 24:00 and no day 7 by default', () => {
		draw();
		expect(optionValues(field('Tot (lokale tijd)'))).not.toContain('00:00');
		expect(optionValues(field('Tot (lokale tijd)'))).not.toContain('24:00');
		expect(optionValues(field('Dagen vooruit (na vandaag)'))).toEqual(['', '0', '1', '2', '3', '4', '5', '6']);
	});

	it('offers day 7 when the row already has it', () => {
		draw(ruleRow('test-meer', { days_ahead: 7 }));
		expect(optionValues(field('Dagen vooruit (na vandaag)'))).toContain('7');
	});

	it('reset deletes the rule', async () => {
		draw(ruleRow('test-meer', { min_kn: 18 }));
		await userEvent.setup().click(screen.getByRole('button', { name: 'Standaardinstellingen' }));
		expect(await screen.findByText('Standaardinstellingen hersteld.')).toBeInTheDocument();
		expect(fake.current.calls).toEqual([
			{
				table: 'alert_rules',
				ops: [['delete'], ['eq', 'user_id', USER_ID], ['eq', 'spot_id', 'test-meer']]
			}
		]);
		expect(onsaved).toHaveBeenCalledWith(null);
	});

	it('has no reset button without a stored rule', () => {
		draw();
		expect(screen.queryByRole('button', { name: 'Standaardinstellingen' })).toBeNull();
	});

	it('reports a removed favorite (23503)', async () => {
		fake.current.respond('alert_rules', { data: null, error: { code: '23503' } });
		draw();
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(
			await screen.findByText('Deze spot staat niet meer in je favorieten. Herlaad de pagina.')
		).toBeInTheDocument();
		expect(onsaved).not.toHaveBeenCalled();
	});

	it('reports a generic save failure', async () => {
		fake.current.respond('alert_rules', { data: null, error: { code: '42501' } });
		draw();
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByText('Opslaan is niet gelukt. Probeer het opnieuw.')).toBeInTheDocument();
	});

	it('B-1/E24: choosing Vanaf after Tot does not crash; Opslaan reports timeOrder', async () => {
		const spy = vi.fn();
		window.addEventListener('error', spy);
		try {
			draw(ruleRow('test-meer', { latest_local: '17:00:00' }));
			const user = userEvent.setup();
			await user.selectOptions(field('Vanaf (lokale tijd)'), '19:00');
			expect(screen.getByRole('button', { name: 'Opslaan' })).toBeInTheDocument();
			expect(screen.getByText('standaard: 14 kn (je profiel)')).toBeInTheDocument();
			await user.click(screen.getByRole('button', { name: 'Opslaan' }));
			expect(screen.getByText('"Tot" moet later zijn dan "Vanaf".')).toBeInTheDocument();
			expect(screen.getByRole('alert')).toHaveTextContent(
				'Niet opgeslagen: controleer de gemarkeerde velden.'
			);
			expect(writeCalls(fake.current.calls)).toHaveLength(0);
			expect(spy).not.toHaveBeenCalled();
		} finally {
			window.removeEventListener('error', spy);
		}
	});
});
