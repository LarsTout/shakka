import { vi, type Mock } from 'vitest';
import type { MapLibre } from '../../src/lib/map/platform.js';

export class FakeGPUInitializationError extends Error {}

type EventName = 'style.load' | 'load' | 'error';

export interface FakeMap {
	options: Record<string, unknown>;
	controls: Array<{ control: unknown; position?: string }>;
	remove: Mock;
	emit(type: EventName, event?: unknown): void;
}
export interface FakeMarker {
	options: { element: HTMLElement; anchor: string };
	lngLat: [number, number] | null;
	removed: boolean;
}

export function createFakeMapLibre() {
	const maps: FakeMap[] = [];
	const markers: FakeMarker[] = [];
	const navigationOptions: unknown[] = [];
	const throwOnConstruct: { error: Error | null } = { error: null };

	class Map implements FakeMap {
		options: Record<string, unknown>;
		controls: Array<{ control: unknown; position?: string }> = [];
		remove = vi.fn();
		private handlers: Record<string, Array<(event?: unknown) => void>> = {};
		constructor(options: Record<string, unknown>) {
			if (throwOnConstruct.error) throw throwOnConstruct.error;
			this.options = options;
			maps.push(this);
		}
		on(type: string, fn: (event?: unknown) => void) {
			(this.handlers[type] ??= []).push(fn);
		}
		addControl(control: unknown, position?: string) {
			this.controls.push({ control, position });
		}
		emit(type: EventName, event?: unknown) {
			for (const fn of this.handlers[type] ?? []) fn(event);
		}
	}

	class Marker implements FakeMarker {
		options: { element: HTMLElement; anchor: string };
		lngLat: [number, number] | null = null;
		removed = false;
		constructor(options: { element: HTMLElement; anchor: string }) {
			this.options = options;
			markers.push(this);
		}
		setLngLat(ll: [number, number]) {
			this.lngLat = ll;
			return this;
		}
		addTo(map: Map) {
			(map.options.container as HTMLElement).append(this.options.element);
			return this;
		}
		remove() {
			this.options.element.remove();
			this.removed = true;
			return this;
		}
	}

	class NavigationControl {
		constructor(options: unknown) {
			navigationOptions.push(options);
		}
	}

	const lib = {
		Map,
		Marker,
		NavigationControl,
		GPUInitializationError: FakeGPUInitializationError,
		setWorkerUrl: vi.fn()
	} as unknown as MapLibre; // the one cast: test code only
	return { lib, maps, markers, navigationOptions, throwOnConstruct };
}
