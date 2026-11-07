/**
 * Feedback API for the isometric map of Luxembourg City.
 *
 * Visitors mark a box on the map and send a private note to the map's author. Nobody but the author can read
 * the notes: listing, updating and deleting need the admin token. Everything a visitor sends is checked here,
 * on the server; the viewer's own checks are only for convenience.
 *
 *   POST   /api/comments              send a note (Turnstile, rate limits, strict schema)
 *   GET    /api/comments?status=&limit=&before=   list notes, newest first (admin)
 *   PATCH  /api/comments/:id {status} mark a note new or done (admin)
 *   DELETE /api/comments/:id          delete a note (admin)
 */

export interface Env {
  DB: D1Database;
  BURST?: RateLimit;
  TURNSTILE_SECRET: string;
  IP_SALT: string;
  ADMIN_TOKEN: string;
  ALLOWED_ORIGINS?: string;
  TURNSTILE_HOSTNAMES?: string;
}

// ---- Limits ----------------------------------------------------------------------------------------------
const MAP_W = 26624;
const MAP_H = 14336;
const MIN_BOX_SIDE = 4; // map px; anything smaller is a click, not a box
const MAX_BOX_AREA = 64_000_000; // map px², about 8000 x 8000 (2 km x 2 km), 17 % of the map
const MAX_BODY_BYTES = 4096;
const MAX_TEXT = 1000;
const MAX_CONTACT = 120;
const MAX_FEATURES = 400;
const MAX_TOKEN = 2048;
const MAX_UA = 200;

const TEN_MIN = 10 * 60 * 1000;
const DAY = 24 * 60 * 60 * 1000;
const POSTS_PER_10_MIN = 5; // per client (salted IP hash)
const POSTS_PER_DAY = 20; // per client
const GLOBAL_PER_DAY = 300; // all clients together, so a botnet cannot use up D1's free daily quota
const ADMIN_FAILS_PER_10_MIN = 10; // per client
const IP_HASH_RETENTION = 30 * DAY;

const DEFAULT_ORIGINS = "https://isometric.lu,https://www.isometric.lu,http://localhost:3000";
const SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

// ---- Responses -------------------------------------------------------------------------------------------
const SECURITY_HEADERS: Record<string, string> = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
  "Cross-Origin-Resource-Policy": "same-site",
  Vary: "Origin",
};

function allowedOrigins(env: Env): Set<string> {
  return new Set((env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(",").map((s) => s.trim()).filter(Boolean));
}

function corsHeaders(origin: string | null, env: Env): Record<string, string> {
  if (!origin || !allowedOrigins(env).has(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "600",
  };
}

function json(body: unknown, status: number, cors: Record<string, string>, extra: Record<string, string> = {}): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { ...SECURITY_HEADERS, ...cors, ...extra } });
}

const err = (status: number, error: string, cors: Record<string, string>, extra?: Record<string, string>) =>
  json({ error }, status, cors, extra);

// ---- Helpers ---------------------------------------------------------------------------------------------
async function sha256(s: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
}

const hex = (b: Uint8Array) => [...b].map((x) => x.toString(16).padStart(2, "0")).join("");

async function clientHash(request: Request, env: Env): Promise<string> {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  return hex(await sha256(`${env.IP_SALT}:${ip}`));
}

/** Constant-time comparison: both sides are hashed first, so length and content leak nothing. */
async function sameSecret(given: string, expected: string): Promise<boolean> {
  if (!expected) return false;
  const [a, b] = await Promise.all([sha256(given), sha256(expected)]);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

/** Read at most `max` bytes of the body; null if it is longer. */
async function readBody(request: Request, max: number): Promise<string | null> {
  const declared = Number(request.headers.get("Content-Length") || "0");
  if (declared > max) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) { all.set(c, at); at += c.byteLength; }
  return new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(all);
}

/**
 * Increment fixed-window counters and return their new values. One batch, so it is a single round trip and
 * atomic in D1.
 */
async function bump(db: D1Database, keys: { key: string; expires: number }[]): Promise<number[]> {
  const stmt = db.prepare(
    "INSERT INTO counters (key, n, expires_at) VALUES (?1, 1, ?2) ON CONFLICT(key) DO UPDATE SET n = n + 1 RETURNING n",
  );
  const res = await db.batch<{ n: number }>(keys.map((k) => stmt.bind(k.key, k.expires)));
  return res.map((r) => r.results[0]?.n ?? 0);
}

