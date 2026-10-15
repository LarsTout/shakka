import { redirect } from '@sveltejs/kit';
import { goTarget } from '#lib/go.js';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	redirect(307, goTarget(url));
};
