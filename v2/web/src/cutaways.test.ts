import assert from "node:assert/strict";
import { test } from "node:test";
import { cutawayParam, depthWithCutaways, inSlice, parseCutaway, sliceHalfPlanes, tileMeets, type CutLandmark } from "./cutaways.ts";

const NAMES = ["cathedral", "palace", "abbey"];

test("?cutaway: absent is off, alone is every landmark, a list is those that exist", () => {
  assert.deepEqual(parseCutaway(null, NAMES), []);
  assert.deepEqual(parseCutaway("", NAMES), NAMES);
  assert.deepEqual(parseCutaway("palace, cathedral,nowhere", NAMES), ["cathedral", "palace"]);
  assert.deepEqual(parseCutaway("nowhere", NAMES), []);
});

test("the address keeps the choice and reads back the same", () => {
  for (const on of [[], ["abbey"], ["palace", "cathedral"], NAMES]) {
    const v = cutawayParam(on, NAMES);
    assert.deepEqual(parseCutaway(v, NAMES), NAMES.filter((n) => on.includes(n)));
  }
  assert.equal(cutawayParam([], NAMES), null);
  assert.equal(cutawayParam(NAMES, NAMES), "");
});

test("a tile meets a landmark's extent at every zoom", () => {
  const bbox: [number, number, number, number] = [600, 1100, 1000, 1500];
  assert.ok(tileMeets(bbox, 0, 1, 2) && tileMeets(bbox, 0, 1, 2));
  assert.ok(!tileMeets(bbox, 0, 0, 2) && !tileMeets(bbox, 0, 2, 2) && !tileMeets(bbox, 0, 1, 1) && !tileMeets(bbox, 0, 1, 3));
  assert.ok(tileMeets(bbox, 1, 0, 1) && !tileMeets(bbox, 1, 1, 1));
  assert.ok(tileMeets(bbox, 3, 0, 0));
});

const lm = (planes: CutLandmark["planes"]): CutLandmark => ({ name: "x", slug: "x", replaces: [], replaces_index: [7], planes, floor_z: 300,
  bbox_px: [0, 0, 1, 1], levels: 0, tiles: {} });

test("the slice is in front of every plane, within its extent, above the floor (as v2/layers/cutaways.py)", () => {
  const origin: [number, number] = [70000, 65000];
  // one plane through (70010, 65020) facing east, from 2 m south of it to 3 m north
  const h = sliceHalfPlanes(lm([{ origin: [70010, 65020], normal: [2, 0], extent: [-2, 3] }]), origin);
  assert.equal(h.length, 3);
  assert.ok(inSlice(h, 300, 11, 20, 301));
  assert.ok(!inSlice(h, 300, 9, 20, 301));          // behind the plane
  assert.ok(!inSlice(h, 300, 11, 23.5, 301) && !inSlice(h, 300, 11, 17.5, 301));   // past each end
  assert.ok(inSlice(h, 300, 11, 22.9, 301) && inSlice(h, 300, 11, 18.1, 301));
  assert.ok(!inSlice(h, 300, 11, 20, 300));         // the floor stays
  // two planes: a quarter towards the south-east
  const q = sliceHalfPlanes(lm([{ origin: [70010, 65020], normal: [1, 0], extent: [-60, 0] },
    { origin: [70010, 65020], normal: [0, -1], extent: [0, 60] }]), origin);
  assert.ok(inSlice(q, 300, 15, 15, 310) && !inSlice(q, 300, 15, 25, 310) && !inSlice(q, 300, 5, 15, 310));
});

test("labels meet the cutaway's depth where a replaced building stood, layer 8's elsewhere", () => {
  const replaced = new Set([7]);
  const id = (obj: number, cls: number) => ((obj << 8) | cls) >>> 0;
  assert.equal(depthWithCutaways({ depth: 100, id: id(7, 23) }, replaced, 130), 130);            // its roof: the cutaway's depth
  assert.equal(depthWithCutaways({ depth: 100, id: id(7, 11) }, replaced, Infinity), Infinity);  // open to what lies behind
  assert.equal(depthWithCutaways({ depth: 100, id: id(8, 11) }, replaced, 130), 100);            // another building
  assert.equal(depthWithCutaways({ depth: 100, id: id(7, 18) }, replaced, 130), 100);            // tree number 7 is not building 7
  assert.equal(depthWithCutaways({ depth: 100, id: id(7, 4) }, replaced, 130), 100);
});
