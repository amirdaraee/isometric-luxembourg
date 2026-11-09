// Layer 12 on a small synthetic network: v1's simulation drives on the v2 graph's roads, and every vehicle's height
// is its edge's profile (no jumps); trams follow their matched run and take the track's profile.
import assert from "node:assert/strict";
import { test } from "node:test";
import { declutter, overlaps, type Label } from "./labels.ts";
import { Vehicles, inside, type VehiclesData } from "./vehicles.ts";
import type { TransitData } from "./sim/transit.ts";

const U = 0.25;
// two roads meeting at a junction; the first climbs 10 m over 400 m (a ramp onto a deck), the second is flat
function network(): VehiclesData {
  const line = (x0: number, y0: number, x1: number, y1: number, n: number) => {
    const p: number[] = [];
    for (let i = 0; i <= n; i++) p.push((x0 + (x1 - x0) * i / n) / U, -(y0 + (y1 - y0) * i / n) / U);
    return p;
  };
  const s = (L: number, n: number) => Array.from({ length: n + 1 }, (_, i) => (L * i / n) / U);
  return {
    unit_m: U, origin_en: [70000, 65000],
    edges: [
      { m: "road", st: "bridge", s: s(400, 20), z: Array.from({ length: 21 }, (_, i) => 300 + i * 0.5), id: "a" },
      { m: "road", st: "ground", s: s(300, 15), z: Array(16).fill(310), id: "b" },
      { m: "tram", st: "ground", s: s(400, 20), z: Array.from({ length: 21 }, (_, i) => 290 + i * 0.25), id: "t" },
    ],
    roads: [
      { id: 0, k: "secondary", o: false, b: true, p: line(0, 0, 400, 0, 20), w: 7 },
      { id: 1, k: "secondary", o: false, p: line(400, 0, 400, 300, 15), w: 7 },
    ],
  };
}

function tram(): TransitData {
  const p: number[] = [];
  for (let i = 0; i <= 20; i++) p.push((i * 20) / U, -40 / U);
  return { shapes: [p], runs: [[[2, 0, 400 / U]]], tunnels: [],
    trips: [{ s: 0, k: "tram", n: "T1", t: [[36000, 36000, 0], [36100, 36100, 400 / U]], d: 1 }] };
}

test("cars drive on the graph at their edge's profile height, with no jump between frames", () => {
  const v = new Vehicles(network(), tram(), 3);
  const last = new Map<number, number>();
  let n = 0, worst = 0;
  for (let f = 0; f < 30 * 120; f++) {
    v.step(1 / 30, 8.5);
    for (const c of v.traffic.cars()) {
      const z = v.roadZ(c.rid, c.x, c.y);
      // the height of the point of the road under the car
      const x = c.x * U;
      const want = c.rid === 0 ? 300 + Math.min(Math.max(x, 0), 400) / 400 * 10 : 310;
      assert.ok(Math.abs(z - want) < 0.6, `car on road ${c.rid} at x ${x}: z ${z} vs ${want}`);
      const p = last.get(c.id);
      if (p !== undefined) { worst = Math.max(worst, Math.abs(z - p)); n++; }
      last.set(c.id, z);
    }
  }
  assert.ok(n > 100, "cars moved");
  assert.ok(worst <= 0.5, `largest height step between frames ${worst}`);
});

test("trams run on their matched run and take its profile", () => {
  const v = new Vehicles(network(), tram(), 3);
  v.update(36050, 1, true);
  const t = v.samples.filter((s) => s.kind.startsWith("tram"));
  assert.ok(t.length >= 1, "a tram is out");
  for (const s of t) {
    assert.ok(Math.abs(s.y - 40) < 1e-6, "on its track");
    assert.ok(Math.abs(s.z - (290 + s.x / 400 * 5)) < 0.05, `z ${s.z} at ${s.x}`);
  }
});

test("point in polygon", () => {
  const sq: [number, number][] = [[0, 0], [10, 0], [10, 10], [0, 10]];
  assert.ok(inside(sq, 5, 5));
  assert.ok(!inside(sq, 15, 5));
});

test("labels never overlap after decluttering", () => {
  const labels: Label[] = [];
  for (let i = 0; i < 200; i++) labels.push({ name: `place ${i}`, cat: "x", src: "x", px: (i * 37) % 500, py: (i * 53) % 400,
    depth: 0, prio: 1 + (i % 5) });
  const shown = declutter(labels, 1, (l) => [l.px, l.py], (l) => l.name.length * 7, () => false, { w: 600, h: 500 });
  assert.ok(shown.length > 10);
  for (let i = 0; i < shown.length; i++) for (let j = i + 1; j < shown.length; j++) assert.ok(!overlaps(shown[i].box, shown[j].box));
});
