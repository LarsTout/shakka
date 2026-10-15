import { redirect } from '@sveltejs/kit';
import { newSessionHref } from '#lib/go.js';
import { parseGoParams } from '#lib/time.js';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	const p = parseGoParams(url);
	if (!p) redirect(307, '/');
	return { returnPath: url.pathname + url.search, target: newSessionHref(p) };
};
