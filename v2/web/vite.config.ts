// The v2 viewer's dev server. It serves the built release of an area (python -m v2.build <area> release) under
// /data/: <ISOLUX_DATA>/v2/<V2_AREA>/release/<current>/ (data root default: the repository's data/, area: test).
import { createReadStream, existsSync, readFileSync, realpathSync, statSync } from "node:fs";
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

function serveRelease(): Plugin {
  return {
    name: "v2-release",
    configureServer(server) {
      server.config.logger.info(`  v2 release: ${releaseDir()}`);
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
