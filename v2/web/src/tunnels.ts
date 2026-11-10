// Tunnel view (x-ray, v2/docs/specs/tunnel-view.md): the tubes of tunnels.json as a mesh, and which vehicles are
// inside a tunnel. The mesh rule is the one of v2/layers/tunnels.py (tube_frame, tube_mesh), which the checks use:
// per segment the floor (two strips, either side of the centre line, so the floor's height along it is the profile's
// whatever the corners do), and each wall and closed end whose inside faces the camera; where tubes join at a node,
// a wall is left out as far as it runs inside another of them (wallTrims). No DOM here (Node tests).

export interface Tube {
  id: string; edge: number; kind: string; mode: string; name: string; chain: string;
  w: number; h: number; portal_m: number;
  p: number[];              // centre line of the floor: E, N relative to the camera origin, flat (m)
  z: number[];              // floor height per point (m)
  s: number[];              // distance along the edge per point (m)
  c: number[];              // depth of the floor under the surface per point (m)
  d: number[];              // distance into the tunnel from its nearest portal per point (m)
  ends: [number, number];   // 0 joins another tube, 1 a portal, 2 closed
  nodes: [number, number];  // the graph node at each end (-1: none): tubes with the same node join there
}
export interface Junction { step_m: number; max_m: number; segments: number; slack_m: number }
export interface TunnelsData { origin_en: [number, number]; portal_face_m: number; junction: Junction; depth_cm: [number, number];
  tubes: Tube[] }

export const FLOOR = 0, WALL = 1, CAP = 2;
export const PORTAL = 1, CLOSED = 2;
// A vertex: x, y, z (local E, N, up), a, b, cover, face + 4 * family, tube index, then (floors) the two ends of the
// segment of the centre line the face lies on (x, y, z each). a runs across a face (floor: -1 and 1 at its edges;
// wall: 1 at its top; closed end: +-1 at its sides, with b = 1 at its top). On a floor, b is how far along the tube
// the point is into the part where the wall of its side stands (m; negative where the wall is left out at a
// junction: no line is drawn along the floor's edge there). The centre line is drawn by the floor itself, from the
// distance on screen to its segment: the profile's own projection.
export const VERTEX_FLOATS = 14;
const C30 = Math.sqrt(3) / 2, R2 = Math.SQRT1_2;
/** The camera's view direction on the ground (E, N), into the scene: v2/layers/common.py VIEW. */
export const VIEW_EN: [number, number] = [-R2 * C30, R2 * C30];

/** A vertical face whose inside normal is (nx, ny) shows its inside to the camera. */
export function facesCamera(nx: number, ny: number): boolean {
  return nx * VIEW_EN[0] + ny * VIEW_EN[1] < 0;
}

export interface Frame { n: number; px: number[]; py: number[]; z: number[]; c: number[]; ax: number[]; ay: number[];
  bx: number[]; by: number[]; dx: number[]; dy: number[] }

/** The floor of a tube: its centre line, and its left (a) and right (b) edges. A portal end runs `face` m on, to the
 * face layer 4 draws there; corners are mitred, so the tube keeps its width round a bend. */
export function tubeFrame(t: Tube, face: number): Frame | null {
  const px: number[] = [], py: number[] = [], z: number[] = [], c: number[] = [];
  for (let i = 0; i < t.z.length; i++) {
    const x = t.p[2 * i], y = t.p[2 * i + 1];
    if (i > 0 && Math.hypot(x - px[px.length - 1], y - py[py.length - 1]) <= 1e-6) continue;
    px.push(x); py.push(y); z.push(t.z[i]); c.push(t.c[i]);
  }
  if (px.length < 2) return null;
  if (t.ends[0] === PORTAL) {
    const L = Math.hypot(px[0] - px[1], py[0] - py[1]);
    px.unshift(px[0] + ((px[0] - px[1]) / L) * face); py.unshift(py[0] + ((py[0] - py[1]) / L) * face);
    z.unshift(z[0]); c.unshift(c[0]);
  }
  if (t.ends[1] === PORTAL) {
    const k = px.length - 1, L = Math.hypot(px[k] - px[k - 1], py[k] - py[k - 1]);
    px.push(px[k] + ((px[k] - px[k - 1]) / L) * face); py.push(py[k] + ((py[k] - py[k - 1]) / L) * face);
    z.push(z[k]); c.push(c[k]);
  }
  const n = px.length;
  const dx: number[] = [], dy: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    const L = Math.hypot(px[i + 1] - px[i], py[i + 1] - py[i]);
    dx.push((px[i + 1] - px[i]) / L); dy.push((py[i + 1] - py[i]) / L);
  }
  const ax: number[] = [], ay: number[] = [], bx: number[] = [], by: number[] = [];
  for (let i = 0; i < n; i++) {
    const i0 = Math.max(i - 1, 0), i1 = Math.min(i, n - 2);
    let tx = i0 === i1 ? dx[i1] : dx[i0] + dx[i1], ty = i0 === i1 ? dy[i1] : dy[i0] + dy[i1];
    const L = Math.hypot(tx, ty);
    if (L > 1e-6) { tx /= L; ty /= L; } else { tx = dx[i1]; ty = dy[i1]; }
    const cos = i0 === i1 ? 1 : tx * dx[i1] + ty * dy[i1];
    const half = t.w / 2 / Math.max(cos, 0.5);
    ax.push(px[i] - ty * half); ay.push(py[i] + tx * half);
    bx.push(px[i] + ty * half); by.push(py[i] - tx * half);
  }
  return { n, px, py, z, c, ax, ay, bx, by, dx, dy };
}

