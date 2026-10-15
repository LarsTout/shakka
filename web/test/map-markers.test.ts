import { describe, expect, it } from 'vitest';
import { createMarkerElement, initialView, markerModels } from '../src/lib/map/markers.js';
import type { SpotSummary } from '../src/lib/types.js';
import { MAP_SPOTS, MAP_SUMMARIES, SPOT_NO_COORDS } from './fixtures/map-data.js';
import { SPOT_VERIFIED } from './fixtures/spot-data.js';

describe('markerModels', () => {
	const { markers, withoutCoords } = markerModels(MAP_SPOTS, MAP_SUMMARIES);

	it('keeps spot order and counts spots without coordinates', () => {
		expect(withoutCoords).toBe(1);
		expect(markers.map((m) => m.id)).toEqual(['test-strand', 'test-meer', 'test-avond']);
	});

	it('spot without summary gets the grey badge', () => {
		expect(markers[0]).toMatchObject({
			verdict: null,
			day: null,
			badge: 'Nog geen data',
			unverified: true,
			href: '/spot/test-strand',
			lon: 4.57,
			lat: 52.47
		});
	});

	it('uses today.best, then tomorrow.best with prefix', () => {
		expect(markers[1]).toMatchObject({ verdict: 'go', day: 'today', badge: 'Go', unverified: false });
		expect(markers[2]).toMatchObject({ verdict: 'marginal', day: 'tomorrow', badge: 'Morgen: Twijfel' });
	});

	it('counts invalid coordinates as without', () => {
		for (const bad of [{ lat: 95 }, { lon: NaN }, { lon: null }]) {
			const r = markerModels([{ ...SPOT_VERIFIED, ...bad }], {});
			expect(r.markers).toEqual([]);
			expect(r.withoutCoords).toBe(1);
		}
		expect(markerModels([SPOT_NO_COORDS], {}).withoutCoords).toBe(1);
	});

	it('empty summary days give no data', () => {
		const empty: SpotSummary = {
			spot_id: 'test-meer',
			today: { date: 'a', go: 0, marginal: 0, no_go: 0, best: null, first_go_at: null },
			tomorrow: { date: 'b', go: 0, marginal: 0, no_go: 0, best: null, first_go_at: null },
			latest_evaluated_at: 'x'
		};
		expect(markerModels([SPOT_VERIFIED], { 'test-meer': empty }).markers[0]!.badge).toBe('Nog geen data');
	});
});

describe('initialView', () => {
	it('centres on the Netherlands without markers', () => {
		expect(initialView([])).toEqual({ kind: 'center', center: [5.3, 52.2], zoom: 6.5 });
	});

	it('widens the bounds around all markers', () => {
		const v = initialView(markerModels(MAP_SPOTS, MAP_SUMMARIES).markers);
		if (v.kind !== 'bounds') throw new Error('expected bounds');
		expect(v.bounds[0][0]).toBeCloseTo(4.15);
		expect(v.bounds[0][1]).toBeCloseTo(52.05);
		expect(v.bounds[1][0]).toBeCloseTo(4.62);
		expect(v.bounds[1][1]).toBeCloseTo(52.52);
	});

	it('single marker is never a degenerate box', () => {
		const v = initialView(markerModels([SPOT_VERIFIED], {}).markers);
		if (v.kind !== 'bounds') throw new Error('expected bounds');
		expect(v.bounds[1][0] - v.bounds[0][0]).toBeCloseTo(0.1);
	});
});

describe('createMarkerElement', () => {
	const models = markerModels(MAP_SPOTS, MAP_SUMMARIES).markers;

	it('renders a verified marker with a verdict badge', () => {
		const el = createMarkerElement(models[1]!, document);
		expect(el.tagName).toBe('A');
		expect(el.getAttribute('href')).toBe('/spot/test-meer');
		expect(el.getAttribute('data-marker-spot')).toBe('test-meer');
		expect(el.hasAttribute('data-spot')).toBe(false);
		expect(el.getAttribute('data-verdict')).toBe('go');
		expect(el.querySelector('.map-marker-name')?.textContent).toBe('Testmeer');
		expect(el.querySelector('.verdict.verdict-go')?.textContent).toBe('Go');
		expect(el.querySelector('.sr-only')).toBeNull();
	});

	it('renders an unverified marker without data', () => {
		const el = createMarkerElement(models[0]!, document);
		expect(el.getAttribute('data-verdict')).toBe('none');
		expect(el.querySelector('.verdict-none')?.textContent).toBe('Nog geen data');
		expect(el.classList.contains('map-marker-unverified')).toBe(true);
		expect(el.querySelector('.sr-only')?.textContent).toBe(' (niet geverifieerd)');
	});

	it('never turns a name into HTML', () => {
		const el = createMarkerElement({ ...models[1]!, name: '<img src=x onerror=alert(1)>' }, document);
		expect(el.querySelector('img')).toBeNull();
		expect(el.textContent).toContain('<img src=x onerror=alert(1)>');
	});
});
