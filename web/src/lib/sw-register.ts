export const SERVICE_WORKER_URL = '/service-worker.js';

export interface ServiceWorkerHost {
	serviceWorker?: Pick<ServiceWorkerContainer, 'register'>;
}

/** Registers the SvelteKit service worker as a module. No-op (null) when disabled
 *  (dev/test), when nav is undefined, or when service workers are unsupported.
 *  Registration errors are caught (console.warn) and give null; never throws. */
export async function registerServiceWorker(
	nav: ServiceWorkerHost | undefined,
	enabled: boolean
): Promise<ServiceWorkerRegistration | null> {
	if (!enabled || !nav?.serviceWorker) return null;
	try {
		return await nav.serviceWorker.register(SERVICE_WORKER_URL, { type: 'module', scope: '/' });
	} catch {
		console.warn('service worker registration failed');
		return null;
	}
}
