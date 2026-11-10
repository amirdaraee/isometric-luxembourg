// Layer 12: v1's traffic simulation and transit on the v2 graph, lifted onto each edge's height profile.
// Positions come from the graph only (layer-12 rule 1): a car's height is its road's profile at the point of the
// road it is on; a tram or train section's is its track edge's profile. The boxes are depth-tested per pixel by
// the compositor (rule 2). No DOM here, so the headless audit (scripts/audit.ts) runs it in Node.

import { Traffic, type RoadLine } from "./sim/traffic.ts";
import { prepareShapes, transitSections, type Shape, type TransitData } from "./sim/transit.ts";
import type { TunnelIndex } from "./tunnels.ts";

export interface EdgeProfile { m: string; st: string; s: number[]; z: number[]; id: string }
export interface VehiclesData { unit_m: number; origin_en: [number, number]; edges: EdgeProfile[]; roads: RoadLine[] }

export const SIZES: Record<string, [number, number, number]> = {
  car: [4.4, 1.8, 1.45], van: [5.4, 2.0, 2.2], bus: [12.0, 2.55, 3.1], police: [4.7, 1.85, 1.5],
  ambulance: [5.9, 2.1, 2.6], fire: [8.5, 2.5, 3.2], tram_end: [9.5, 2.65, 3.6], tram_mid: [8.7, 2.65, 3.6],
  train_cab: [26.8, 2.9, 4.6], train_coach: [26.8, 2.9, 4.6], train_loco: [19.0, 2.9, 4.6], funicular: [14.0, 2.6, 3.4],
};
const COLOUR: Record<string, number> = { car: 0, van: 2, bus: 1, police: 6, ambulance: 2, fire: 5, tram_end: 4,
  tram_mid: 4, train_cab: 5, train_coach: 6, train_loco: 5, funicular: 7 };

/** Busy factor of v1's viewer by the hour (web/src/components/Overlay.tsx). */
export function busyAt(hr: number): number {
  return hr < 5 ? 0.12 : hr < 6.5 ? 0.35 : hr < 9.5 ? 1 : hr < 16 ? 0.75 : hr < 19 ? 1 : hr < 22 ? 0.5 : 0.25;
}

export interface Sample {
  id: number; kind: string; x: number; y: number; z: number; h: number; L: number; W: number; H: number;
  edge: number; tunnel: boolean; bridge: boolean;
  deep: boolean;            // in a tunnel past its portal (tunnel view draws it in the tube)
}

/** Point in polygon (ray casting); ring as [x, y][]. */
export function inside(ring: [number, number][], x: number, y: number): boolean {
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

function interp(xs: number[], ys: number[], x: number): number {
  const n = xs.length;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xs[m] <= x) lo = m; else hi = m; }
  const t = (x - xs[lo]) / (xs[hi] - xs[lo] || 1);
  return ys[lo] + (ys[hi] - ys[lo]) * t;
}

export class Vehicles {
  traffic: Traffic;
  shapes: Shape[];
  roadById = new Map<number, RoadLine & { cum: number[] }>();
  area: { x0: number; y0: number; x1: number; y1: number };
  inst = new Float32Array(4 * 4096);
  size = new Float32Array(4 * 4096);
  count = 0;
  samples: Sample[] = [];
  /** Tunnel view: per vehicle, 1 when it is in a tunnel past its portal (needs `tunnels`). */
  deep = new Uint8Array(4096);
  tunnels: TunnelIndex | null = null;

  /** The area's outline in local metres (E, N relative to the camera origin): vehicles are drawn inside it. */
  ring: [number, number][] | null = null;

  data: VehiclesData;
  transit: TransitData;

