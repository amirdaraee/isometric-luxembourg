import { test } from "node:test";
import assert from "node:assert/strict";
import { METHODS, VIEWS, viewerUrl } from "./bakeoff.ts";

test("every method's column opens the same view of its own release", () => {
  const v = VIEWS[0];
  const urls = METHODS.map((m) => new URL(viewerUrl(m.id, v), "http://x"));
  for (const [i, u] of urls.entries()) {
    assert.equal(u.searchParams.get("data"), `/bake/${METHODS[i].id}/`);
    for (const k of ["x", "y", "z", "hour", "date"]) assert.equal(u.searchParams.get(k), urls[0].searchParams.get(k));
    assert.ok(u.searchParams.has("nosim") && u.searchParams.has("noui"));
  }
});

test("the fixed views cover the brief's previews", () => {
  const ids = VIEWS.map((v) => v.id);
  for (const id of ["grund-day", "grund-golden", "grund-night", "bock", "facade"]) assert.ok(ids.includes(id), id);
  for (const v of VIEWS) assert.ok(v.z > 0 && v.hour >= 0 && v.hour < 24);
});
