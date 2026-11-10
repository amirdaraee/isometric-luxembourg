// Tunnel view: the tube mesh and which vehicles are in a tunnel, on a small synthetic tunnel.
import assert from "node:assert/strict";
import { test } from "node:test";
import { CAP, FLOOR, TunnelIndex, VERTEX_FLOATS, WALL, facesCamera, tubeFrame, tubeMesh, wallTrims, type Tube, type TunnelsData } from "./tunnels.ts";
import { Vehicles, type VehiclesData } from "./vehicles.ts";
import type { TransitData } from "./sim/transit.ts";

// a straight tunnel heading east, 100 m long, 6 m wide, 4.5 m high, a portal at each end
function tube(over: Partial<Tube> = {}): Tube {
  const n = 51, p: number[] = [], z: number[] = [], s: number[] = [], c: number[] = [], d: number[] = [];
  for (let i = 0; i < n; i++) { p.push(1000 + i * 2, 2000); z.push(280); s.push(i * 2); c.push(Math.min(i * 2, 100 - i * 2)); d.push(Math.min(i * 2, 100 - i * 2)); }
  return { id: "t", edge: 0, kind: "tunnel", mode: "road", name: "", chain: "c", w: 6, h: 4.5, portal_m: 8, p, z, s, c, d, ends: [1, 1],
    nodes: [1, 2], ...over };
}
const data = (tubes: Tube[]): TunnelsData => ({ origin_en: [70000, 65000], portal_face_m: 0.3,
  junction: { step_m: 0.25, max_m: 40, segments: 24, slack_m: 0.05 }, depth_cm: [0, 1], tubes });
const faces = (m: { data: Float32Array; vertices: number }) => {
  const out: number[] = [];
  for (let v = 0; v < m.vertices; v += 6) out.push(m.data[v * VERTEX_FLOATS + 6] % 4);
  return out;
};

test("a tube keeps its width and runs on to the portal's face at a portal end", () => {
  const f = tubeFrame(tube(), 0.3)!;
  assert.equal(f.n, 53);
  assert.ok(Math.abs(f.px[0] - 999.7) < 1e-9 && Math.abs(f.px[52] - 1100.3) < 1e-9);
  for (let i = 0; i < f.n; i++) assert.ok(Math.abs(Math.hypot(f.ax[i] - f.bx[i], f.ay[i] - f.by[i]) - 6) < 1e-9);
  // the left edge is to the north of a tube heading east
  assert.ok(f.ay[10] > f.by[10]);
  assert.equal(tubeFrame(tube({ ends: [0, 2] }), 0.3)!.n, 51);
});

test("a corner is mitred: the tube is as wide after the bend as before it", () => {
  const t = tube({ p: [0, 0, 10, 0, 10, 10], z: [0, 0, 0], s: [0, 10, 20], c: [5, 5, 5], d: [0, 10, 0], ends: [0, 0] });
  const f = tubeFrame(t, 0.3)!;
  assert.ok(Math.abs(f.ax[1] - 7) < 1e-9 && Math.abs(f.ay[1] - 3) < 1e-9, "the inner corner");
  assert.ok(Math.abs(f.bx[1] - 13) < 1e-9 && Math.abs(f.by[1] + 3) < 1e-9, "the outer corner");
});

test("the mesh is the floor and the far wall of each segment; a closed end only when its inside faces the camera", () => {
  const m = tubeMesh(data([tube()]));
  const k = faces(m);
  assert.equal(k.filter((x) => x === FLOOR).length, 2 * 52, "two strips, either side of the centre line");
  assert.equal(k.filter((x) => x === WALL).length, 52);
  assert.equal(k.filter((x) => x === CAP).length, 0);
  // the far wall of a tube heading east is its north wall (the camera looks north-west): every wall vertex is on it
  for (let v = 0; v < m.vertices; v++) {
    const o = v * VERTEX_FLOATS;
    if (m.data[o + 6] % 4 === WALL) assert.ok(Math.abs(m.data[o + 1] - 2003) < 1e-4);
    assert.equal(m.data[o + 7], 0);
  }
  assert.ok(facesCamera(0, -1) && !facesCamera(0, 1));
  // the centre line is an edge of the mesh: vertices with a = 0 at the profile's height
  let centre = 0;
  for (let v = 0; v < m.vertices; v++) {
    const o = v * VERTEX_FLOATS;
    if (m.data[o + 6] % 4 === FLOOR && m.data[o + 3] === 0) { centre++; assert.ok(Math.abs(m.data[o + 1] - 2000) < 1e-4 && m.data[o + 2] === 280); }
  }
  assert.ok(centre > 0);
  // and every floor vertex carries its segment of the profile (the centre line is drawn from it)
  for (let v = 0; v < m.vertices; v++) {
    const o = v * VERTEX_FLOATS;
    if (m.data[o + 6] % 4 !== FLOOR) continue;
    assert.ok(m.data[o + 9] === 2000 && m.data[o + 10] === 280 && m.data[o + 12] === 2000 && m.data[o + 13] === 280);
    assert.ok(m.data[o + 8] <= m.data[o] + 1e-3 && m.data[o] <= m.data[o + 11] + 1e-3 && m.data[o + 11] - m.data[o + 8] <= 2 + 1e-3);
  }
  const closed = faces(tubeMesh(data([tube({ ends: [2, 2] })])));
  assert.equal(closed.filter((x) => x === CAP).length, 1);
});

