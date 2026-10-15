// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

const script = fileURLToPath(new URL('../../scripts/check-no-client-openmeteo.sh', import.meta.url));
const run = (...args: string[]) => spawnSync('bash', [script, ...args], { encoding: 'utf8' });

let dir: string;
beforeEach(() => {
	dir = mkdtempSync(join(tmpdir(), 'guard-'));
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));

describe('check-no-client-openmeteo.sh', () => {
	it('fails on the forecast API host', () => {
		writeFileSync(join(dir, 'fixture.ts'), `const u = '${'https://' + 'api.open-meteo.com/v1/forecast'}';`);
		const r = run(dir);
		expect(r.status).toBe(1);
		expect(r.stdout).toContain('fixture.ts');
	});
	it('fails on the marine API host', () => {
		writeFileSync(join(dir, 'fixture.ts'), `const u = '${'https://' + 'marine-api.open-meteo.com/v1/marine'}';`);
		expect(run(dir).status).toBe(1);
	});
	it('allows the attribution link', () => {
		writeFileSync(join(dir, 'fixture.ts'), "const u = 'https://open-meteo.com/';");
		expect(run(dir).status).toBe(0);
	});
	it('exits 2 for a missing path', () => {
		expect(run(join(dir, 'nope')).status).toBe(2);
	});
	it('is clean on the repo itself', () => {
		expect(run().status).toBe(0);
	});
});
