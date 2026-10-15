// Bundle budgets (WP-23): initial JavaScript and service worker precache, in gzip bytes. Run after a build:
// `node scripts/check-bundle-size.mjs` (from web/).
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const KB = 1024;
export const BUDGETS = { initialJsGzip: 150 * KB, precacheGzip: 900 * KB };
export const PRECACHE_EXCLUDED = ['/_headers', '/_redirects']; // = PRECACHE_EXCLUDED_PATHS in src/lib/sw/shell.ts
export const SUPABASE_MARKER = 'X-Client-Info';

/** gzip (level 9) length. @param {Uint8Array | string} data @returns {number} */
export function gzipSize(data) {
	return gzipSync(data, { level: 9 }).length;
}

/** Relative specifiers ('./' or '../') of static imports and re-exports, in order, unique.
 *  Never matches import("x"). The preceding character must not be [\w$.].
 *  @param {string} code @returns {string[]} */
export function staticImports(code) {
	const out = new Set();
	const re = /(?<![\w$.])(?:import|export)\s*(?:(?:[\w$]+\s*,?\s*)?(?:\{[^}]*\}|\*\s*as\s+[\w$]+|\*)?\s*from\s*)?["']([^"']+)["']/g;
	for (const m of code.matchAll(re)) {
		const spec = m[1] ?? '';
		if (spec.startsWith('./') || spec.startsWith('../')) out.add(spec);
	}
	return [...out];
}

/** Relative specifiers of dynamic import("...") calls with a literal argument (quotes or backticks).
 *  @param {string} code @returns {string[]} */
