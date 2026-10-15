import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SessionForm from '../src/lib/components/SessionForm.svelte';
import { SESSION_FORM_MESSAGES as M, type SessionFormValues } from '../src/lib/session-form.js';
import { NOW_SESSIONS, validForm } from './fixtures/session-data.js';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';

const onsave = vi.fn(async (_v: unknown): Promise<string | null> => null);

beforeEach(() => {
	vi.clearAllMocks();
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW_SESSIONS));
});
afterEach(() => vi.useRealTimers());

function draw(initial: SessionFormValues = validForm(), mode: 'create' | 'edit' = 'create') {
	return render(SessionForm, {
		mode,
		idPrefix: 'new',
		spots: [SPOT_UNVERIFIED, SPOT_VERIFIED],
		initial,
		preferred: null,
		onsave
	});
}
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const set = (label: string, value: string) => fireEvent.input(field(label), { target: { value } });
const submit = () => fireEvent.click(screen.getByRole('button', { name: /Sessie aanmaken|Wijzigingen opslaan/ }));

async function refused(label: string, message: string) {
	await submit();
	expect(onsave).not.toHaveBeenCalled();
	expect(screen.getByText(message, { selector: '.form-field p.error' })).toBeInTheDocument();
	expect(screen.getByRole('alert')).toHaveTextContent(M.summary);
	expect(field(label)).toHaveAttribute('aria-invalid', 'true');
	expect(field(label).getAttribute('aria-describedby')).toContain('-error');
}

describe('SessionForm (AC-4)', () => {
	it('(a) end equal to start', async () => {
		draw();
		await set('Tot', '14:00');
		await refused('Tot', M.endBeforeStart);
	});
	it('(b) end before start', async () => {
		draw();
		await set('Tot', '13:00');
		await refused('Tot', M.endBeforeStart);
	});
	it('(c) seats 9', async () => {
		draw();
		await set('Vrije plekken in je auto (optioneel)', '9');
		await refused('Vrije plekken in je auto (optioneel)', M.seatsFree);
	});
	it('(d) Tikkie http and a foreign host', async () => {
		draw();
		await set('Tikkie-link (optioneel)', 'http://tikkie.me/x');
		await refused('Tikkie-link (optioneel)', M.tikkieUrl);
		await set('Tikkie-link (optioneel)', 'https://example.org/pay/x');
		await refused('Tikkie-link (optioneel)', M.tikkieUrl);
	});
	it('(e) name of 31 characters', async () => {
		draw();
		await set('Je voornaam', 'a'.repeat(31));
		await refused('Je voornaam', M.organizerName);
	});
	it('(f) a valid form calls onsave once', async () => {
		draw();
		await submit();
		expect(onsave).toHaveBeenCalledTimes(1);
		expect(onsave).toHaveBeenCalledWith({
			spot_id: 'test-strand',
			organizer_name: 'Lars',
			starts_at: '2026-07-18T12:00:00.000Z',
			ends_at: '2026-07-18T16:00:00.000Z',
			note: null,
			seats_free: null,
			departure_point: null,
			tikkie_url: null
		});
	});
	it('(g) shows the message from onsave', async () => {
		onsave.mockResolvedValueOnce('X');
		draw();
		await submit();
		expect(await screen.findByRole('alert')).toHaveTextContent('X');
	});
	it('(i) edit mode', () => {
		draw(validForm(), 'edit');
		expect(screen.getByRole('button', { name: 'Wijzigingen opslaan' })).toBeInTheDocument();
		expect(screen.getByText(/Deelnemers krijgen geen bericht/)).toBeInTheDocument();
	});
	it('(j) date bounds and range error', async () => {
		draw();
		expect(field('Datum')).toHaveAttribute('min', '2026-07-15');
		expect(field('Datum')).toHaveAttribute('max', '2027-07-15');
		await set('Datum', '2026-07-14');
		await refused('Datum', M.dateRange);
	});
});
