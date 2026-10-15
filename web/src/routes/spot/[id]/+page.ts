import { loadSpotPage } from '#lib/page-data.js';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => loadSpotPage(params.id, new Date());
