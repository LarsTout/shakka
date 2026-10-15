// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
	BUDGETS,
	PRECACHE_EXCLUDED,
	checkBudgets,
	dynamicImports,
	gzipSize,
	importClosure,
	measure,
	modulepreloadFiles,
	staticImports
} from '../scripts/check-bundle-size.mjs';
import { PRECACHE_EXCLUDED_PATHS } from '../src/lib/sw/shell.js';

const webRoot = process.cwd();
let root: string;
let build: string;
let staticDir: string;

function put(base: string, rel: string, text: string) {
	const p = join(base, rel);
	mkdirSync(dirname(p), { recursive: true });
	writeFileSync(p, text);
}
const imm = (rel: string, text: string) => put(build, `_app/immutable/${rel}`, text);

const MAPLIBRE = 'export{setWorkerUrl,getWorkerCount};';
function fixture() {
	imm('entry/start.a.js', 'import{a as b}from"../chunks/x.js";import"../chunks/y.js";const l=()=>import("../chunks/lazy.js");');
	imm('entry/app.b.js', 'export{c}from"../chunks/x.js";export*from"../chunks/z.js";');
	imm('nodes/0.c.js', 'import{s}from"../chunks/supa.js";');
	imm('nodes/1.d.js', 'import"../chunks/route.js";');
	imm('chunks/x.js', 'export const c=1;');
	imm('chunks/y.js', 'export const y=1;');
	imm('chunks/z.js', 'export const z=1;');
	imm('chunks/supa.js', 'export const s="X-Client-Info";');
	imm('chunks/lazy.js', 'export const l=1;');
	imm('chunks/route.js', 'export const r=1;');
	imm('chunks/maplibre.e.js', MAPLIBRE);
	imm('assets/a.css', 'body{}');
	put(
		build,
		'index.html',
		[
			'<html><head>',
			'<link rel="modulepreload" href="/_app/immutable/entry/start.a.js">',
			'<link rel="modulepreload" href="/_app/immutable/entry/app.b.js">',
			'<link rel="modulepreload" href="/_app/immutable/nodes/0.c.js">',
			'<link rel="modulepreload" href="/_app/immutable/chunks/y.js">',
			'<link rel="modulepreload" href="/_app/immutable/chunks/z.js">',
			'<link rel="modulepreload" href="/_app/immutable/chunks/supa.js">',
			'<link href="./_app/immutable/chunks/x.js?v=1" rel=modulepreload>',
			'<link rel="stylesheet" href="/_app/immutable/assets/a.css">',
			'</head></html>'
		].join('\n')
	);
	put(staticDir, 'favicon.svg', '<svg/>');
	put(staticDir, '_headers', '/*\n  A: b');
	put(build, 'favicon.svg', '<svg/>');
	put(build, '_headers', '/*\n  A: b');
}
const rel = (files: string[]) => files.map((f) => relative(join(build, '_app/immutable'), f)).sort();

