import { loadSpotList } from '#lib/page-data.js';
import type { PageLoad } from './$types';

export const load: PageLoad = () => loadSpotList(new Date());