  constructor(data: VehiclesData, transit: TransitData, seed = 20240607) {
    this.data = data;
    this.transit = transit;
    for (const r of data.roads) {
      const cum = [0];
      for (let i = 2; i < r.p.length; i += 2) cum.push(cum[cum.length - 1] + Math.hypot(r.p[i] - r.p[i - 2], r.p[i + 1] - r.p[i - 1]));
      this.roadById.set(r.id, { ...r, cum });
    }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const r of data.roads) for (let i = 0; i < r.p.length; i += 2) {
      x0 = Math.min(x0, r.p[i]); x1 = Math.max(x1, r.p[i]); y0 = Math.min(y0, r.p[i + 1]); y1 = Math.max(y1, r.p[i + 1]);
    }
    this.area = { x0, y0, x1, y1 };
    this.traffic = new Traffic(data.roads, { seed, mpp: data.unit_m, maxCars: 900 });
    this.shapes = prepareShapes(transit, false);
  }

  /** Height of a point (sim units) on a road: its nearest point on the road's line, then the edge's profile. */
  roadZ(rid: number, x: number, y: number): number {
    const e = this.data.edges[rid];
    if (!this.roadById.has(rid) || !e) return 0;
    return interp(e.s, e.z, this.roadS(rid, x, y));
  }

  /** How far along its road (sim units) a point is: its nearest point on the road's line. */
  roadS(rid: number, x: number, y: number): number {
    const r = this.roadById.get(rid);
    if (!r) return 0;
    const p = r.p;
    let best = Infinity, bs = 0;
    for (let i = 0; i + 3 < p.length; i += 2) {
      const ax = p[i], ay = p[i + 1], dx = p[i + 2] - ax, dy = p[i + 3] - ay;
      const L2 = dx * dx + dy * dy || 1e-9;
      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L2));
      const qx = ax + dx * t - x, qy = ay + dy * t - y, d = qx * qx + qy * qy;
      if (d < best) { best = d; bs = r.cum[i / 2] + Math.sqrt(L2) * t; }
    }
    return bs;
  }

  /** A car's height: on a lane, its road's profile; crossing a junction (whose box can join nodes up to 20 m
   * apart), from the road it leaves to the road it enters, in step with how far across it is. */
  carZ(c: { rid: number; rid0: number; u: number; x: number; y: number }): number {
    const z1 = this.roadZ(c.rid, c.x, c.y);
    if (c.rid0 < 0 || c.rid0 === c.rid) return z1;
    const z0 = this.roadZ(c.rid0, c.x, c.y);
    return z0 + (z1 - z0) * c.u;
  }

  edgeZ(edge: number, s: number): number {
    const e = this.data.edges[edge];
    return e ? interp(e.s, e.z, s) : 0;
  }

  step(dt: number, hour: number) {
    this.traffic.step(dt, this.area, busyAt(hour));
  }

  /** Every vehicle now, as boxes for the compositor (and as samples for the audit). */
  update(secOfDay: number, dayMask: number, keepSamples = false): number {
    const U = this.data.unit_m;
    let n = 0;
    if (keepSamples) this.samples = [];
    const tun = this.tunnels;
    // along: how far along its edge (sim units) the vehicle is, asked only for an edge that is a tube
    const put = (id: number, kind: string, x: number, y: number, z: number, hScreen: number, edge: number, tunnel: boolean, bridge: boolean,
      along: () => number) => {
      const sz = SIZES[kind] ?? SIZES.car;
      if (n >= this.inst.length / 4) return;
      const le = x * U, ln = -y * U, h = -hScreen;
      if (this.ring && !inside(this.ring, le, ln)) return;
      this.inst[n * 4] = le; this.inst[n * 4 + 1] = ln; this.inst[n * 4 + 2] = z; this.inst[n * 4 + 3] = h;
      this.size[n * 4] = sz[0]; this.size[n * 4 + 1] = sz[1]; this.size[n * 4 + 2] = sz[2]; this.size[n * 4 + 3] = COLOUR[kind] ?? 0;
      const deep = !!tun && tun.has(edge) && tun.inside(edge, along() * U, sz[0] / 2);
      this.deep[n] = deep ? 1 : 0;
      if (keepSamples) this.samples.push({ id, kind, x: le, y: ln, z, h, L: sz[0], W: sz[1], H: sz[2], edge, tunnel, bridge, deep });
      n++;
    };
    for (const c of this.traffic.cars()) {
      put(c.id, c.type, c.x, c.y, this.carZ(c), c.headingScreenRad, c.rid, c.tunnel, c.bridge, () => this.roadS(c.rid, c.x, c.y));
    }
    const box: [number, number, number, number] = [this.area.x0 - 2000, this.area.y0 - 2000, this.area.x1 + 2000, this.area.y1 + 2000];
    for (const s of transitSections(this.transit, this.shapes, secOfDay, dayMask, box)) {
      const z = s.way >= 0 ? this.edgeZ(s.way, s.s) : 0;
      const e = this.data.edges[s.way];
      put(1_000_000 + s.shape * 1000 + Math.round(s.d0) % 1000, s.type, s.x, s.y, z, s.h, s.way, e?.st === "tunnel", e?.st === "bridge", () => s.s);
    }
    this.count = n;
    return n;
  }
}
