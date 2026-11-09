// The viewer's sun is v2/config/sun.py's: the same positions (values from the Python model).
import assert from "node:assert/strict";
import { test } from "node:test";
import { sunPosition, sunVector } from "./sun.ts";

const PY: [string, number, number][] = [
  ["2026-06-21T11:00:00Z", 161.006231, 62.832706],
  ["2026-11-09T07:30:00Z", 125.848887, 6.654504],
  ["2026-03-20T18:00:00Z", 273.306268, -2.615394],
  ["2026-12-21T22:00:00Z", 316.41105, -58.03439],
];

test("sun position equals the Python model", () => {
  for (const [t, az, el] of PY) {
    const p = sunPosition(new Date(t));
    assert.ok(Math.abs(p.az - az) < 1e-6, `${t} az ${p.az} vs ${az}`);
    assert.ok(Math.abs(p.el - el) < 1e-6, `${t} el ${p.el} vs ${el}`);
  }
});

test("sun vector is a unit vector towards the sun", () => {
  const [x, y, z] = sunVector(180, 30);
  assert.ok(Math.abs(Math.hypot(x, y, z) - 1) < 1e-12);
  assert.ok(Math.abs(x) < 1e-12 && y < 0 && z > 0);
});