function along(x: number[], y: number[]): number[] {
  const L = [0];
  for (let i = 1; i < x.length; i++) L.push(L[i - 1] + Math.hypot(x[i] - x[i - 1], y[i] - y[i - 1]));
  return L;
}

/** Per tube, how much of each wall is left out at each end: [[left, right] at its first end, [left, right] at its
 * last], in metres along the wall. Where tubes join at a node, a wall is left out from the node as far as it runs
 * inside another of them (within its half width less slack_m of its centre line): the first point clear of them,
 * looked for every step_m, up to max_m. (v2/layers/tunnels.py wall_trims.) */
export function wallTrims(data: TunnelsData, frames: (Frame | null)[]): number[][][] {
  const J = data.junction;
  const at = new Map<number, [number, number][]>();
  data.tubes.forEach((t, i) => {
    for (const end of [0, 1]) {
      const node = t.nodes?.[end] ?? -1;
      if (!frames[i] || node < 0) continue;
      if (!at.has(node)) at.set(node, []);
      at.get(node)!.push([i, end]);
    }
  });
  const out = data.tubes.map(() => [[0, 0], [0, 0]]);
  for (const ends of at.values()) {
    if (ends.length < 2) continue;
    for (const [i, end] of ends) {
      const f = frames[i]!;
      // the other tubes' centre lines from the node, and their half widths
      const others = ends.filter(([j]) => j !== i).map(([j, e2]) => {
        const g = frames[j]!, n = Math.min(g.n, J.segments + 1), x: number[] = [], y: number[] = [];
        for (let k = 0; k < n; k++) { const q = e2 === 0 ? k : g.n - 1 - k; x.push(g.px[q]); y.push(g.py[q]); }
        return { x, y, r: data.tubes[j].w / 2 - J.slack_m };
      });
      const inside = (qx: number, qy: number) => others.some((o) => {
        for (let k = 0; k + 1 < o.x.length; k++) {
          const dx = o.x[k + 1] - o.x[k], dy = o.y[k + 1] - o.y[k];
          const t = Math.max(0, Math.min(1, ((qx - o.x[k]) * dx + (qy - o.y[k]) * dy) / Math.max(dx * dx + dy * dy, 1e-12)));
          if (Math.hypot(qx - o.x[k] - dx * t, qy - o.y[k] - dy * t) < o.r) return true;
        }
        return false;
      });
      [[f.ax, f.ay], [f.bx, f.by]].forEach(([wx0, wy0], side) => {
        const wx = end === 0 ? wx0 : [...wx0].reverse(), wy = end === 0 ? wy0 : [...wy0].reverse();
        const L = along(wx, wy), reach = Math.min(L[L.length - 1], J.max_m);
        let trim = reach, k = 0;
        for (let m = 0; m * J.step_m <= reach + 1e-9; m++) {
          const t = m * J.step_m;
          while (k + 2 < L.length && L[k + 1] < t) k++;
          const u = Math.max(0, Math.min(1, (t - L[k]) / Math.max(L[k + 1] - L[k], 1e-12)));
          if (!inside(wx[k] + (wx[k + 1] - wx[k]) * u, wy[k] + (wy[k + 1] - wy[k]) * u)) { trim = t; break; }
        }
        out[i][end][side] = trim;
      });
    }
  }
  return out;
}

/** 0: a tunnel of the graph; 1: a casemate gallery (its own fill, and it can be switched off). */
export function family(t: Tube): number {
  return t.kind === "casemate" ? 1 : 0;
}

/** The drawn faces of every tube as triangles (VERTEX_FLOATS per vertex). `tubes` keep their index (the tube index
 * of the debug frames); the casemates come last in the buffer so they can be left out: `graphVertices` is where
 * they start. */
