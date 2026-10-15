import { loadPublicSessionPage } from '#lib/public-session-data.js';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => loadPublicSessionPage(params.slug, new Date());
