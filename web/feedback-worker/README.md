# Feedback worker

Small Cloudflare Worker behind the map's "Mark a spot" button (feature switch `comments`). A visitor draws a box
on the map and sends a note. The notes are **private**: visitors can only send them. Only the map's author can
list, update or delete them, using the admin token, through the local-only page `web/public/admin/index.html`.
Nothing a visitor writes is ever shown to anyone else.

It runs on free tiers only: Workers Free, D1 Free, Turnstile, and the Workers rate-limiting binding.

## Endpoints

| Method and path | Who | What |
|---|---|---|
| `POST /api/comments` | anyone (Turnstile) | `{ box: {x0,y0,x1,y1}, text, contact?, view?: {x,y,z}, features?, turnstileToken }` → `201 {ok, id}` |
| `GET /api/comments?status=new\|done\|all&limit=1..100&before=<id>` | admin | newest first → `{comments, next}` (`next` is the `before` value for the next page) |
| `PATCH /api/comments/:id` `{status: "new"\|"done"}` | admin | → `{ok}` or 404 |
| `DELETE /api/comments/:id` | admin | → `{ok}` or 404 |
| `OPTIONS *` | allowed origins | CORS preflight |

Admin requests send `Authorization: Bearer <ADMIN_TOKEN>`. Errors are always a short JSON code such as
`{"error":"invalid_request"}`, never details or stack traces.

## What is checked, and the limits

All checks happen in the Worker. The viewer's own checks are only there for convenience.

- **Origin and CORS:** an allow-list from the `ALLOWED_ORIGINS` var (production: `https://isometric.lu`,
  `https://www.isometric.lu`, and `http://localhost:3000` for the local admin page). There is no wildcard.
  A `POST` without an allowed `Origin` gets 403. Preflights from other origins get 403.
- **Body:** `Content-Type: application/json` only (415). At most **4096 bytes** (413), checked against
  `Content-Length` and again while streaming. The body must be valid UTF-8 JSON (400).
- **Schema, strict:** unknown fields anywhere are rejected (400).
  - `box`: four finite numbers, inside 0..26624 × 0..14336, each side ≥ 4 px, area ≤ 64,000,000 px²
    (about 2 × 2 km).
  - `text`: 1..1000 characters after trimming. Control characters other than newline and tab are removed.
    Stored as plain text.
  - `contact`: optional, ≤ 120 characters, on one line.
  - `view`: optional `{x,y,z}` finite numbers, with 0 < z ≤ 10.
  - `features`: optional, ≤ 400 characters of `[A-Za-z0-9,]`.
  - `turnstileToken`: 1..2048 characters.
- **Turnstile:** verified with siteverify, using `TURNSTILE_SECRET` and the client IP, and with an idempotency
  key. If `TURNSTILE_HOSTNAMES` is set, the token's hostname must be in it. Failure gives 403.
- **Rate limits.** Clients are keyed by `SHA-256(IP_SALT + ":" + CF-Connecting-IP)`. The raw IP is never stored.
  - Burst: **10 POSTs per minute** per client, per Cloudflare location (`BURST` binding). This check needs no
    D1 query.
  - **5 POSTs per 10 minutes** and **20 per UTC day** per client (D1 fixed-window counters). These are counted
    *before* Turnstile, so failed attempts use up the allowance too. Over the limit gives 429 with
    `Retry-After`.
  - **300 stored notes per UTC day** in total (global cap) gives 503. A botnet cannot fill D1's free quota.
  - Admin: **10 failed tokens per 10 minutes** per client gives 429 for the rest of the window, even with the
    right token. The token is compared in constant time (both sides are hashed, then XOR-compared).
- **Stored per note:** box, text, contact, view, features, IP hash, country (`request.cf.country`), user agent
  (cut to 200 characters), time and status. A daily cron (03:17 UTC) deletes expired counters and **clears IP
  hashes older than 30 days**.
