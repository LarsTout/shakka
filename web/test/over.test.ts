import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Over from '../src/routes/over/+page.svelte';

describe('over page', () => {
	it('renders the heading and the full attribution', () => {
		render(Over);
		expect(screen.getByRole('heading', { level: 1, name: 'Over Shakka' })).toBeInTheDocument();
		expect(
			screen.getAllByRole('link').some((a) => a.getAttribute('href') === 'https://open-meteo.com/')
		).toBe(true);
	});
	it('links to the privacy statement', () => {
		render(Over);
		expect(screen.getAllByRole('link').some((a) => a.getAttribute('href') === '/privacy')).toBe(true);
	});
});
