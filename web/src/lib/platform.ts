export interface PlatformInfo {
	userAgent: string;
	maxTouchPoints: number;
	navigatorStandalone: boolean; // iOS Safari: navigator.standalone === true
	displayModeStandalone: boolean; // matchMedia('(display-mode: standalone)').matches
}

/** Reads navigator/window defensively; never throws (also in Node without window). */
export function readPlatform(): PlatformInfo {
	const nav = typeof navigator !== 'undefined' ? navigator : undefined;
	const hasMatchMedia = typeof window !== 'undefined' && typeof window.matchMedia === 'function';
	return {
		userAgent: typeof nav?.userAgent === 'string' ? nav.userAgent : '',
		maxTouchPoints: typeof nav?.maxTouchPoints === 'number' ? nav.maxTouchPoints : 0,
		navigatorStandalone:
			(nav as (Navigator & { standalone?: boolean }) | undefined)?.standalone === true,
		displayModeStandalone: hasMatchMedia && window.matchMedia('(display-mode: standalone)').matches
	};
}

/** iPhone, iPad or iPod in the UA, or iPadOS with a desktop UA (Macintosh and maxTouchPoints > 1). */
export function isIos(p: PlatformInfo = readPlatform()): boolean {
	return (
		/\b(iPhone|iPad|iPod)\b/.test(p.userAgent) ||
		(/\bMacintosh\b/.test(p.userAgent) && p.maxTouchPoints > 1)
	);
}

export function isStandalone(p: PlatformInfo = readPlatform()): boolean {
	return p.navigatorStandalone || p.displayModeStandalone;
}

/** Web Push on iOS/iPadOS only works in the Home Screen app (16.4+). */
export function needsInstallFirst(p: PlatformInfo = readPlatform()): boolean {
	return isIos(p) && !isStandalone(p);
}
