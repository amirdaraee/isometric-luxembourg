import assert from "node:assert/strict";
import { test } from "node:test";
import { coarseTops, TOP_CELLS } from "./heightmap.ts";

// the shader's reading of the height map at a point (hmAt): the highest thing it can return there
// (second: whether it reads a tree or a structure, whose numbers are in the second texture)
function readTop(A: Uint8Array, B: Uint8Array, w: number, h: number, zbase: number, u: [number, number, number], gx: number, gy: number) {
  const x0 = Math.floor(gx - 0.5), y0 = Math.floor(gy - 0.5), fx = gx - 0.5 - x0, fy = gy - 0.5 - y0;
  let T = 0, pb = 0, hb = 0, pt = 0, ht = 0, ps = 0, hs = 0;
  for (let k = 0; k < 4; k++) {
    const ox = k & 1, oy = k >> 1;
    const cx = Math.min(Math.max(x0 + ox, 0), w - 1), cy = Math.min(Math.max(y0 + oy, 0), h - 1);
    const wt = (ox ? fx : 1 - fx) * (oy ? fy : 1 - fy), i = (cy * w + cx) * 4;
    T += wt * (zbase + (A[i] + A[i + 1] * 256) / 100);
    if (A[i + 2] > 0) { pb += wt; hb += wt * A[i + 2] * u[0]; }
    if (A[i + 3] > 0) { pt += wt; ht += wt * A[i + 3] * u[1]; }
    if (B[i + 1] > 0) { ps += wt; hs += wt * B[i + 1] * u[2]; }
  }
  return { top: T + Math.max(pb > 0.5 ? hb / pb : 0, pt > 0.5 ? ht / pt : 0, ps > 0.5 ? hs / ps : 0), second: pt > 0 || ps > 0 };
}

test("a block's coarse top is never below what the light pass can read anywhere in it", () => {
  const w = 70, h = 53, zbase = 200, u: [number, number, number] = [0.25, 0.25, 0.5];
  const A = new Uint8Array(w * h * 4), B = new Uint8Array(w * h * 4);
  let s = 7;
  const rnd = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  for (let i = 0; i < w * h; i++) {
    const T = Math.floor(rnd() * 9000);
    A[i * 4] = T & 255; A[i * 4 + 1] = T >> 8;
    A[i * 4 + 2] = rnd() < 0.3 ? 1 + Math.floor(rnd() * 254) : 0;
    A[i * 4 + 3] = rnd() < 0.3 ? 1 + Math.floor(rnd() * 254) : 0;
    B[i * 4 + 1] = rnd() < 0.1 ? 1 + Math.floor(rnd() * 254) : 0;
  }
  const C = coarseTops(A, B, w, h, zbase, u);
  assert.equal(C.width, Math.ceil(w / TOP_CELLS));
  assert.equal(C.height, Math.ceil(h / TOP_CELLS));
  let tight = 0;
  for (let k = 0; k < 40000; k++) {
    const gx = rnd() * w * 0.999999, gy = rnd() * h * 0.999999;
    const o = Math.floor(gy / TOP_CELLS) * C.width + Math.floor(gx / TOP_CELLS);
    const c = C.data[o * 2];
    const r = readTop(A, B, w, h, zbase, u, gx, gy);
    assert.ok(c >= r.top, `block top ${c} below a reading of ${r.top} at ${gx}, ${gy}`);
    assert.ok(!r.second || C.data[o * 2 + 1] === 1, `a tree or a structure read at ${gx}, ${gy} in a block marked as having none`);
    if (c - r.top < 30) tight++;
  }
  assert.ok(tight > 0);                                    // and it is a top of the block, not of the whole map
  assert.ok(C.zTop >= zbase + 80);
});

test("flat empty ground: every block's top is the ground", () => {
  const w = 32, h = 32, A = new Uint8Array(w * h * 4), B = new Uint8Array(w * h * 4);
  for (let i = 0; i < w * h; i++) { A[i * 4] = 100; }
  const C = coarseTops(A, B, w, h, 10, [0.25, 0.25, 0.5]);
  for (let o = 0; o < C.width * C.height; o++) { assert.ok(Math.abs(C.data[o * 2] - 11.01) < 1e-4); assert.equal(C.data[o * 2 + 1], 0); }
});