export function tubeMesh(data: TunnelsData): { data: Float32Array; vertices: number; graphVertices: number } {
  const out: number[] = [];
  let graphVertices = 0;
  const NONE = [0, 0, 0, 0, 0, 0];
  const quad = (P: number[][], A: number[][], cover: number[], code: number, idx: number, seg: number[] = NONE) => {
    for (const k of [0, 1, 2, 0, 2, 3]) out.push(P[k][0], P[k][1], P[k][2], A[k][0], A[k][1], cover[k], code, idx, ...seg);
  };
  const frames = data.tubes.map((t) => tubeFrame(t, data.portal_face_m));
  const trims = wallTrims(data, frames);
  for (const fam of [0, 1]) {
    data.tubes.forEach((t, idx) => {
      if (family(t) !== fam) return;
      const f = frames[idx];
      if (!f) return;
      const { n, px, py, z, c, ax, ay, bx, by, dx, dy } = f;
      const walls = [{ x: ax, y: ay, L: along(ax, ay) }, { x: bx, y: by, L: along(bx, by) }];
      // a wall of segment i, between what is left out of it at the tube's two ends
      const wall = (side: number, i: number) => {
        const { x, y, L } = walls[side], j = i + 1;
        const lo = Math.max(L[i], trims[idx][0][side]), hi = Math.min(L[j], L[n - 1] - trims[idx][1][side]);
        if (hi - lo < 1e-6) return;
        const u0 = (lo - L[i]) / (L[j] - L[i]), u1 = (hi - L[i]) / (L[j] - L[i]);
        const at = (u: number) => [x[i] + (x[j] - x[i]) * u, y[i] + (y[j] - y[i]) * u, z[i] + (z[j] - z[i]) * u, c[i] + (c[j] - c[i]) * u];
        const p = at(u0), q = at(u1);
        quad([[p[0], p[1], p[2]], [q[0], q[1], q[2]], [q[0], q[1], q[2] + t.h], [p[0], p[1], p[2] + t.h]],
          [[0, 0], [0, 0], [1, 0], [1, 0]], [p[3], q[3], q[3], p[3]], WALL + 4 * fam, idx);
      };
      // how far point i of a side is into the part of the tube where that side's wall stands
      const stands = (side: number, i: number) => {
        const L = walls[side].L;
        return Math.min(L[i] - trims[idx][0][side], L[n - 1] - trims[idx][1][side] - L[i]) + 1e-3;
      };
      for (let i = 0; i < n - 1; i++) {
        const j = i + 1, cv = [c[i], c[j], c[j], c[i]];
        const seg = [px[i], py[i], z[i], px[j], py[j], z[j]];
        const ai = stands(0, i), aj = stands(0, j), bi = stands(1, i), bj = stands(1, j);
        quad([[ax[i], ay[i], z[i]], [ax[j], ay[j], z[j]], [px[j], py[j], z[j]], [px[i], py[i], z[i]]],
          [[-1, ai], [-1, aj], [0, aj], [0, ai]], cv, FLOOR + 4 * fam, idx, seg);
        quad([[px[i], py[i], z[i]], [px[j], py[j], z[j]], [bx[j], by[j], z[j]], [bx[i], by[i], z[i]]],
          [[0, bi], [0, bj], [1, bj], [1, bi]], cv, FLOOR + 4 * fam, idx, seg);
        const lx = -dy[i], ly = dx[i];                   // the segment's left
        if (facesCamera(-lx, -ly)) wall(0, i);
        if (facesCamera(lx, ly)) wall(1, i);
      }
      for (const [end, i, k, sign] of [[0, 0, 0, 1], [1, n - 1, n - 2, -1]] as const) {
        if (t.ends[end] === CLOSED && facesCamera(sign * dx[k], sign * dy[k]))
          quad([[ax[i], ay[i], z[i]], [bx[i], by[i], z[i]], [bx[i], by[i], z[i] + t.h], [ax[i], ay[i], z[i] + t.h]],
            [[-1, 0], [1, 0], [1, 1], [-1, 1]], [c[i], c[i], c[i], c[i]], CAP + 4 * fam, idx);
      }
    });
    if (fam === 0) graphVertices = out.length / VERTEX_FLOATS;
  }
  return { data: new Float32Array(out), vertices: out.length / VERTEX_FLOATS, graphVertices };
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

/** Which vehicles are in a tunnel past its portal (rule 4): by the graph edge they are on and how far along it. */
export class TunnelIndex {
  byEdge = new Map<number, Tube>();

  constructor(data: TunnelsData) {
    for (const t of data.tubes) if (t.edge >= 0) this.byEdge.set(t.edge, t);
  }

  has(edge: number): boolean { return this.byEdge.has(edge); }

  /** A vehicle whose centre is `s` m along graph edge `edge`, `halfLength` m long each way: its nearer end is past
   * the tunnel's portal (the point where a vehicle is first a full clearance under its cover). */
  inside(edge: number, s: number, halfLength: number): boolean {
    const t = this.byEdge.get(edge);
    if (!t) return false;
    return interp(t.s, t.d, s) - halfLength >= t.portal_m;
  }
}
