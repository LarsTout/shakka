import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DayTimeline from '../src/lib/components/DayTimeline.svelte';
import type { Timeline } from '../src/lib/timeline.js';

const TL: Timeline = {
	slots: ['go', 'none', 'marginal', 'outside'],
	ticks: [
		{ pos: 0, label: '09' },
		{ pos: 0.5, label: '12' }
	],
	markers: [{ pos: 0.25, label: 'LW 10:00', kind: 'low', row: 0 }],
	window: { from: 0.25, to: 0.75 }
};
const draw = (size?: 'sm' | 'md' | 'lg') => render(DayTimeline, { timeline: TL, size });

describe('DayTimeline', () => {
	it('renders one slot per hour with kind classes', () => {
		draw();
		const slots = [...document.querySelectorAll('.slot')];
		expect(slots.map((s) => [...s.classList].find((c) => c.startsWith('slot-')))).toEqual([
			'slot-go',
			'slot-none',
			'slot-marginal',
			'slot-outside'
		]);
	});
	it('is aria-hidden', () => {
		draw();
		expect(document.querySelector('.timeline')).toHaveAttribute('aria-hidden', 'true');
	});
	it('sm has no ticks', () => {
		draw('sm');
		expect(document.querySelector('.timeline-ticks')).toBeNull();
		draw('md');
		expect(document.querySelectorAll('.timeline-tick')).toHaveLength(2);
	});
	it('markers only for lg', () => {
		const { unmount } = draw('md');
		expect(document.querySelector('.timeline-marker')).toBeNull();
		unmount();
		draw('lg');
		expect(document.querySelector('.timeline-marker')).toHaveTextContent('LW 10:00');
	});
	it('window element with left/width', () => {
		draw('lg');
		const w = document.querySelector('.timeline-window') as HTMLElement;
		expect(w.style.left).toBe('25%');
		expect(w.style.width).toBe('50%');
	});
});
