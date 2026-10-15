import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Attribution from '#lib/components/Attribution.svelte';

describe.each([false, true])('Attribution compact=%s', (compact) => {
	it('links Open-Meteo and the CC BY 4.0 licence', () => {
		render(Attribution, { compact });
		const links = screen.getAllByRole('link');
		const om = links.find((a) => a.getAttribute('href') === 'https://open-meteo.com/');
		expect(om?.textContent).toContain('Open-Meteo');
		expect(links.some((a) => a.getAttribute('href') === 'https://creativecommons.org/licenses/by/4.0/')).toBe(true);
	});
	it('names all sources', () => {
		const { container } = render(Attribution, { compact });
		for (const name of ['KNMI', 'DWD', 'ECMWF', 'NOAA', 'Rijkswaterstaat']) {
			expect(container.textContent).toContain(name);
		}
	});
	it('opens links safely', () => {
		render(Attribution, { compact });
		for (const a of screen.getAllByRole('link')) expect(a.getAttribute('rel')).toContain('noopener');
	});
});

describe('Attribution wave models (A18)', () => {
	it('the full variant names the wave models', () => {
		const { container } = render(Attribution, { compact: false });
		expect(container.textContent?.replace(/\s+/g, ' ')).toContain('golfmodellen van DWD en ECMWF');
	});
});