beforeEach(() => {
	root = mkdtempSync(join(tmpdir(), 'shakka-size-'));
	build = join(root, 'build');
	staticDir = join(root, 'static');
	fixture();
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

const INITIAL = ['chunks/supa.js', 'chunks/x.js', 'chunks/y.js', 'chunks/z.js', 'entry/app.b.js', 'entry/start.a.js', 'nodes/0.c.js'];

describe('staticImports', () => {
	it('finds static specifiers only', () => {
		expect(
			staticImports('import{a as b}from"../x.js";import"../y.js";export{c}from"../z.js";export*from"../w.js";const l=()=>import("../lazy.js");')
		).toEqual(['../x.js', '../y.js', '../z.js', '../w.js']);
	});
	it('handles spaces and namespace imports', () => {
		expect(staticImports("import { a } from './x.js';\nimport * as m from\"./m.js\";import d from './d.js'")).toEqual([
			'./x.js',
			'./m.js',
			'./d.js'
		]);
	});
	it('ignores member names that end in import and bare package specifiers', () => {
		expect(staticImports('foo.import"x";import"pkg";import("../a.js")')).toEqual([]);
	});
});

describe('measure', () => {
	it('counts the static closure of entry and root layout, plus the modulepreload files', () => {
		const m = measure(build, staticDir);
		expect(rel(m.initial.files)).toEqual(INITIAL);
		expect(m.problems).toEqual([]);
	});
	it('precache has the immutable files, favicon and index.html but not _headers', () => {
		const m = measure(build, staticDir);
		const names = m.precache.files.map((f: string) => relative(build, f));
		expect(names).toEqual(expect.arrayContaining(['_app/immutable/chunks/maplibre.e.js', '_app/immutable/chunks/lazy.js', 'favicon.svg', 'index.html']));
		expect(names).not.toContain('_headers');
	});
	it('finds the MapLibre chunk', () => {
		expect(measure(build, staticDir).maplibre.file).toMatch(/maplibre\.e\.js$/);
	});
	it('importClosure follows relative imports and ignores missing targets', () => {
		imm('chunks/q.js', 'import"./nowhere.js";import"./y.js";');
		expect(rel(importClosure([join(build, '_app/immutable/chunks/q.js')]))).toEqual(['chunks/q.js', 'chunks/y.js']);
	});
	it('reports a missing root layout chunk', () => {
		rmSync(join(build, '_app/immutable/nodes/0.c.js'));
		expect(measure(build, staticDir).problems.join()).toContain('root layout chunk');
	});
	it('reports a closure without supabase-js', () => {
		imm('chunks/supa.js', 'export const s=1;');
		expect(measure(build, staticDir).problems.join()).toContain('supabase-js');
	});
	it('reports MapLibre in the initial JS', () => {
		imm('entry/start.a.js', 'import"../chunks/maplibre.e.js";import"../chunks/x.js";');
		expect(measure(build, staticDir).problems.join()).toContain('MapLibre is in the initial JS');
	});
	it('reports an index.html without modulepreload links', () => {
		put(build, 'index.html', '<html></html>');
		expect(measure(build, staticDir).problems.join()).toContain('index.html has no modulepreload links');
	});
	it('reports modulepreload files outside the import closure and counts them', () => {
		put(build, 'index.html', readFileSync(join(build, 'index.html'), 'utf8').replace('</head>', '<link rel="modulepreload" href="/_app/immutable/chunks/route.js"></head>'));
		const m = measure(build, staticDir);
		expect(m.problems.join()).toMatch(/modulepreload files missing from the import closure.*route\.js/);
		expect(rel(m.initial.files)).toContain('chunks/route.js');
	});
});

describe('startup dynamic import (SvelteKit entry/start)', () => {
	it('a preloaded file that the closure imports dynamically is not a problem, and is counted', () => {
		put(build, 'index.html', readFileSync(join(build, 'index.html'), 'utf8').replace('</head>', '<link rel="modulepreload" href="/_app/immutable/chunks/lazy.js"></head>'));
		const m = measure(build, staticDir);
		expect(m.problems).toEqual([]);
		expect(rel(m.initial.files)).toContain('chunks/lazy.js');
	});
	it('dynamicImports reads literals with quotes and backticks only', () => {
		expect(dynamicImports('t(()=>import(`../c/a.js`),0);import("./b.js");import(x);foo.import("./n.js")')).toEqual(['../c/a.js', './b.js']);
	});
});

describe('modulepreloadFiles', () => {
	it('normalises paths and leaves out stylesheets', () => {
		const html = readFileSync(join(build, 'index.html'), 'utf8');
		expect(rel(modulepreloadFiles(html, build))).toEqual(INITIAL);
	});
});

describe('checkBudgets', () => {
	it('reports both budgets when exceeded and nothing within them', () => {
		const m = measure(build, staticDir);
		expect(checkBudgets(m, { initialJsGzip: 1, precacheGzip: 1 })).toHaveLength(2);
		expect(checkBudgets(m, BUDGETS)).toEqual([]);
		expect(gzipSize('aaaa')).toBeGreaterThan(0);
	});
});

describe('contracts', () => {
	it('PRECACHE_EXCLUDED equals PRECACHE_EXCLUDED_PATHS of the service worker', () => {
		expect([...PRECACHE_EXCLUDED]).toEqual([...PRECACHE_EXCLUDED_PATHS]);
	});
	it('CI runs the script after the build', () => {
		const lines = readFileSync(join(webRoot, '../.github/workflows/ci.yml'), 'utf8').split('\n').map((l) => l.trim());
		const size = lines.indexOf('- run: node scripts/check-bundle-size.mjs');
		expect(size).toBeGreaterThan(lines.indexOf('- run: npm run build'));
	});
});

describe('CLI', () => {
	const run = () =>
		spawnSync(process.execPath, ['scripts/check-bundle-size.mjs', '--build', build, '--static', staticDir], {
			cwd: webRoot,
			encoding: 'utf8'
		});
	it('exits 0 within the budgets', () => {
		const r = run();
		expect(r.status).toBe(0);
		expect(r.stdout).toContain('initial JS:');
	});
	it('exits 1 when the initial JS is too large', () => {
		imm('chunks/x.js', randomBytes(300_000).toString('base64'));
		const r = run();
		expect(r.status).toBe(1);
		expect(r.stdout + r.stderr).toContain('initial JS is');
	});
});
