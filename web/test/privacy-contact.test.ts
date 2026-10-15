import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

// Separate file: vi.mock applies per file (E19, a contact address is chosen).
vi.mock('#lib/privacy.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('../src/lib/privacy.js')>()),
	PRIVACY_CONTACT_EMAIL: 'privacy@example.test'
}));

import Page from '../src/routes/privacy/+page.svelte';

describe('/privacy with a contact address', () => {
	it('shows a mailto link and not the generic sentence', () => {
		render(Page);
		expect(screen.getByRole('link', { name: 'privacy@example.test' })).toHaveAttribute(
			'href',
			'mailto:privacy@example.test'
		);
		expect(document.body.textContent).not.toContain('Neem contact op met de beheerder');
	});
});
