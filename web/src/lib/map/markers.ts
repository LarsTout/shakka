import { verdictLabel } from '../labels.js';
import type { Spot, SpotSummary, Verdict } from '../types.js';
import { BOUNDS_MARGIN_DEG, NL_CENTER, NL_ZOOM } from './config.js';

export interface MarkerModel {
	id: string;
	name: string;
	lon: number;
	lat: number;
	verdict: Verdict | null; // null -> grey "Nog geen data"
	day: 'today' | 'tomorrow' | null;
	badge: string; // 'Go' | 'Morgen: Twijfel' | 'Nog geen data'
	unverified: boolean;
	href: string;
}

const NO_DATA = 'Nog geen data';

function hasCoords(spot: Spot): spot is Spot & { lat: number; lon: number } {
	const { lat, lon } = spot;
	return (
		typeof lat === 'number' &&
		typeof lon === 'number' &&
		Number.isFinite(lat) &&
		Number.isFinite(lon) &&
		Math.abs(lat) <= 90 &&
		Math.abs(lon) <= 180
	);
}

function describe(summary: SpotSummary | undefined): Pick<MarkerModel, 'verdict' | 'day' | 'badge'> {
	if (summary?.today.best) {
		return { verdict: summary.today.best, day: 'today', badge: verdictLabel(summary.today.best) };
	}
	if (summary?.tomorrow.best) {
		return {
			verdict: summary.tomorrow.best,
			day: 'tomorrow',
			badge: `Morgen: ${verdictLabel(summary.tomorrow.best)}`
		};
	}
	return { verdict: null, day: null, badge: NO_DATA };
}

/** In spot order. Skips spots whose lat/lon is null, not finite, |lat| > 90 or |lon| > 180 (counted in withoutCoords). */
export function markerModels(
	spots: readonly Spot[],
	summaries: Readonly<Record<string, SpotSummary>>
): { markers: MarkerModel[]; withoutCoords: number } {
	const markers: MarkerModel[] = [];
	let withoutCoords = 0;
	for (const spot of spots) {
		if (!hasCoords(spot)) {
			withoutCoords += 1;
			continue;
		}
		markers.push({
			id: spot.id,
			name: spot.name,
			lon: spot.lon,
			lat: spot.lat,
			...describe(summaries[spot.id]),
			unverified: !spot.verified,
			href: `/spot/${encodeURIComponent(spot.id)}`
		});
	}
	return { markers, withoutCoords };
}

export type InitialView =
	| { kind: 'bounds'; bounds: [[number, number], [number, number]] } // [[minLon, minLat], [maxLon, maxLat]]
	| { kind: 'center'; center: [number, number]; zoom: number };

/** No markers -> NL view. Otherwise min/max over all markers, widened by BOUNDS_MARGIN_DEG on each side. */
export function initialView(markers: readonly MarkerModel[]): InitialView {
	if (markers.length === 0) return { kind: 'center', center: NL_CENTER, zoom: NL_ZOOM };
	const lons = markers.map((m) => m.lon);
	const lats = markers.map((m) => m.lat);
	return {
		kind: 'bounds',
		bounds: [
			[Math.min(...lons) - BOUNDS_MARGIN_DEG, Math.min(...lats) - BOUNDS_MARGIN_DEG],
			[Math.max(...lons) + BOUNDS_MARGIN_DEG, Math.max(...lats) + BOUNDS_MARGIN_DEG]
		]
	};
}

/** Built with createElement and textContent only. Never sets data-spot (reserved for li.spot-item). */
export function createMarkerElement(model: MarkerModel, doc: Document): HTMLAnchorElement {
	const a = doc.createElement('a');
	a.className = model.unverified ? 'map-marker map-marker-unverified' : 'map-marker';
	a.setAttribute('href', model.href);
	a.setAttribute('data-marker-spot', model.id);
	a.setAttribute('data-verdict', model.verdict ?? 'none');
	const name = doc.createElement('span');
	name.className = 'map-marker-name';
	name.textContent = model.name;
	const badge = doc.createElement('span');
	badge.className = `verdict verdict-${model.verdict ?? 'none'}`;
	badge.textContent = model.badge;
	a.append(name, badge);
	if (model.unverified) {
		const sr = doc.createElement('span');
		sr.className = 'sr-only';
		sr.textContent = ' (niet geverifieerd)';
		a.append(sr);
	}
	return a;
}
