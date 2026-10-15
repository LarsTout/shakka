import { render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MAP_SPOTS, MAP_SUMMARIES } from './fixtures/map-data.js';
import { createFakeMapLibre } from './helpers/fake-maplibre.js';

const p = vi.hoisted(() => ({ key: 'testkey123', webgl: true, load: vi.fn() }));
vi.mock('#lib/map/platform.js', () => ({
	getMaptilerKey: () => p.key,
	supportsWebGL2: () => p.webgl,
	loadMapLibre: () => p.load()
}));

import MapView from '../src/lib/components/MapView.svelte';

let fake: ReturnType<typeof createFakeMapLibre>;
const onfail = vi.fn();

beforeEach(() => {
	vi.clearAllMocks();
	fake = createFakeMapLibre();
	p.key = 'testkey123';
	p.webgl = true;
	p.load.mockResolvedValue(fake.lib);
});

const props = () => ({ spots: MAP_SPOTS, summaries: MAP_SUMMARIES, onfail });
const mapReady = async () => {
	await waitFor(() => expect(fake.maps).toHaveLength(1));
	fake.maps[0]!.emit('load');
};

describe('MapView', () => {
	it('shows a loading status and no logo before load', () => {
		render(MapView, props());
		expect(screen.getByRole('status')).toHaveTextContent('Kaart laden…');
		expect(screen.queryByRole('img')).toBeNull();
	});

	it('shows the MapTiler logo and attribution after load', async () => {
		render(MapView, props());
		await mapReady();
		const img = await screen.findByAltText('MapTiler logo');
		expect(img).toHaveAttribute('src', 'https://api.maptiler.com/resources/logo.svg');
		expect(img.closest('a')).toHaveAttribute('href', 'https://www.maptiler.com');
		expect(screen.getByRole('link', { name: '© MapTiler' })).toHaveAttribute('href', 'https://www.maptiler.com/copyright/');
		expect(screen.getByRole('link', { name: '© OpenStreetMap contributors' })).toHaveAttribute(
			'href',
			'https://www.openstreetmap.org/copyright'
		);
		expect(screen.getByRole('link', { name: 'MapLibre' })).toHaveAttribute('href', 'https://maplibre.org/');
	});

	it('markers link to the spot page and show the verdict', async () => {
		render(MapView, props());
		await mapReady();
		const meer = await screen.findByRole('link', { name: /Testmeer/ });
		expect(meer).toHaveAttribute('href', '/spot/test-meer');
		expect(meer).toHaveTextContent('Go');
		expect(screen.getByRole('link', { name: /Testavond/ })).toHaveTextContent('Morgen: Twijfel');
	});

	it('mentions spots without coordinates', () => {
		render(MapView, props());
		expect(screen.getByText('1 spot zonder coördinaten staat niet op de kaart.')).toBeInTheDocument();
	});

	it('reports a fatal error before style.load', async () => {
		render(MapView, props());
		await waitFor(() => expect(fake.maps).toHaveLength(1));
		fake.maps[0]!.emit('error', {});
		expect(onfail).toHaveBeenCalledWith('load_failed');
	});

	it('removes the map on unmount', async () => {
		const { unmount } = render(MapView, props());
		await mapReady();
		unmount();
		expect(fake.maps[0]!.remove).toHaveBeenCalled();
	});

	it('shows the attribution paragraph before load', () => {
		render(MapView, props());
		expect(screen.getByText(/© OpenStreetMap contributors/)).toBeInTheDocument();
	});

	it('new data replaces the markers without a new map', async () => {
		const { rerender } = render(MapView, props());
		await mapReady();
		await rerender({ spots: MAP_SPOTS, summaries: {} });
		expect(fake.markers.slice(0, 3).every((m) => m.removed)).toBe(true);
		expect(fake.markers.slice(3)).toHaveLength(3);
		expect(fake.markers.slice(3).every((m) => !m.removed)).toBe(true);
		expect(fake.maps).toHaveLength(1);
		expect(screen.getByRole('link', { name: /Testmeer/ })).toHaveTextContent('Nog geen data');
	});
});
