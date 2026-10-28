import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PROFILE_FULL } from './fixtures/user-data.js';
import { USER_ID } from './helpers/fake-session.js';

const update = vi.hoisted(() => vi.fn());
vi.mock('#lib/user-data.js', () => ({ updateQuietHours: update }));

import QuietHoursSettings from '../src/lib/components/QuietHoursSettings.svelte';
import type { Profile } from '../src/lib/types.js';

const onsaved = vi.fn();
const NIGHT: Profile = { ...PROFILE_FULL, quiet_from: '22:00:00', quiet_until: '07:00:00' };
const draw = (profile: Profile | null = PROFILE_FULL) =>
	render(QuietHoursSettings, { userId: USER_ID, profile, onsaved });
const from = () => screen.getByLabelText('Van') as HTMLSelectElement;
const until = () => screen.getByLabelText('Tot') as HTMLSelectElement;

beforeEach(() => {
	vi.clearAllMocks();
});

describe('QuietHoursSettings', () => {
	it('shows the stored hours', () => {
		draw(NIGHT);
		expect(screen.getByRole('heading', { name: 'Stille uren' })).toBeInTheDocument();
		expect(from().value).toBe('22:00');
		expect(until().value).toBe('07:00');
		expect(
			screen.getByText('Elke dag van 22:00 tot 07:00 (de volgende dag) geen alerts.')
		).toBeInTheDocument();
	});

	it('offers one empty option and a stored non-whole hour', () => {
		draw({ ...NIGHT, quiet_from: '22:30:00' });
		const values = [...from().querySelectorAll('option')].map((o) => o.value);
		expect(values.filter((v) => v === '')).toHaveLength(1);
		expect(values).toContain('22:30');
		expect(from().value).toBe('22:30');
	});

	it('"Uit" writes null for both columns', async () => {
		update.mockResolvedValue(PROFILE_FULL);
		draw(NIGHT);
		await userEvent.setup().click(screen.getByRole('button', { name: 'Uit' }));
		expect(update).toHaveBeenCalledTimes(1);
		expect(update).toHaveBeenCalledWith(USER_ID, { quiet_from: null, quiet_until: null });
		expect(from().value).toBe('');
		expect(until().value).toBe('');
		expect(onsaved).toHaveBeenCalledWith(PROFILE_FULL);
		expect(await screen.findByRole('status')).toHaveTextContent('Stille uren staan uit.');
	});

	it('equal times show a Dutch error without writing', async () => {
		draw();
		const user = userEvent.setup();
		await user.selectOptions(from(), '22:00');
		await user.selectOptions(until(), '22:00');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByRole('alert')).toHaveTextContent(
			'Begin en einde van de stille uren mogen niet gelijk zijn.'
		);
		expect(update).not.toHaveBeenCalled();
	});

	it('one empty time shows a Dutch error without writing', async () => {
		draw();
		const user = userEvent.setup();
		await user.selectOptions(from(), '22:00');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByRole('alert')).toHaveTextContent(
			'Kies een begin- én een eindtijd, of zet stille uren uit.'
		);
		expect(update).not.toHaveBeenCalled();
	});

	it('a valid choice writes only the two columns', async () => {
		const saved = { ...PROFILE_FULL, quiet_from: '22:00:00', quiet_until: '07:00:00' };
		update.mockResolvedValue(saved);
		draw();
		const user = userEvent.setup();
		await user.selectOptions(from(), '22:00');
		await user.selectOptions(until(), '07:00');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(update).toHaveBeenCalledWith(USER_ID, {
			quiet_from: '22:00:00',
			quiet_until: '07:00:00'
		});
		expect(onsaved).toHaveBeenCalledWith(saved);
		expect(await screen.findByRole('status')).toHaveTextContent('Opgeslagen.');
	});

	it('an unchanged non-whole hour is written back unchanged', async () => {
		const odd = { ...NIGHT, quiet_from: '22:30:00' };
		update.mockResolvedValue(odd);
		draw(odd);
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(update).toHaveBeenCalledWith(USER_ID, {
			quiet_from: '22:30:00',
			quiet_until: '07:00:00'
		});
	});

	it('a failed save shows an error and keeps the values', async () => {
		update.mockRejectedValue(new Error('42501'));
		draw(NIGHT);
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(
			'Opslaan is niet gelukt. Probeer het opnieuw.'
		);
		expect(from().value).toBe('22:00');
		expect(until().value).toBe('07:00');
		expect(onsaved).not.toHaveBeenCalled();
	});

	it('without a profile there is no form', () => {
		draw(null);
		expect(
			screen.getByText('Stille uren kun je instellen zodra je profiel is aangemaakt.')
		).toBeInTheDocument();
		expect(screen.queryByLabelText('Van')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
	});
});
