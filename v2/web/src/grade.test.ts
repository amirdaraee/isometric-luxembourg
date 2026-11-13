// The hour's light (gl/grade.ts) from v2/config/light.json: day is untouched, golden hour is brighter and warmer
// than day's shade, night is a deep blue and not black, and nothing jumps on the way down.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { LightConfig } from "./data.ts";
import { grade, nightFactor } from "./gl/grade.ts";

const cfg = JSON.parse(readFileSync(new URL("../../config/light.json", import.meta.url), "utf8")) as LightConfig;
const lum = (c: number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];

test("day is one constant: the sun's own tint, white sky, no fill, no moon, hard shadows", () => {
  for (const el of [6, 10, 35, 63]) {
    assert.deepEqual(grade(cfg, el), { ...grade(cfg, 6), sun: cfg.grade.day_tint });
    const g = grade(cfg, el);
    assert.deepEqual(g.amb, [1, 1, 1]);
    assert.equal(g.fill + g.soft + g.moon + g.desat, 0);
  }
});

test("golden hour is brighter and warmer than day's sky light, with soft shadows", () => {
  const g = grade(cfg, 3);
  assert.ok(lum(g.amb) > 1.25, "the sky light is lifted");
  assert.ok(g.amb[0] > g.amb[1] && g.amb[1] > g.amb[2] && g.sun[0] > g.sun[1] && g.sun[1] > g.sun[2], "warm");
  assert.ok(g.sun[2] / g.sun[0] < 0.55, "the sun is orange");
  assert.ok(g.fill > 0.2 && g.soft > 0.5 && g.moon === 0);
});

test("night is a deep blue, not black, and the moon gives the shapes", () => {
  const g = grade(cfg, -20);
  const a = g.amb.map((v) => v * cfg.sun.ambient);
  assert.ok(a[2] > 1.8 * a[0] && a[2] > a[1], "blue");
  assert.ok(lum(a) > 0.2 && lum(a) < 0.45, `the night's own light is ${lum(a).toFixed(2)} of day's ambient scale`);
  assert.ok(g.moon >= 0.3 && g.moonDir[2] > 0.4 && Math.abs(Math.hypot(...g.moonDir) - 1) < 1e-9);
  assert.equal(g.fill, 0);
  assert.equal(nightFactor(cfg, 1), 0);
  assert.equal(nightFactor(cfg, -6), 1);
});

test("a cutaway's opening gets the sky's light only: day as bright as lit stone, warm at golden hour, blue at night", () => {
  const K = cfg.cutaway!, a = cfg.sun.ambient;
  const open = (el: number) => grade(cfg, el).open.map((v) => v * a);
  for (const el of [6, 20, 63]) assert.deepEqual(grade(cfg, el).open, [K.sky_day, K.sky_day, K.sky_day]);
  // by day about the level of the kept outside stone (0.85), well over the shade the opening stood in before (0.48)
  assert.ok(Math.abs(lum(open(40)) - 0.85) < 0.01, `day ${lum(open(40)).toFixed(3)}`);
  const g = open(2), n = open(-20);
  assert.ok(g[0] > g[1] && g[1] > g[2] && Math.abs(lum(g) - 0.84) < 0.02, `golden hour, warm: ${g.map((v) => v.toFixed(2))}`);
  assert.ok(n[2] > 1.8 * n[0] && n[2] > n[1] && Math.abs(lum(n) - 0.31) < 0.02, `night, blue: ${n.map((v) => v.toFixed(2))}`);
  // it is the hour's sky colour at one level: no channel of it is set apart
  for (const el of [40, 5, 2, -2, -4, -20]) {
    const G = grade(cfg, el), r = G.open.map((v, i) => v / G.amb[i]);
    assert.ok(Math.abs(r[0] - r[1]) < 1e-9 && Math.abs(r[1] - r[2]) < 1e-9);
  }
});

test("nothing jumps between day, golden hour, the blue hour and night", () => {
  const key = (el: number) => { const g = grade(cfg, el); return [...g.sun, ...g.amb, g.fill, g.soft, g.moon, g.desat, ...g.open]; };
  for (let el = 8; el > -9; el -= 0.01) {
    const a = key(el), b = key(el - 0.01);
    a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) < 0.012, `value ${i} jumps by ${Math.abs(v - b[i]).toFixed(3)} at ${el.toFixed(2)} deg`));
  }
});
