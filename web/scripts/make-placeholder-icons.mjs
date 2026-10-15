// Generates placeholder PNG icons (blue square with a white kite diamond). Node stdlib only.
// Replace the files in static/icons/ with your own design using the same names and sizes.
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crc32, deflateSync } from 'node:zlib';

const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'static', 'icons');
const BLUE = [11, 94, 138];
const WHITE = [255, 255, 255];
const SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

/** @param {string} type @param {Buffer} data */
function chunk(type, data) {
	const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
	const length = Buffer.alloc(4);
	length.writeUInt32BE(data.length);
	const crc = Buffer.alloc(4);
	crc.writeUInt32BE(crc32(body) >>> 0);
	return Buffer.concat([length, body, crc]);
}

/** @param {number} size @param {number} hwRatio @param {number} hhRatio */
export function makePng(size, hwRatio, hhRatio) {
	const c = (size - 1) / 2;
	const hw = hwRatio * size;
	const hh = hhRatio * size;
	const rows = [];
	for (let y = 0; y < size; y++) {
		const row = Buffer.alloc(1 + size * 3);
		row[0] = 0;
		for (let x = 0; x < size; x++) {
			const inside = Math.abs(x - c) / hw + Math.abs(y - c) / hh <= 1;
			const [r, g, b] = inside ? WHITE : BLUE;
			row[1 + x * 3] = r;
			row[2 + x * 3] = g;
			row[3 + x * 3] = b;
		}
		rows.push(row);
	}
	const ihdr = Buffer.alloc(13);
	ihdr.writeUInt32BE(size, 0);
	ihdr.writeUInt32BE(size, 4);
	ihdr[8] = 8; // bit depth
	ihdr[9] = 2; // colour type RGB
	return Buffer.concat([
		SIGNATURE,
		chunk('IHDR', ihdr),
		chunk('IDAT', deflateSync(Buffer.concat(rows))),
		chunk('IEND', Buffer.alloc(0))
	]);
}

const ANY = [0.22, 0.32];
const MASKABLE = [0.16, 0.24];
const files = [
	['icon-192.png', 192, ANY],
	['icon-512.png', 512, ANY],
	['icon-maskable-192.png', 192, MASKABLE],
	['icon-maskable-512.png', 512, MASKABLE],
	['apple-touch-icon.png', 180, MASKABLE]
];

mkdirSync(OUT_DIR, { recursive: true });
for (const [name, size, [hw, hh]] of files) {
	writeFileSync(join(OUT_DIR, name), makePng(size, hw, hh));
	console.log(`wrote ${name}`);
}
