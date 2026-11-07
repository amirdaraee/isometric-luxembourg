import { existsSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Work-in-progress pages that live in public/ for local use only and must never be published.
const LOCAL_ONLY = ["live", "style-test", "compare", "admin"];

/** After a build: drop the local-only folders and the files of switched-off features, add CNAME (custom domain)
 * and .nojekyll for GitHub Pages. */
function release(): Plugin {
  let off = new Set<string>();
  return {
    name: "release",
    apply: "build",
    configResolved(c) {
      const env = loadEnv(c.mode, __dirname, "VITE_");
      const on = new Set((env.VITE_FEATURES_ON ?? "").split(",").map((x) => x.trim()));
      off = new Set((env.VITE_FEATURES_OFF ?? "").split(",").map((x) => x.trim()).filter((x) => x && !on.has(x)));
    },
    closeBundle() {
      const dist = resolve(__dirname, "dist");
      for (const d of LOCAL_ONLY) rmSync(resolve(dist, d), { recursive: true, force: true });
      // no time of day and no seasons: only the day map is ever shown, so the other painted versions stay home
      const metaPath = resolve(dist, "tiles/meta.json");
      if (off.has("timeOfDay") && off.has("seasons") && existsSync(metaPath)) {
        const meta = JSON.parse(readFileSync(metaPath, "utf8"));
        for (const folder of Object.values<string>(meta.variants ?? {})) rmSync(resolve(dist, "tiles", folder), { recursive: true, force: true });
        delete meta.variants;
        writeFileSync(metaPath, JSON.stringify(meta));
      }
      if (off.has("christmas")) rmSync(resolve(dist, "events"), { recursive: true, force: true });
      if (off.has("models3d") && existsSync(resolve(dist, "landmarks")))
        for (const slug of readdirSync(resolve(dist, "landmarks"))) rmSync(resolve(dist, "landmarks", slug, "model.bin"), { force: true });
      if (off.has("transit")) rmSync(resolve(dist, "data/transit.json"), { force: true });
      writeFileSync(resolve(dist, ".nojekyll"), "");
      if (process.env.CNAME) writeFileSync(resolve(dist, "CNAME"), `${process.env.CNAME}\n`);
    },
  };
}

export default defineConfig({
  // "/" for a custom domain; "/isometric-luxembourg/" for https://<user>.github.io/isometric-luxembourg/
  base: process.env.VITE_BASE || "/",
  plugins: [react(), release()],
  server: { port: 3000, open: false },
  define: {
    // Empty serves tiles from public/tiles. Set TILES_URL at build time to serve them from R2 (whole city).
    __TILES_URL__: JSON.stringify(process.env.TILES_URL || ""),
  },
});