- **D1:** parameterised statements only.
- **Response headers:** `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
  `Cross-Origin-Resource-Policy: same-site`, `Vary: Origin`.

## DDoS and abuse layers (outside in)

1. **Cloudflare's edge.** The Worker is reachable only on the custom domain `api.isometric.lu`, in the
   `isometric.lu` zone. `workers_dev` and preview URLs are off. Every request therefore passes Cloudflare's
   always-on, unmetered L3/4/7 DDoS protection, and the zone's WAF, before the Worker runs.
2. **WAF rate-limiting rule.** The free plan allows one such rule. Create it under Security → Security rules →
   Create rule → Rate limiting rules:
   - Name: `api burst`
   - Expression: `(http.request.uri.path wildcard "/api/*")`. On Free, the rule may only use the URI path
     (and Verified Bot), not the host. That is fine here, because only the Worker serves `/api/` paths in this
     zone. If the editor refuses `wildcard`, use `(http.request.uri.path eq "/api/comments")` instead. That
     still covers every visitor POST.
   - With the same characteristics: IP (fixed on Free)
   - When rate exceeds: **20 requests per 10 seconds** (10 s is the only period on Free)
   - Then: **Block**, for **10 seconds** (the only duration on Free)

   This blocks a single IP from flooding before the Worker is even called. Blocked requests are not Worker
   requests, so they do not count against the 100k/day quota. A visitor sending one note makes two requests
   (preflight and POST); the admin page makes a handful. 20 per 10 s leaves plenty of room for both.
3. **Turnstile** on every POST (mostly invisible: `appearance: interaction-only`).
4. **Per-client limits** (burst binding, then the D1 counters) and the **global daily cap**.
5. **Body size limit**, plus a strict schema checked before any D1 write except the counters.

**Free plan limits to know about:**

- **Workers Free allows 100,000 requests per day** for the account, reset at 00:00 UTC. Once that is used up,
  requests to the Worker fail with Cloudflare error 1027 until the reset. On a custom domain there is no origin
  to "fail open" to, so the note card shows "could not be sent". The map itself is static on GitHub Pages and
  is not affected.
- Workers Free allows 10 ms CPU per request. This Worker uses well under 1 ms apart from the hashing.
- **D1 Free allows 5 million rows read and 100,000 rows written per day.** Since 1 September 2026 these are
  enforced: queries fail until midnight UTC. A POST that gets past the burst limit writes 2 counter rows, and
  a stored note writes 2 more. At 100k requests a day, the most possible, that stays within the write quota.
  The global cap keeps the comments table small.

## Run it locally

    cd web/feedback-worker
    npm install
    cp .dev.vars.example .dev.vars        # Turnstile always-pass test secret, dev salt and token
    npx wrangler d1 execute isometric-feedback --local --file=schema.sql
    npx wrangler dev --local              # http://localhost:8787

Then run the viewer with `VITE_FEEDBACK_API=http://localhost:8787 npm run dev` (in dev this is also the default).
Open `http://localhost:3000/admin/index.html`, with the API URL `http://localhost:8787` and the token from
`.dev.vars`. In dev the page must be opened with `index.html` in the URL: Vite answers `/admin/` with the map.

Turnstile test secrets: `1x0000000000000000000000000000000AA` always passes and
`2x0000000000000000000000000000000AA` always fails. Use, for example,
`npx wrangler dev --local --port 8788 --var TURNSTILE_SECRET:2x0000000000000000000000000000000AA`. The dev site
key `1x00000000000000000000AA` always passes. Test tokens report the hostname `example.com`, so `.dev.vars`
leaves `TURNSTILE_HOSTNAMES` empty.

Type check: `npx wrangler types` (writes `worker-configuration.d.ts`, which is not kept in git), then
`npx tsc -p .` with TypeScript from `web/node_modules`.

## Deploy

1. **D1:** run `npx wrangler d1 create isometric-feedback`, and put the printed `database_id` into
   `wrangler.jsonc`. Then run `npx wrangler d1 execute isometric-feedback --remote --file=schema.sql`.
2. **Turnstile widget:** in the dashboard go to Turnstile → Add widget. Name it `isometric.lu feedback`. Add the
   hostnames `isometric.lu` and `www.isometric.lu` (add `localhost` too to test the real key locally). Set the
   mode to **Managed**. Keep the site key for the viewer and the secret key for the Worker.
3. **Secrets** (each one is prompted for, so it never appears in shell history):

       npx wrangler secret put TURNSTILE_SECRET     # the widget's secret key
       npx wrangler secret put IP_SALT              # e.g. output of: openssl rand -hex 32
       npx wrangler secret put ADMIN_TOKEN          # e.g. output of: openssl rand -base64 33

4. **Rate-limiting binding:** the `ratelimits` block in `wrangler.jsonc` uses the namespace id `4711`. Any
   integer that is unique in the account will do. The code works without the binding, so if deployment rejects
   it, remove the block.
5. **Deploy:** run `npx wrangler deploy`. The `routes` entry
   `{ "pattern": "api.isometric.lu", "custom_domain": true }` creates the DNS record and certificate for
   `api.isometric.lu` in the `isometric.lu` zone. No DNS record is made by hand, and there must not already be
   one with that name.
6. **WAF rule:** create the rate-limiting rule above in the `isometric.lu` zone.
7. **Viewer:** build with `VITE_FEEDBACK_API=https://api.isometric.lu` and `VITE_TURNSTILE_SITEKEY=<site key>`
   (for example in `web/.env.production`). Then remove `comments` from `VITE_FEATURES_OFF` and publish. Without
   both values, a release build hides the button.
8. **Check:**
   `curl -i -X OPTIONS https://api.isometric.lu/api/comments -H "Origin: https://isometric.lu" -H "Access-Control-Request-Method: POST"`
   should return 204 with `Access-Control-Allow-Origin: https://isometric.lu`.
