// A screenshot of the viewer: node scripts/shot.mjs "<query>" out.png [width height]
// Waits until the view's tiles are drawn (and the shadows, night lights and vehicles loaded), then saves the canvas.
import { chromium } from "playwright";

export const BROWSER_ARGS = ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-webgpu"];

export async function open(base = process.env.V2_URL ?? "http://localhost:5174/", w = 1600, h = 1000, headless = true) {
  const browser = await chromium.launch({ headless, args: BROWSER_ARGS });
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  return { browser, page, errors, base };
}

export async function settle(page, { vehicles = true, shadows = true } = {}) {
  await page.waitForFunction(() => window.__v2 && (window.__v2.firstViewMs || window.__v2.error), null, { timeout: 120000 });
  const err = await page.evaluate(() => window.__v2.error);
  if (err) throw new Error(err);
  if (shadows) await page.waitForFunction(() => window.__v2.shadowsReady, null, { timeout: 120000 });
  if (vehicles) await page.waitForFunction(() => window.__v2.vehicles, null, { timeout: 120000 });
  await page.waitForFunction(() => window.__v2.missing() === 0, null, { timeout: 120000 });
  await page.waitForTimeout(400);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [q, out, w, h] = process.argv.slice(2);
  const { browser, page, errors, base } = await open(undefined, +(w ?? 1600), +(h ?? 1000));
  await page.goto(base + (q.startsWith("?") ? q : "?" + q));
  await settle(page, { vehicles: !q.includes("nosim") || true });
  await page.locator("#map").screenshot({ path: out });
  const info = await page.evaluate(() => ({ first: window.__v2.firstViewMs, frame: window.__v2.lastFrameMs,
    gpu: (() => { const gl = document.createElement("canvas").getContext("webgl2"); const e = gl.getExtension("WEBGL_debug_renderer_info");
      return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : "?"; })() }));
  console.log(JSON.stringify({ ...info, errors }));
  await browser.close();
}
