// Preview screenshots of the test area for the phase report (called by v2/build/report1.py with a server running):
//   node scripts/previews.mjs <base url> <out folder>
// PNGs; the report stage turns them into JPEGs under 1 MB.
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { open, settle } from "./shot.mjs";

const [base, out] = process.argv.slice(2);
const DATE = "2026-06-23";   // a Tuesday near midsummer: a weekday timetable
const { browser, page } = await open(base, 1600, 1000);
const meta = {};

async function shot(name, q, opts = {}) {
  await page.goto(base + "?noui&" + q);
  await settle(page, opts);
  if (opts.after) await opts.after();
  await page.waitForTimeout(opts.wait ?? 300);
  await page.screenshot({ path: join(out, name + ".png") });
  meta[name] = { q, sun: await page.evaluate(() => ({ az: window.__v2.state.az, el: window.__v2.state.el, hour: window.__v2.state.hour })) };
}

// the hour (on DATE) when the sun stands at an elevation, found in the page's own sun model
async function hourAt(el, after = 12) {
  await page.goto(base + `?noui&nosim&date=${DATE}&hour=12`);
  await page.waitForFunction(() => window.__v2 && window.__v2.setHour);
  return page.evaluate(([el, after]) => {
    let best = after, bd = 1e9;
    for (let h = after; h < 24; h += 1 / 60) {
      window.__v2.setHour(h);
      const d = Math.abs(window.__v2.state.el - el);
      if (d < bd) { bd = d; best = h; }
    }
    return best;
  }, [el, after]);
}

// a second of the day when a train or tram section is near a point (local E, N relative to the camera origin)
async function trainNear(q, le, ln, from = 8 * 3600, radius = 60) {
  await page.goto(base + "?noui&" + q);
  await settle(page, { vehicles: true, shadows: false });
  return page.evaluate(([le, ln, from, radius]) => {
    const v = window.__v2.vehicles;
    for (let s = from; s < from + 6 * 3600; s += 5) {
      v.update(s, 1, true);
      const hit = v.samples.find((x) => x.kind.startsWith("train") || x.kind.startsWith("tram") ? Math.hypot(x.x - le, x.y - ln) < radius : false);
      if (hit) return s;
    }
    return from;
  }, [le, ln, from, radius]);
}

const golden = await hourAt(3.0, 15);
const night = 23.25;
await shot("test_day_1300", `hour=13&date=${DATE}`, { wait: 600 });
await shot("test_golden_hour", `hour=${golden.toFixed(3)}&date=${DATE}`, { wait: 600 });
await shot("test_night", `hour=${night}&date=${DATE}`, { wait: 600 });
await shot("test_shadows_1000", `hour=10&date=${DATE}&x=62600&y=34400&z=0.7&nosim`);
await shot("test_shadows_1600", `hour=16&date=${DATE}&x=62600&y=34400&z=0.7&nosim`);
// close-ups with vehicles: a tunnel portal of the main line and the Pulvermuehl viaduct, at a moment with a train
const O = [70000, 65000];
const PORTAL = [77822.06, 74639.21, 278.8], VIA = [77905, 74780, 278];
const proj = ([e, n, z]) => {
  const R2 = Math.SQRT1_2, le = e - O[0], ln = n - O[1], u = (le + ln) * R2, f = (ln - le) * R2;
  return [(u - 4741.3037109375) / 0.125, (5334.111328125 - (f * 0.5 + z * Math.sqrt(3) / 2)) / 0.125];
};
for (const [name, P] of [["test_portal_vehicles", PORTAL], ["test_viaduct_vehicles", VIA]]) {
  const [x, y] = proj(P);
  const sec = await trainNear(`date=${DATE}&hour=9&nosim&x=${x}&y=${y}&z=1.4`, P[0] - O[0], P[1] - O[1]);
  const hour = sec / 3600;
  await shot(name, `date=${DATE}&hour=${hour.toFixed(4)}&nosim&simtime=900&x=${x.toFixed(0)}&y=${y.toFixed(0)}&z=1.4`, { vehicles: true });
  meta[name].train_second = sec;
}
// layer toggles (one view): everything; light off (the albedo the layers carry); buildings off; trees off;
// only ground, relief and water; the layer map (debug)
const T = `hour=15&date=${DATE}&x=61900&y=33900&z=0.45&nosim`;
await shot("toggle_all", T);
await shot("toggle_nolight", T + "&off=light,look");
await shot("toggle_nobuildings", T + "&off=buildings");
await shot("toggle_notrees", T + "&off=trees");
await shot("toggle_base", T + "&off=transport,buildings,structures,trees,vehicles");
await shot("toggle_layers", T + "&debug=layer");
writeFileSync(join(out, "previews.json"), JSON.stringify(meta, null, 1));
await browser.close();
