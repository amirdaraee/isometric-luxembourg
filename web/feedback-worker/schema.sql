-- Notes visitors leave on the map. Private: only the map's author reads them (admin endpoints).
-- Apply with: npx wrangler d1 execute isometric-feedback --local|--remote --file=schema.sql
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at INTEGER NOT NULL,                 -- Unix time in milliseconds
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'done')),
  x0 REAL NOT NULL, y0 REAL NOT NULL,          -- the marked box, in map pixels
  x1 REAL NOT NULL, y1 REAL NOT NULL,
  text TEXT NOT NULL,
  contact TEXT,                                -- optional email or name, as typed
  view_x REAL, view_y REAL, view_z REAL,       -- the visitor's view when sending
  features TEXT,                               -- feature switches that were on
  ip_hash TEXT,                                -- salted SHA-256 of the client IP (never the IP); cleared after 30 days
  country TEXT,
  user_agent TEXT                              -- truncated
);
CREATE INDEX IF NOT EXISTS comments_status_id ON comments (status, id);
CREATE INDEX IF NOT EXISTS comments_created ON comments (created_at);

-- Fixed-window counters for rate limits. Keys look like "post10m:<hash>:<window>", "postday:<hash>:<day>",
-- "global:<day>" and "adminfail:<hash>:<window>". Expired rows are removed by the daily cron.
CREATE TABLE IF NOT EXISTS counters (
  key TEXT PRIMARY KEY,
  n INTEGER NOT NULL,
  expires_at INTEGER NOT NULL                  -- Unix time in milliseconds
);
CREATE INDEX IF NOT EXISTS counters_expires ON counters (expires_at);
