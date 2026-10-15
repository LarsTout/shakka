import { parseGoParams } from './time.js';

/** '/spot/' + encodeURIComponent(spot) for valid params, otherwise '/'. */
export function goTarget(url: URL): string {
	const p = parseGoParams(url);
	return p ? `/spot/${encodeURIComponent(p.spot)}` : '/';
}