export function dynamicImports(code) {
	const out = new Set();
	for (const m of code.matchAll(/(?<![\w$.])import\(\s*["'`]([^"'`]+)["'`]\s*\)/g)) {
		const spec = m[1] ?? '';
		if (spec.startsWith('./') || spec.startsWith('../')) out.add(spec);
	}
	return [...out];
}

/** Static import closure (absolute paths) of the start files, resolved relative to each importing file.
 *  Missing targets are ignored. @param {string[]} startFiles @returns {string[]} sorted */
export function importClosure(startFiles) {
	const seen = new Set();
	const queue = [...startFiles];
	while (queue.length) {
		const file = /** @type {string} */ (queue.pop());
		if (seen.has(file) || !existsSync(file)) continue;
		seen.add(file);
		for (const spec of staticImports(readFileSync(file, 'utf8'))) queue.push(resolve(dirname(file), spec));
	}
	return [...seen].sort();
}

/** @param {string} text */
export function isMapLibreChunk(text) {
	return text.includes('setWorkerUrl') && text.includes('getWorkerCount');
}

/** Absolute paths of the .js files that index.html lists as <link rel="modulepreload" href="...">. Unique, sorted.
 *  @param {string} html @param {string} buildDir @returns {string[]} */
export function modulepreloadFiles(html, buildDir) {
	const files = new Set();
	for (const tag of html.matchAll(/<link\b[^>]*>/gi)) {
		const attrs = tag[0];
		if (!/\brel\s*=\s*["']?modulepreload\b/i.test(attrs)) continue;
		const href = /\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i.exec(attrs);
		const raw = href?.[1] ?? href?.[2] ?? href?.[3];
		if (!raw) continue;
		const path = raw.replace(/[?#].*$/, '').replace(/^\/+/, '').replace(/^(?:\.\.?\/)+/, '');
		if (path.startsWith('_app/immutable/') && path.endsWith('.js')) files.add(resolve(buildDir, path));
	}
	return [...files].sort();
}

/** @param {string} dir @returns {string[]} */
function listFiles(dir) {
	if (!existsSync(dir)) return [];
	return readdirSync(dir).flatMap((name) => {
		const p = join(dir, name);
		return statSync(p).isDirectory() ? listFiles(p) : [p];
	});
}

/** @param {string[]} files */
const totalGzip = (files) => files.reduce((sum, f) => sum + gzipSize(readFileSync(f)), 0);

/** @param {string} buildDir @param {string} staticDir */
export function measure(buildDir, staticDir) {
	/** @type {string[]} */
	const problems = [];
	const immutable = join(buildDir, '_app', 'immutable');
	const entryDir = join(immutable, 'entry');
	const nodesDir = join(immutable, 'nodes');

	const entries = listFiles(entryDir).filter((f) => f.endsWith('.js'));
	if (entries.length === 0) problems.push('no entry chunks in _app/immutable/entry');
	const nodes = existsSync(nodesDir) ? readdirSync(nodesDir).sort() : [];
	const root = nodes.find((n) => /^0(\.[^.]+)?\.js$/.test(n));
	if (!root) problems.push('root layout chunk _app/immutable/nodes/0.*.js not found');
	const startFiles = [...entries, ...(root ? [join(nodesDir, root)] : [])];

	const closure = importClosure(startFiles);
	const rootRel = (/** @type {string[]} */ files) => files.map((f) => relative(buildDir, f)).join(', ');
	if (!closure.some((f) => readFileSync(f, 'utf8').includes(SUPABASE_MARKER))) {
		problems.push('initial JS does not contain supabase-js: import parsing is probably broken');
	}
	for (const f of closure) {
		if (isMapLibreChunk(readFileSync(f, 'utf8'))) problems.push(`MapLibre is in the initial JS: ${relative(buildDir, f)}`);
	}

	const indexPath = join(buildDir, 'index.html');
	const preloaded = existsSync(indexPath) ? modulepreloadFiles(readFileSync(indexPath, 'utf8'), buildDir) : [];
	if (preloaded.length === 0) {
		problems.push('index.html has no modulepreload links: cannot cross-check the import closure');
	} else {
		// SvelteKit's entry/start calls import("../chunks/<client>.js") from init(), so index.html preloads that chunk
		// although it is a dynamic import: a file that the closure imports dynamically explains a preload too.
		const dynamicTargets = closure.flatMap((f) =>
			dynamicImports(readFileSync(f, 'utf8')).map((spec) => resolve(dirname(f), spec))
		);
		const explained = new Set([...closure, ...importClosure(dynamicTargets)]);
		const missing = preloaded.filter((f) => !explained.has(f));
		if (missing.length) {
			problems.push(
				`modulepreload files missing from the import closure (import parsing is probably broken): ${rootRel(missing)}`
			);
		}
	}
	const initialFiles = [...new Set([...closure, ...preloaded])].filter((f) => existsSync(f)).sort();

	const precache = new Set(listFiles(immutable));
	for (const f of listFiles(staticDir)) {
		const relPath = relative(staticDir, f).split('\\').join('/');
		if (PRECACHE_EXCLUDED.includes('/' + relPath)) continue;
		const built = join(buildDir, relPath);
		if (existsSync(built)) precache.add(built);
	}
	if (existsSync(indexPath)) precache.add(indexPath);
	const precacheFiles = [...precache].sort();

	const maplibreFile =
		listFiles(immutable).find((f) => !f.startsWith(entryDir) && f.endsWith('.js') && isMapLibreChunk(readFileSync(f, 'utf8'))) ??
		null;

	return {
		initial: { files: initialFiles, gzip: totalGzip(initialFiles) },
		precache: { files: precacheFiles, gzip: totalGzip(precacheFiles) },
		maplibre: { file: maplibreFile, gzip: maplibreFile ? gzipSize(readFileSync(maplibreFile)) : 0 },
		problems
	};
}

const kb = (/** @type {number} */ bytes) => Math.round((bytes / KB) * 10) / 10;

/** Problems for every budget exceeded, plus m.problems.
 *  @param {ReturnType<typeof measure>} m @param {typeof BUDGETS} [budgets] @returns {string[]} */
export function checkBudgets(m, budgets = BUDGETS) {
	const problems = [...m.problems];
	if (m.initial.gzip > budgets.initialJsGzip) {
		problems.push(`initial JS is ${kb(m.initial.gzip)} kB gzip, budget ${kb(budgets.initialJsGzip)} kB`);
	}
	if (m.precache.gzip > budgets.precacheGzip) {
		problems.push(`precache is ${kb(m.precache.gzip)} kB gzip, budget ${kb(budgets.precacheGzip)} kB`);
	}
	return problems;
}

/** @param {string} name @param {string} fallback @returns {string} */
function arg(name, fallback) {
	const i = process.argv.indexOf(name);
	return i !== -1 && process.argv[i + 1] ? resolve(process.cwd(), process.argv[i + 1] ?? '') : fallback;
}

function main() {
	const webRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
	const build = arg('--build', join(webRoot, 'build'));
	const staticDir = arg('--static', join(webRoot, 'static'));
	if (!existsSync(build)) {
		console.error('check-bundle-size: build/ is missing (run npm run build first)');
		process.exit(1);
	}
	const m = measure(build, staticDir);
	console.log(`initial JS: ${kb(m.initial.gzip)} kB gzip (${m.initial.files.length} files, budget ${kb(BUDGETS.initialJsGzip)} kB)`);
	console.log(`precache: ${kb(m.precache.gzip)} kB gzip (${m.precache.files.length} files, budget ${kb(BUDGETS.precacheGzip)} kB)`);
	console.log(m.maplibre.file ? `maplibre chunk: ${kb(m.maplibre.gzip)} kB gzip` : 'maplibre chunk: not found');
	const problems = checkBudgets(m);
	for (const p of problems) console.error(`check-bundle-size: ${p}`);
	process.exit(problems.length ? 1 : 0);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
