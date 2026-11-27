import assert from "node:assert/strict";
import { test } from "node:test";
import { limiter, retry, retryWaitMs, Stale } from "./loadq.ts";

const tick = () => new Promise<void>((r) => setTimeout(r, 0));

test("no more than the limit run at a time, and every load asked for is run, in the order asked", async () => {
  const load = limiter(4);
  let active = 0, most = 0;
  const started: number[] = [], gates: (() => void)[] = [];
  const all = Array.from({ length: 2000 }, (_, i) => load(async () => {
    started.push(i);
    most = Math.max(most, ++active);
    await new Promise<void>((r) => gates.push(r));
    active--;
    return i;
  }));
  await tick();
  assert.equal(started.length, 4);
  while (gates.length) { gates.shift()!(); await tick(); }
  assert.deepEqual(await Promise.all(all), Array.from({ length: 2000 }, (_, i) => i));
  assert.equal(most, 4);
  assert.deepEqual(started, Array.from({ length: 2000 }, (_, i) => i));
});

test("a load no longer wanted when its turn comes is dropped unrun, and those after it still run", async () => {
  const load = limiter(1);
  let open!: () => void;
  const ran: string[] = [];
  let wanted = true;
  const a = load(() => new Promise<void>((r) => { ran.push("a"); open = r; }));
  const b = load(async () => { ran.push("b"); }, () => wanted);
  const c = load(async () => { ran.push("c"); return "c"; });
  wanted = false;                                  // the view moved on while b waited
  await tick();
  open();
  await a;
  await assert.rejects(b, Stale);
  assert.equal(await c, "c");
  assert.deepEqual(ran, ["a", "c"]);
});

test("a load that throws frees its place", async () => {
  const load = limiter(1);
  await assert.rejects(load(async () => { throw new Error("x"); }), /x/);
  await assert.rejects(load(() => { throw new Error("y"); }), /y/);
  assert.equal(await load(async () => 5), 5);
});

test("a failed request is made again, with a doubling wait, and its last failure is passed on", async () => {
  const waits: number[] = [];
  const sleep = async (ms: number) => { waits.push(ms); };
  let n = 0;
  assert.equal(await retry(async () => { if (++n < 3) throw new TypeError("Failed to fetch"); return "ok"; }, 3, 250, sleep), "ok");
  assert.equal(n, 3);
  assert.deepEqual(waits, [250, 500]);
  n = 0;
  await assert.rejects(retry(async () => { n++; throw new Error(`fail ${n}`); }, 3, 250, sleep), /fail 3/);
  assert.equal(n, 3);
});

test("a failed tile is asked for again after 1 s, then later each time, never later than 30 s", () => {
  assert.deepEqual([1, 2, 3, 4, 5, 6, 7, 20].map(retryWaitMs), [1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000]);
});
