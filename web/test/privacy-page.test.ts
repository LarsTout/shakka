import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import {
	ALERT_STATE_RETENTION_HOURS,
	FORECAST_RETENTION_HOURS,
	RETURN_TO_TTL_MINUTES
} from '../src/lib/privacy.js';
import { SESSION_RETENTION_DAYS } from '../src/lib/rsvp-types.js';
import Page from '../src/routes/privacy/+page.svelte';

const norm = (t: string | null | undefined) => (t ?? '').replace(/\s+/g, ' ');
const bodyText = () => norm(document.body.textContent);
const PRIVACY_MD = readFileSync(resolve(process.cwd(), '../docs/PRIVACY.md'), 'utf8')  // jsdom's URL cannot make file URLs;

describe('/privacy', () => {
	it('has the h1 and the document title', () => {
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Privacy' })).toBeInTheDocument();
		expect(document.title).toBe('Privacy · Shakka');
	});
	it('names the data and the parties', () => {
		render(Page);
		const text = bodyText().toLowerCase();
		for (const w of [
			'e-mailadres',
			'voornaam',
			'profiel',
			'push-abonnementen',
			'supabase',
			'cloudflare',
			'github',
			'maptiler',
			'apple',
			'google'
		]) {
			expect(text).toContain(w);
		}
	});
	it('names quiet hours as profile data', () => {
		render(Page);
		expect(bodyText().toLowerCase()).toContain('stille uren');
	});
	it('PRIVACY.md profile row lists the quiet columns', () => {
		const row = PRIVACY_MD.split('\n').find((l) => l.startsWith('| Profiel |'));
		expect(row).toBeDefined();
		expect(row).toContain('`quiet_from`');
		expect(row).toContain('`quiet_until`');
	});
	it('shows the retention periods from the constants', () => {
		render(Page);
		const text = bodyText();
		expect(text).toContain(`${FORECAST_RETENTION_HOURS} uur`);
		expect(text).toContain(`${ALERT_STATE_RETENTION_HOURS} uur`);
		expect(text).toContain(`${SESSION_RETENTION_DAYS} dagen`);
	});
	it('describes shakka:return_to exactly (B-1a, N-2)', () => {
		render(Page);
		const text = bodyText();
		expect(text).toContain('gewist zodra je op dit apparaat inlogt');
		expect(text).toContain(
			`na ${RETURN_TO_TTL_MINUTES} minuten niet meer, en wist het de eerstvolgende keer dat je Shakka opent`
		);
		expect(text).not.toMatch(/hoogstens\s*\d+\s*minuten/i);
	});
	it('lists what the hourly job reads (B-1b)', () => {
		render(Page);
		const item = screen.getAllByRole('listitem').find((li) => li.textContent?.includes('GitHub'));
		expect(norm(item?.textContent)).toContain(
			'profiel, favorieten, alertinstellingen, push-abonnementen en welke alerts je al kreeg'
		);
	});
	it('has the legal basis section (N-7)', () => {
		render(Page);
		expect(screen.getByRole('heading', { level: 2, name: 'Waarom Shakka dit mag' })).toBeInTheDocument();
		const text = bodyText();
		expect(text).toContain('dienst te leveren die je zelf aanvraagt');
		expect(text).toContain('vraagt daarom niet om toestemming voor cookies');
	});
	it('mentions browser-managed storage (N-8)', () => {
		render(Page);
		const text = bodyText();
		expect(text).toContain('kaarttegels');
		expect(text).toContain('scrollpositie');
	});
	it('does not mention telegram', () => {
		render(Page);
		expect(bodyText()).not.toMatch(/telegram/i);
	});
	it('links to /profiel', () => {
		render(Page);
		expect(screen.getAllByRole('link').some((a) => a.getAttribute('href') === '/profiel')).toBe(true);
	});
	it('opens the Autoriteit Persoonsgegevens link safely', () => {
		render(Page);
		const a = screen.getByRole('link', { name: 'Autoriteit Persoonsgegevens' });
		expect(a).toHaveAttribute('href', 'https://autoriteitpersoonsgegevens.nl/');
		expect(a.getAttribute('rel')).toContain('noopener');
	});
	it('has no mailto link while the contact address is null', () => {
		render(Page);
		expect(screen.getAllByRole('link').some((a) => a.getAttribute('href')?.startsWith('mailto:'))).toBe(false);
		expect(bodyText()).toContain('Neem contact op met de beheerder van Shakka');
	});
});

describe('docs/PRIVACY.md agrees with /privacy (4e)', () => {
	it('lists what the GitHub Actions job reads', () => {
		const line = PRIVACY_MD.split('\n').map((l) => l.trim()).find((l) => l.startsWith('- GitHub Actions:'));
		expect(line).toBeDefined();
		for (const w of ['profielen', 'favorieten', 'alertregels', 'push-abonnementen', '`alert_state`']) {
			expect(line).toContain(w);
		}
	});
	it('describes shakka:return_to with pruneReturnTo and takeReturnTo', () => {
		const row = PRIVACY_MD.split('\n').find((l) => l.includes('`shakka:return_to`'));
		expect(row).toBeDefined();
		expect(row).toContain('pruneReturnTo');
		expect(row).toContain('takeReturnTo');
		expect(row).not.toContain('hoogstens');
	});
	it('inventories sessionStorage', () => {
		expect(PRIVACY_MD).toContain('sessionStorage');
		expect(PRIVACY_MD).toContain('sveltekit:history-info');
		expect(PRIVACY_MD).toContain('sveltekit:navigation-snapshot');
	});
});
