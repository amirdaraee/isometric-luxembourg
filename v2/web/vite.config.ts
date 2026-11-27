// The v2 viewer's dev server. It serves the built release of an area (python -m v2.build <area> release) under
// /data/: <ISOLUX_DATA>/v2/<V2_AREA>/release/<current>/ (data root default: the repository's data/, area: test).
// It also keeps the review notes written in the viewer (?review, src/notes.ts): POST /notes writes them to
// <ISOLUX_DATA>/v2/<V2_AREA>/review_notes.json, GET /notes reads them back.
import { createReadStream, existsSync, readFileSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { extname, join, resolve, sep } from "node:path";
import { defineConfig, type Plugin } from "vite";

const TYPES: Record<string, string> = { ".json": "application/json", ".webp": "image/webp", ".bin": "application/octet-stream" };

function releaseDir(): string {
  if (process.env.V2_RELEASE) return resolve(process.env.V2_RELEASE);
  const root = resolve(process.env.ISOLUX_DATA ?? resolve(__dirname, "../../data"));
  const area = process.env.V2_AREA ?? "test";
  const rel = join(root, "v2", area, "release");
  const cur = join(rel, "current.json");
  if (!existsSync(cur)) throw new Error(`no release for ${area} under ${rel}: run python -m v2.build ${area} release`);
  return join(rel, JSON.parse(readFileSync(cur, "utf8")).folder);
}

// The bake-off's releases, one per art method (python -m v2.bakeoff register <method>):
// <ISOLUX_DATA>/v2/<V2_AREA>/bakeoff/releases.json = {"a": {"release": "<folder>"}, "b": {...}, ...}
function bakeIndex(): Record<string, { release: string | null; note?: string }> {
  const root = resolve(process.env.ISOLUX_DATA ?? resolve(__dirname, "../../data"));
  const p = join(root, "v2", process.env.V2_AREA ?? "test", "bakeoff", "releases.json");
  return existsSync(p) ? JSON.parse(readFileSync(p, "utf8")) : {};
}

function notesFile(): string {
  const root = resolve(process.env.ISOLUX_DATA ?? resolve(__dirname, "../../data"));
  return join(root, "v2", process.env.V2_AREA ?? "test", "review_notes.json");
}

// The notes are this machine's: a request is answered only when it names this server as a local host and, if a page
// sent it, when that page is this server's own. Another site's page, or one reaching here under another name
// (DNS rebinding), gets 403.
const LOCAL = new Set(["localhost", "127.0.0.1", "[::1]"]);
function ownRequest(headers: { host?: string; origin?: string }): boolean {
  let host: URL;
  try { host = new URL(`http://${headers.host ?? ""}`); } catch { return false; }
  if (!LOCAL.has(host.hostname)) return false;
  if (headers.origin === undefined) return true;
  try { return new URL(headers.origin).host === host.host; } catch { return false; }
}

function sendFile(dir: string, url: string, res: any, next: () => void) {
  const p = resolve(dir, "." + url);
  if (!(p === dir || p.startsWith(dir + sep))) { res.statusCode = 403; res.end(); return; }
  let real: string;
  try { real = realpathSync(p); } catch { res.statusCode = 404; res.end(); return; }
  if (!statSync(real).isFile()) return next();
  res.setHeader("Content-Type", TYPES[extname(real)] ?? "application/octet-stream");
  res.setHeader("Cache-Control", "max-age=60");
  res.setHeader("Content-Length", String(statSync(real).size));
  createReadStream(real).pipe(res);
}

function serveRelease(): Plugin {
  return {
    name: "v2-release",
    configureServer(server) {
      server.config.logger.info(`  v2 release: ${releaseDir()}`);
      server.middlewares.use("/bake", (req, res, next) => {
        const url = decodeURIComponent((req.url ?? "/").split("?")[0]);
        const idx = bakeIndex();
        if (url === "/index.json") {
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(idx));
          return;
        }
        const m = url.match(/^\/([a-z0-9]+)(\/.*)$/);
        const rel = m ? idx[m[1]]?.release : null;
        if (!m || !rel) { res.statusCode = 404; res.end(); return; }
        sendFile(resolve(rel), m[2], res, next);
      });
      server.middlewares.use("/notes", (req, res) => {
        if (!ownRequest(req.headers)) { res.statusCode = 403; res.end(); return; }
        const file = notesFile();
        if (req.method === "GET") {
          res.setHeader("Content-Type", "application/json");
          res.end(existsSync(file) ? readFileSync(file, "utf8") : "[]");
          return;
        }
        if (req.method !== "POST") { res.statusCode = 405; res.end(); return; }
        // a page of this server only: another site's page cannot send JSON here without asking first, and is not answered
        if (!(req.headers["content-type"] ?? "").startsWith("application/json")) { res.statusCode = 415; res.end(); return; }
        let body = "";
        req.setEncoding("utf8");
        req.on("data", (c: string) => { body += c; if (body.length > 1_000_000) req.destroy(); });
        req.on("end", () => {
          let notes: unknown;
          try { notes = JSON.parse(body); } catch { notes = null; }
          if (!Array.isArray(notes)) { res.statusCode = 400; res.end(); return; }
          writeFileSync(file, JSON.stringify(notes, null, 1) + "\n");
          res.statusCode = 204; res.end();
        });
      });
      server.middlewares.use("/data", (req, res, next) => {
        const dir = releaseDir();          // per request: a rebuilt release is served without a restart
        const url = decodeURIComponent((req.url ?? "/").split("?")[0]);
        const p = resolve(dir, "." + url);
        if (!(p === dir || p.startsWith(dir + sep))) { res.statusCode = 403; res.end(); return; }
        let real: string;
        try { real = realpathSync(p); } catch { res.statusCode = 404; res.end(); return; }
        if (!statSync(real).isFile()) return next();
        res.setHeader("Content-Type", TYPES[extname(real)] ?? "application/octet-stream");
        res.setHeader("Cache-Control", "max-age=60");
        res.setHeader("Content-Length", String(statSync(real).size));
        createReadStream(real).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [serveRelease()],
  server: { port: Number(process.env.PORT ?? 5174), strictPort: false },
  build: { target: "es2022" },
});
