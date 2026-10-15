import { compassLabel, formatKn } from './labels.js';
import type { MarineHour } from './types.js';
import { STALE_AFTER_MS } from './view.js';

/** Wave rows older than this (fetched_at) are not shown (A9). */
export const MARINE_STALE_AFTER_MS = STALE_AFTER_MS;

export const WAVES_NOTE_NL =
	'Golven zijn een modelverwachting (Open-Meteo Marine, DWD en ECMWF), minder nauwkeurig vlak bij de kust en op binnenwater. Ze tellen niet mee in het oordeel.';

/** One decimal with a comma: Math.floor(x * 10 + 0.5) / 10 via toFixed(1), e.g. 1.24 -> '1,2', 0 -> '0,0'. */
export function formatMeters(x: number): string {
	return (Math.floor(x * 10 + 0.5) / 10).toFixed(1).replace('.', ',');
}

/** 'Golven 1,2 m, periode 5 s, uit WZW (250°)'. Unknown parts are spelled out. */
export function waveText(
	m: Pick<MarineHour, 'wave_height_m' | 'wave_period_s' | 'wave_dir_deg'>
): string {
	const h = m.wave_height_m === null ? 'hoogte onbekend' : `${formatMeters(m.wave_height_m)} m`;
	const p = m.wave_period_s === null ? 'periode onbekend' : `periode ${formatKn(m.wave_period_s)} s`;
	const d =
		m.wave_dir_deg === null
			? 'richting onbekend'
			: `uit ${compassLabel(m.wave_dir_deg)} (${Math.round(m.wave_dir_deg)}°)`;
	return `Golven ${h}, ${p}, ${d}`;
}

/** Map from Date.parse(valid_at) to the row. Skips rows with an unparseable valid_at or fetched_at,
 *  rows with now - fetched_at > MARINE_STALE_AFTER_MS (strict; exactly 3 h is still shown),
 *  and rows with all three values null. Later rows with the same hour overwrite earlier ones. */
export function marineByHour(rows: readonly MarineHour[], now: Date): Map<number, MarineHour> {
	const out = new Map<number, MarineHour>();
	for (const row of rows) {
		const at = Date.parse(row.valid_at);
		const fetched = Date.parse(row.fetched_at);
		if (Number.isNaN(at) || Number.isNaN(fetched)) continue;
		if (now.getTime() - fetched > MARINE_STALE_AFTER_MS) continue;
		if (row.wave_height_m === null && row.wave_period_s === null && row.wave_dir_deg === null) {
			continue;
		}
		out.set(at, row);
	}
	return out;
}
