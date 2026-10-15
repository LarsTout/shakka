import type { PageLoad } from './$types';

export const load: PageLoad = ({ params, url }) => ({ slug: params.slug, origin: url.origin });
