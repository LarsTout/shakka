import { render, screen } from '@testing-library/svelte';
import { describe, it } from 'vitest';
import Over from '../src/routes/over/+page.svelte';
import Privacy from '../src/routes/privacy/+page.svelte';
import { expectNoSeriousViolations } from './helpers/axe.js';

describe('a11y: static pages', () => {
	it('/privacy', async () => {
		render(Privacy);
		await screen.findByRole('heading', { level: 1, name: 'Privacy' });
		await expectNoSeriousViolations();
	});
	it('/over', async () => {
		render(Over);
		await screen.findByRole('heading', { level: 1, name: 'Over Shakka' });
		await expectNoSeriousViolations();
	});
});
