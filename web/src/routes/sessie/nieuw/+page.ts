import { parseNewSessionParams } from '#lib/go.js';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => ({ params: parseNewSessionParams(url) });
