import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import HourVerdict from '../src/lib/components/HourVerdict.svelte';
import { EVAL_GO, EVAL_OFFSHORE } from './fixtures/spot-data.js';

describe('HourVerdict', () => {
	it('renders a go hour', () => {
		const { container } = render(HourVerdict, { evaluation: EVAL_GO });
		const time = screen.getByText('14:00', { selector: 'time' });
		expect(time).toHaveAttribute('datetime', '2026-07-15T12:00:00+00:00');
		expect(screen.getByText('Go')).toBeInTheDocument();
		expect(screen.getByText('18 kn, vlagen 24 kn')).toBeInTheDocument();
		expect(screen.getByText(/Wind uit WZW \(250°\)/)).toBeInTheDocument();
		expect(screen.getByText('Aanlandig')).toBeInTheDocument();
		expect(screen.getByText('Betrouwbaarheid: Hoog')).toBeInTheDocument();
		expect(container.querySelector('ul.reasons')).toBeNull();
		expect(container.querySelector('svg g[transform]')).toHaveAttribute('transform', 'rotate(70 16 16)');
	});

	it('renders an offshore hour with labels, never raw codes', () => {
		const { container } = render(HourVerdict, { evaluation: EVAL_OFFSHORE });
		expect(container.querySelector('[data-verdict="no_go"]')).toHaveTextContent('Niet gaan');
		expect(screen.getByText('Aflandig')).toBeInTheDocument();
		expect(screen.getByText('Aflandige wind: niet kiten')).toBeInTheDocument();
		expect(screen.queryByText('offshore')).toBeNull();
	});

	it('renders unknowns', () => {
		const { container } = render(HourVerdict, {
			evaluation: {
				...EVAL_GO,
				dir_deg: null,
				dir_class: null,
				confidence: null,
				wind_kn: null,
				reasons: ['no_data', 'direction_unknown'],
				verdict: 'no_go'
			}
		});
		expect(screen.getByText('Wind onbekend')).toBeInTheDocument();
		expect(screen.getByText(/Richting onbekend/)).toBeInTheDocument();
		expect(screen.getByText('Richtingsklasse onbekend')).toBeInTheDocument();
		expect(screen.getByText('Betrouwbaarheid: onbekend')).toBeInTheDocument();
		expect(container.querySelector('svg g[transform]')).toBeNull();
	});
});
