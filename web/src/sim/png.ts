// A small PNG reader for the headless checks (sim/audit.ts, sim/roadfit.test.ts): 8-bit grey, RGB, RGBA or palette
// indices, non-interlaced, enough for the map's data files.
import { readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";

export interface Png { w: number; h: number; ch: number; d: Uint8Array }

export function readPng(file: string): Png {
  const b = readFileSync(file);
  let o = 8, w = 0, h = 0, type = 0;
  const idat: Buffer[] = [];
  while (o < b.length) {
    const len = b.readUInt32BE(o), kind = b.toString("latin1", o + 4, o + 8), data = b.subarray(o + 8, o + 8 + len);
    if (kind === "IHDR") {
      w = data.readUInt32BE(0); h = data.readUInt32BE(4); type = data[9];
      if (data[8] !== 8 || data[12] !== 0) throw new Error(`${file}: only 8-bit, non-interlaced PNGs`);
    } else if (kind === "IDAT") idat.push(data);
    else if (kind === "IEND") break;
    o += 12 + len;
  }
  const ch = type === 0 || type === 3 ? 1 : type === 2 ? 3 : type === 4 ? 2 : 4;
  const raw = inflateSync(Buffer.concat(idat)), stride = w * ch, d = new Uint8Array(w * h * ch);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], src = y * (stride + 1) + 1, dst = y * stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= ch ? d[dst + x - ch] : 0, up = y ? d[dst - stride + x] : 0, ul = y && x >= ch ? d[dst - stride + x - ch] : 0;
      let v = raw[src + x];
      if (f === 1) v += a; else if (f === 2) v += up; else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) { const p = a + up - ul, pa = Math.abs(p - a), pb = Math.abs(p - up), pc = Math.abs(p - ul); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : ul; }
      d[dst + x] = v & 255;
    }
  }
  return { w, h, ch, d };
}