test("a junction is open: a wall is left out as far as it runs inside a tube joined at the same node", () => {
  // the tunnel heading east, cut in two at x = 1050, and a branch 4 m wide leaving north from there
  const half = (i0: number, i1: number, nodes: [number, number], ends: [number, number]): Tube => {
    const t = tube();
    return { ...t, p: t.p.slice(2 * i0, 2 * i1 + 2), z: t.z.slice(i0, i1 + 1), s: t.s.slice(i0, i1 + 1).map((v) => v - t.s[i0]),
      c: t.c.slice(i0, i1 + 1), d: t.d.slice(i0, i1 + 1), nodes, ends };
  };
  const west = half(0, 25, [1, 9], [1, 0]), east = half(25, 50, [9, 2], [0, 1]);
  const branch = tube({ w: 4, p: [1050, 2000, 1050, 2002, 1050, 2030], z: [280, 280, 280], s: [0, 2, 30], c: [9, 9, 9], d: [0, 2, 30],
    nodes: [9, 3], ends: [0, 2] });
  const D = data([west, east, branch]);
  const tr = wallTrims(D, D.tubes.map((t) => tubeFrame(t, 0.3)));
  // the branch's walls start where they leave the tunnel: 3 m (its half width), found to the step and the slack
  assert.ok(tr[2][0].every((v) => v >= 2.75 && v <= 3.0), `branch ${tr[2][0]}`);
  assert.deepEqual(tr[2][1], [0, 0]);
  // the tunnel's north wall opens for the branch, 2 m either side of the node; its south wall is whole
  assert.ok(tr[0][1][0] >= 1.75 && tr[0][1][0] <= 2.0 && tr[1][0][0] >= 1.75 && tr[1][0][0] <= 2.0, `${tr[0][1]} ${tr[1][0]}`);
  assert.equal(tr[0][1][1], 0); assert.equal(tr[1][0][1], 0);
  assert.deepEqual(tr[0][0], [0, 0]);
  // in the mesh: no wall vertex of the tunnel (its north wall, y = 2003) within 1.75 m of the node
  const m = tubeMesh(D);
  let walls = 0;
  for (let v = 0; v < m.vertices; v++) {
    const o = v * VERTEX_FLOATS;
    if (m.data[o + 6] % 4 !== WALL || m.data[o + 7] === 2) continue;
    walls++;
    assert.ok(Math.abs(m.data[o] - 1050) >= 1.75 - 1e-4, `a wall at x ${m.data[o]}`);
  }
  assert.ok(walls > 0);
});

test("the casemates come last in the mesh, so they can be left out", () => {
  const c = tube({ id: "casemate/x", kind: "casemate", edge: -1, ends: [2, 2], nodes: [-1, -1] });
  const m = tubeMesh(data([c, tube()]));
  assert.ok(m.graphVertices > 0 && m.graphVertices < m.vertices);
  assert.equal(m.data[7], 1, "the graph's tunnel (tube 1) is first");
  assert.equal(m.data[m.graphVertices * VERTEX_FLOATS + 7], 0);
  assert.equal(m.data[m.graphVertices * VERTEX_FLOATS + 6], FLOOR + 4);
});

test("a vehicle is in the tunnel once its nearer end is past the portal", () => {
  const ix = new TunnelIndex(data([tube()]));
  assert.ok(!ix.inside(0, 9, 2.2), "its tail is still before the portal");
  assert.ok(ix.inside(0, 10.5, 2.2));
  assert.ok(ix.inside(0, 50, 13.4));
  assert.ok(!ix.inside(0, 95, 2.2), "leaving at the other end");
  assert.ok(!ix.inside(7, 50, 2.2), "not a tube");
});

test("the simulation flags the trams in a tunnel, and no vehicle without the tubes", () => {
  const U = 0.25;
  const s = Array.from({ length: 51 }, (_, i) => (i * 2) / U);
  const p: number[] = [];
  for (let i = 0; i <= 50; i++) p.push((1000 + i * 2) / U, -2000 / U);
  // the tram's tunnel, and a street beside it (the simulation's area is its roads')
  const vd: VehiclesData = { unit_m: U, origin_en: [70000, 65000],
    roads: [{ id: 1, k: "residential", o: false, p: p.map((v, i) => (i % 2 ? v - 100 / U : v)), w: 5 }],
    edges: [{ m: "tram", st: "tunnel", s, z: Array(51).fill(280), id: "t" }, { m: "road", st: "ground", s, z: Array(51).fill(300), id: "r" }] };
  const td: TransitData = { shapes: [p], runs: [[[0, 0, 100 / U]]], tunnels: [],
    trips: [{ s: 0, k: "tram", n: "T1", t: [[36000, 36000, 0], [36100, 36100, 100 / U]], d: 1 }] };
  const v = new Vehicles(vd, td, 3);
  v.update(36050, 1, true);
  assert.ok(v.samples.length >= 1 && v.samples.every((x) => !x.deep), "no tubes loaded: none flagged");
  v.tunnels = new TunnelIndex(data([tube({ mode: "tram" })]));
  let seen = 0;
  for (let sec = 36000; sec <= 36100; sec += 1) {
    v.update(sec, 1, true);
    v.samples.forEach((x, i) => {
      if (!x.kind.startsWith("tram")) { assert.ok(!x.deep, "a car on the street"); return; }
      const along = x.x - 1000, want = Math.min(along, 100 - along) - x.L / 2 >= 8;
      assert.equal(x.deep, want, `tram section at ${along} m`);
      assert.equal(v.deep[i], want ? 1 : 0);
      seen += want ? 1 : 0;
    });
  }
  assert.ok(seen > 20, "tram sections were in the tunnel");
});