async function count(db: D1Database, key: string): Promise<number> {
  const row = await db.prepare("SELECT n FROM counters WHERE key = ?1").bind(key).first<{ n: number }>();
  return row?.n ?? 0;
}

// ---- Validation ------------------------------------------------------------------------------------------
type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const onlyKeys = (o: Obj, allowed: string[]) => Object.keys(o).every((k) => allowed.includes(k));
/** Drop control characters other than tab and newline; normalise line endings. */
const clean = (s: string) => s.replace(/\r\n?/g, "\n").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "").trim();

interface Comment {
  box: { x0: number; y0: number; x1: number; y1: number };
  text: string;
  contact: string | null;
  view: { x: number; y: number; z: number } | null;
  features: string | null;
  turnstileToken: string;
}

function validate(body: unknown): Comment | null {
  if (!isObj(body) || !onlyKeys(body, ["box", "text", "contact", "view", "features", "turnstileToken"])) return null;
  const { box, text, contact, view, features, turnstileToken } = body;

  if (!isObj(box) || !onlyKeys(box, ["x0", "y0", "x1", "y1"])) return null;
  const { x0, y0, x1, y1 } = box;
  if (![x0, y0, x1, y1].every(isNum)) return null;
  const [bx0, by0, bx1, by1] = [x0, y0, x1, y1] as number[];
  if (bx0 < 0 || by0 < 0 || bx1 > MAP_W || by1 > MAP_H) return null;
  if (bx1 - bx0 < MIN_BOX_SIDE || by1 - by0 < MIN_BOX_SIDE) return null;
  if ((bx1 - bx0) * (by1 - by0) > MAX_BOX_AREA) return null;

  if (typeof text !== "string") return null;
  const t = clean(text);
  if (t.length < 1 || t.length > MAX_TEXT) return null;

  let c: string | null = null;
  if (contact !== undefined && contact !== null) {
    if (typeof contact !== "string") return null;
    c = clean(contact).replace(/\n/g, " ");
    if (c.length > MAX_CONTACT) return null;
    if (!c) c = null;
  }

  let v: Comment["view"] = null;
  if (view !== undefined && view !== null) {
    if (!isObj(view) || !onlyKeys(view, ["x", "y", "z"])) return null;
    if (!isNum(view.x) || !isNum(view.y) || !isNum(view.z)) return null;
    if (Math.abs(view.x) > 2 * MAP_W || Math.abs(view.y) > 2 * MAP_H || view.z <= 0 || view.z > 10) return null;
    v = { x: view.x, y: view.y, z: view.z };
  }

  let f: string | null = null;
  if (features !== undefined && features !== null) {
    if (typeof features !== "string" || features.length > MAX_FEATURES || !/^[A-Za-z0-9,]*$/.test(features)) return null;
    f = features || null;
  }

  if (typeof turnstileToken !== "string" || turnstileToken.length < 1 || turnstileToken.length > MAX_TOKEN) return null;

  return { box: { x0: bx0, y0: by0, x1: bx1, y1: by1 }, text: t, contact: c, view: v, features: f, turnstileToken };
}

// ---- Turnstile -------------------------------------------------------------------------------------------
async function turnstileOk(token: string, ip: string | null, env: Env): Promise<boolean> {
  if (!env.TURNSTILE_SECRET) return false;
  const form = new FormData();
  form.append("secret", env.TURNSTILE_SECRET);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  form.append("idempotency_key", crypto.randomUUID());
  try {
    const r = await fetch(SITEVERIFY, { method: "POST", body: form });
    if (!r.ok) return false;
    const out = (await r.json()) as { success?: boolean; hostname?: string };
    if (out.success !== true) return false;
    const hosts = (env.TURNSTILE_HOSTNAMES || "").split(",").map((s) => s.trim()).filter(Boolean);
    return hosts.length === 0 || (!!out.hostname && hosts.includes(out.hostname));
  } catch {
    return false;
  }
}

