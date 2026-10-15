// Post-build checks for the PWA output (build/) and third-party-free sources. Run via `npm run verify:build`.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const WEB_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const TRACKER_MARKERS = ['googletagmanager', 'google-analytics', 'plausible', 'fonts.googleapis', 'cdn.'];
const TEXT_EXTENSIONS = new Set(['.ts', '.js', '.svelte', '.html', '.css', '.json', '.webmanifest', '.svg', '.txt']);

/** @param {unknown} manifest @returns {string[]} problems (empty = ok) */
export function checkManifest(manifest) {
	/** @type {string[]} */
	const problems = [];
	const m = /** @type {Record<string, any>} */ (manifest ?? {});
	if (m.name !== 'Shakka') problems.push('manifest: name must be "Shakka"');
	if (m.display !== 'standalone') problems.push('manifest: display must be "standalone"');
	if (m.start_url !== '/') problems.push('manifest: start_url must be "/"');
	/** @type {Array<{ sizes?: string, purpose?: string, type?: string }>} */
	const icons = Array.isArray(m.icons) ? m.icons : [];
	for (const purpose of ['any', 'maskable']) {
		for (const sizes of ['192x192', '512x512']) {
			const found = icons.some(
				(i) =>
					i.sizes === sizes &&
					(purpose === 'any' ? i.purpose === undefined || i.purpose === 'any' : i.purpose === purpose)
			);
			if (!found) problems.push(`manifest: missing ${purpose} icon ${sizes}`);
		}
	}
	for (const icon of icons) {
		if (icon.type !== 'image/png') problems.push('manifest: every icon must have type image/png');
	}
	return problems;
}

/** @param {string} html @returns {string[]} offending <script> tags */
export function findExternalScripts(html) {
	return html.match(/<script\b[^>]*\bsrc\s*=\s*["']?(?:https?:)?\/\/[^>]*>/gi) ?? [];
}

/** @param {string} text @returns {string[]} matched tracker/CDN markers */
export function findTrackerRefs(text) {
	return TRACKER_MARKERS.filter((marker) => text.includes(marker));
}

/** @param {Uint8Array} buffer PNG file contents @returns {{ width: number, height: number }} */
export function pngSize(buffer) {
	const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
	if (buffer.length < 24 || signature.some((byte, i) => buffer[i] !== byte)) {
		throw new Error('not a PNG file');
	}
	const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
	return { width: view.getUint32(16), height: view.getUint32(20) };
}

/** @param {string} dir @returns {string[]} */
function listFiles(dir) {
	if (!existsSync(dir)) return [];
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? listFiles(path) : [path];
	});
}

/**
 * MapLibre must be lazy: never mentioned in entry chunks, but present as a real library chunk elsewhere.
 * The library chunk is recognised by its own API names (setWorkerUrl and getWorkerCount), not by the text
 * "maplibre", which also occurs in app code (URLs, attribution) and in page chunks that only call it.
 * @param {string} buildDir @returns {string[]} problems
 */
export function checkLazyMapLibre(buildDir) {
	/** @type {string[]} */
	const problems = [];
	const immutable = join(buildDir, '_app', 'immutable');
	const entry = join(immutable, 'entry');
	for (const file of listFiles(entry)) {
		if (!['.js', '.css'].includes(extname(file))) continue;
		if (readFileSync(file, 'utf8').includes('maplibre')) {
			problems.push(`maplibre referenced in entry chunk ${relative(buildDir, file)}`);
		}
	}
	const hasLibraryChunk = listFiles(immutable).some((file) => {
		if (file.startsWith(entry) || !['.js', '.mjs'].includes(extname(file))) return false;
		const text = readFileSync(file, 'utf8');
		return text.includes('setWorkerUrl') && text.includes('getWorkerCount');
	});
	if (!hasLibraryChunk) problems.push('no lazily loaded maplibre chunk in _app/immutable');
	return problems;
}

function main() {
	/** @type {string[]} */
	const problems = [];
	const build = join(WEB_ROOT, 'build');
	const indexPath = join(build, 'index.html');

	if (!existsSync(indexPath)) problems.push('build/index.html is missing');
	if (existsSync(join(build, '404.html'))) {
		problems.push('build/404.html must not exist (it breaks the Cloudflare Pages SPA fallback)');
	}

	const manifestPath = join(build, 'manifest.webmanifest');
	if (!existsSync(manifestPath)) {
		problems.push('build/manifest.webmanifest is missing');
	} else {
		const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
		problems.push(...checkManifest(manifest));
		for (const icon of manifest.icons ?? []) {
			const file = join(build, icon.src);
			if (!existsSync(file)) {
				problems.push(`icon missing in build: ${icon.src}`);
				continue;
			}
			try {
				const { width, height } = pngSize(readFileSync(file));
				if (`${width}x${height}` !== icon.sizes) {
					problems.push(`icon ${icon.src} is ${width}x${height}, manifest says ${icon.sizes}`);
				}
			} catch {
				problems.push(`icon ${icon.src} is not a valid PNG`);
			}
		}
	}

	if (!existsSync(join(build, 'service-worker.js'))) problems.push('build/service-worker.js is missing');
	problems.push(...checkLazyMapLibre(build));

	if (existsSync(indexPath)) {
		for (const tag of findExternalScripts(readFileSync(indexPath, 'utf8'))) {
			problems.push(`external script in index.html: ${tag}`);
		}
	}

	for (const dir of ['src', 'static']) {
		for (const file of listFiles(join(WEB_ROOT, dir))) {
			if (!TEXT_EXTENSIONS.has(extname(file))) continue;
			const hits = findTrackerRefs(readFileSync(file, 'utf8'));
			if (hits.length) problems.push(`tracker/CDN reference in ${file}: ${hits.join(', ')}`);
		}
	}

	if (problems.length) {
		for (const problem of problems) console.error(`verify-build: ${problem}`);
		process.exit(1);
	}
	console.log('verify-build: ok');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
