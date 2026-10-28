import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { verdictLabel } from '../src/lib/labels.js';
import VerdictBadge from '../src/lib/components/VerdictBadge.svelte';

describe('VerdictBadge', () => {
	it('lg: size class, data attribute and label', () => {
		const { container } = render(VerdictBadge, { verdict: 'go', size: 'lg' });
		const el = container.querySelector('span') as HTMLElement;
		expect(el).toHaveClass('verdict', 'verdict-go', 'verdict-lg');
		expect(el).toHaveAttribute('data-verdict', 'go');
		expect(el).toHaveTextContent(verdictLabel('go'));
	});
	it('default: no verdict-lg', () => {
		const { container } = render(VerdictBadge, { verdict: 'no_go' });
		const el = container.querySelector('span') as HTMLElement;
		expect(el).toHaveClass('verdict', 'verdict-no_go');
		expect(el).not.toHaveClass('verdict-lg');
	});
});
