// Headless audit of the tunnel view's vehicles (check X3, v2/checks/tunnel_checks.py), as scripts/audit.ts:
//   node --experimental-strip-types scripts/xray_audit.ts <release folder> <out folder> [sample seconds]
// Runs the simulation the viewer runs for a simulated day, with the release's tubes loaded and inside the area's
// outline as the viewer draws it, and writes every vehicle every <sample> seconds (samples.bin, float32 x 11: E, N
// local, z, heading, length, width, height, edge, kind code, sim second, and 1 when the viewer draws it in its
// tunnel: Vehicles.deep). Also the viewer's tube mesh (mesh.bin: its triangles, per vertex float32 x 4: E, N local,
// z, tube index).
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { TunnelIndex, tubeMesh, VERTEX_FLOATS, type TunnelsData } from "../src/tunnels.ts";
import { Vehicles, type VehiclesData } from "../src/vehicles.ts";
import type { TransitData } from "../src/sim/transit.ts";

const [rel, out, sampleArg] = process.argv.slice(2);
const read = <T>(name: string) => JSON.parse(readFileSync(join(rel, name), "utf8")) as T;
const SAMPLE = Number(sampleArg ?? 20);
const KIND: Record<string, number> = { car: 0, van: 1, bus: 2, police: 3, ambulance: 4, fire: 5, tram_end: 10, tram_mid: 11,
  train_cab: 20, train_coach: 21, train_loco: 22, funicular: 30 };

const idx = read<{ polygon_en: [number, number][]; camera: { origin_en: [number, number] } }>("index.json");
const tubes = read<TunnelsData>("tunnels.json");
const mesh = tubeMesh(tubes);
const tri = new Float32Array(mesh.vertices * 4);
for (let i = 0; i < mesh.vertices; i++) {
  tri.set(mesh.data.subarray(i * VERTEX_FLOATS, i * VERTEX_FLOATS + 3), i * 4);
  tri[i * 4 + 3] = mesh.data[i * VERTEX_FLOATS + 7];
}
writeFileSync(join(out, "mesh.bin"), Buffer.from(tri.buffer));
const v = new Vehicles(read<VehiclesData>("vehicles.json"), read<TransitData>("transit.json"), 20240607);
v.ring = idx.polygon_en.map(([e, n]) => [e - idx.camera.origin_en[0], n - idx.camera.origin_en[1]] as [number, number]);
v.tunnels = new TunnelIndex(tubes);
const rows: number[] = [];
const dt = 0.1;
const t0 = Date.now();
let n = 0;
for (let sec = 0; sec < 86400; sec += dt) {
  v.step(dt, sec / 3600);
  if (Math.abs(sec / SAMPLE - Math.round(sec / SAMPLE)) < dt / SAMPLE / 2) {
    v.update(sec, 1, true);
    for (const s of v.samples) rows.push(s.x, s.y, s.z, s.h, s.L, s.W, s.H, s.edge, KIND[s.kind] ?? 0, sec, s.deep ? 1 : 0);
    n++;
  }
}
writeFileSync(join(out, "samples.bin"), Buffer.from(new Float32Array(rows).buffer));
const info = { samples: n, sample_s: SAMPLE, rows: rows.length / 11, seconds: (Date.now() - t0) / 1000 };
writeFileSync(join(out, "audit.json"), JSON.stringify(info));
console.log(JSON.stringify(info));