// ---- Handlers --------------------------------------------------------------------------------------------
async function postComment(request: Request, env: Env, cors: Record<string, string>): Promise<Response> {
  // Browsers always send Origin on a cross-site POST; anything else is not the map.
  if (!cors["Access-Control-Allow-Origin"]) return err(403, "forbidden", cors);
  const who = await clientHash(request, env);
  if (env.BURST && !(await env.BURST.limit({ key: `post:${who}` })).success)
    return err(429, "too_many_requests", cors, { "Retry-After": "60" });

  const type = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (type !== "application/json") return err(415, "unsupported_media_type", cors);
  let raw: string | null;
  try {
    raw = await readBody(request, MAX_BODY_BYTES);
  } catch {
    return err(400, "invalid_request", cors);
  }
  if (raw === null) return err(413, "payload_too_large", cors);
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return err(400, "invalid_json", cors);
  }
  const c = validate(body);
  if (!c) return err(400, "invalid_request", cors);

  // Counted before Turnstile, so failed attempts use up the allowance too.
  const now = Date.now();
  const w10 = Math.floor(now / TEN_MIN);
  const day = Math.floor(now / DAY);
  const [n10, nDay] = await bump(env.DB, [
    { key: `post10m:${who}:${w10}`, expires: (w10 + 1) * TEN_MIN },
    { key: `postday:${who}:${day}`, expires: (day + 1) * DAY },
  ]);
  if (n10 > POSTS_PER_10_MIN) return err(429, "too_many_requests", cors, { "Retry-After": String(Math.ceil(((w10 + 1) * TEN_MIN - now) / 1000)) });
  if (nDay > POSTS_PER_DAY) return err(429, "too_many_requests", cors, { "Retry-After": String(Math.ceil(((day + 1) * DAY - now) / 1000)) });
  if ((await count(env.DB, `global:${day}`)) >= GLOBAL_PER_DAY) return err(503, "busy", cors, { "Retry-After": "3600" });

  if (!(await turnstileOk(c.turnstileToken, request.headers.get("CF-Connecting-IP"), env))) return err(403, "verification_failed", cors);

  const cf = (request as Request & { cf?: { country?: string } }).cf;
  const country = typeof cf?.country === "string" ? cf.country.slice(0, 2) : null;
  const ua = (request.headers.get("User-Agent") || "").slice(0, MAX_UA) || null;
  const [ins] = await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO comments (created_at, x0, y0, x1, y1, text, contact, view_x, view_y, view_z, features, ip_hash, country, user_agent)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14) RETURNING id`,
    ).bind(now, c.box.x0, c.box.y0, c.box.x1, c.box.y1, c.text, c.contact, c.view?.x ?? null, c.view?.y ?? null, c.view?.z ?? null,
      c.features, who, country, ua),
    env.DB.prepare("INSERT INTO counters (key, n, expires_at) VALUES (?1, 1, ?2) ON CONFLICT(key) DO UPDATE SET n = n + 1")
      .bind(`global:${day}`, (day + 1) * DAY),
  ]);
  const id = (ins.results[0] as { id?: number } | undefined)?.id;
  return json({ ok: true, id }, 201, cors);
}

/** Null when authorised, otherwise the error response. Failed attempts are rate limited per client. */
async function adminGate(request: Request, env: Env, cors: Record<string, string>): Promise<Response | null> {
  const origin = request.headers.get("Origin");
  if (origin && !cors["Access-Control-Allow-Origin"]) return err(403, "forbidden", cors);
  const who = await clientHash(request, env);
  const now = Date.now();
  const w10 = Math.floor(now / TEN_MIN);
  const failKey = `adminfail:${who}:${w10}`;
  if ((await count(env.DB, failKey)) >= ADMIN_FAILS_PER_10_MIN) return err(429, "too_many_requests", cors, { "Retry-After": "600" });
  const auth = request.headers.get("Authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (token && (await sameSecret(token, env.ADMIN_TOKEN))) return null;
  await bump(env.DB, [{ key: failKey, expires: (w10 + 1) * TEN_MIN }]);
  return err(401, "unauthorised", cors, { "WWW-Authenticate": "Bearer" });
}

interface Row {
  id: number; created_at: number; status: string; x0: number; y0: number; x1: number; y1: number; text: string;
  contact: string | null; view_x: number | null; view_y: number | null; view_z: number | null; features: string | null;
  ip_hash: string | null; country: string | null; user_agent: string | null;
}

async function listComments(url: URL, env: Env, cors: Record<string, string>): Promise<Response> {
  const status = url.searchParams.get("status") || "new";
  if (!["new", "done", "all"].includes(status)) return err(400, "invalid_request", cors);
  const limitRaw = url.searchParams.get("limit") || "50";
  const beforeRaw = url.searchParams.get("before");
  if (!/^\d{1,3}$/.test(limitRaw) || (beforeRaw !== null && !/^\d{1,15}$/.test(beforeRaw))) return err(400, "invalid_request", cors);
  const limit = Math.min(Math.max(Number(limitRaw), 1), 100);
  const before = beforeRaw === null ? Number.MAX_SAFE_INTEGER : Number(beforeRaw);
  const q = status === "all"
    ? env.DB.prepare("SELECT * FROM comments WHERE id < ?1 ORDER BY id DESC LIMIT ?2").bind(before, limit)
    : env.DB.prepare("SELECT * FROM comments WHERE status = ?1 AND id < ?2 ORDER BY id DESC LIMIT ?3").bind(status, before, limit);
  const { results } = await q.all<Row>();
  const comments = results.map((r) => ({
    id: r.id, createdAt: r.created_at, status: r.status,
    box: { x0: r.x0, y0: r.y0, x1: r.x1, y1: r.y1 },
    text: r.text, contact: r.contact,
    view: r.view_x === null ? null : { x: r.view_x, y: r.view_y, z: r.view_z },
    features: r.features, country: r.country, userAgent: r.user_agent,
    // a short, stable tag per sender, enough to spot one person sending many notes
    sender: r.ip_hash ? r.ip_hash.slice(0, 10) : null,
  }));
  const next = results.length === limit ? results[results.length - 1].id : null;
  return json({ comments, next }, 200, cors);
}

async function patchComment(request: Request, id: number, env: Env, cors: Record<string, string>): Promise<Response> {
  const type = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (type !== "application/json") return err(415, "unsupported_media_type", cors);
  const raw = await readBody(request, 256).catch(() => null);
  if (raw === null) return err(413, "payload_too_large", cors);
  let body: unknown;
  try { body = JSON.parse(raw); } catch { return err(400, "invalid_json", cors); }
  if (!isObj(body) || !onlyKeys(body, ["status"]) || (body.status !== "new" && body.status !== "done")) return err(400, "invalid_request", cors);
  const r = await env.DB.prepare("UPDATE comments SET status = ?1 WHERE id = ?2").bind(body.status, id).run();
  if (!r.meta.changes) return err(404, "not_found", cors);
  return json({ ok: true }, 200, cors);
}

async function deleteComment(id: number, env: Env, cors: Record<string, string>): Promise<Response> {
  const r = await env.DB.prepare("DELETE FROM comments WHERE id = ?1").bind(id).run();
  if (!r.meta.changes) return err(404, "not_found", cors);
  return json({ ok: true }, 200, cors);
}

async function route(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const origin = request.headers.get("Origin");
  const cors = corsHeaders(origin, env);

  if (request.method === "OPTIONS") {
    // Preflight: only for allowed origins, never a wildcard.
    return cors["Access-Control-Allow-Origin"] ? new Response(null, { status: 204, headers: { ...SECURITY_HEADERS, ...cors } }) : err(403, "forbidden", {});
  }

  if (url.pathname === "/api/comments") {
    if (request.method === "POST") return postComment(request, env, cors);
    if (request.method === "GET") return (await adminGate(request, env, cors)) ?? listComments(url, env, cors);
    return err(405, "method_not_allowed", cors, { Allow: "GET, POST, OPTIONS" });
  }

  const m = url.pathname.match(/^\/api\/comments\/(\d{1,15})$/);
  if (m) {
    const id = Number(m[1]);
    if (request.method !== "PATCH" && request.method !== "DELETE") return err(405, "method_not_allowed", cors, { Allow: "PATCH, DELETE, OPTIONS" });
    const denied = await adminGate(request, env, cors);
    if (denied) return denied;
    return request.method === "PATCH" ? patchComment(request, id, env, cors) : deleteComment(id, env, cors);
  }

  return err(404, "not_found", cors);
}

export default {
  async fetch(request, env): Promise<Response> {
    try {
      return await route(request, env);
    } catch (e) {
      // Logged for the author (Workers logs); the client only ever sees a generic message.
      console.error("feedback error", e instanceof Error ? e.message : String(e));
      return err(500, "server_error", corsHeaders(request.headers.get("Origin"), env));
    }
  },

  async scheduled(_controller, env): Promise<void> {
    const now = Date.now();
    await env.DB.batch([
      env.DB.prepare("DELETE FROM counters WHERE expires_at < ?1").bind(now),
      env.DB.prepare("UPDATE comments SET ip_hash = NULL WHERE ip_hash IS NOT NULL AND created_at < ?1").bind(now - IP_HASH_RETENTION),
    ]);
  },
} satisfies ExportedHandler<Env>;
