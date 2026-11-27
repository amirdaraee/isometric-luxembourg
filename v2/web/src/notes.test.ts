import assert from "node:assert/strict";
import { test } from "node:test";
import { clock, noteLink, notesText, parseNotes, viewQuery, type Note } from "./notes.ts";

const note: Note = { x: 61440.4, y: 33650.6, z: 3, hour: 20.5, date: "2026-06-24", what: "wall", text: "the top edge is ragged" };

test("the address of a view sets x, y and z and keeps the other parameters", () => {
  assert.equal(viewQuery("?noui&hour=13&x=1&y=2&z=0.5&off=trees", { x: 61440.4, y: 33650.6, z: 2.99999 }),
    "?noui&hour=13&x=61440&y=33651&z=3&off=trees");
  assert.equal(viewQuery("", { x: 10, y: 20, z: 0.123456, hour: 20.504 }), "?x=10&y=20&z=0.123&hour=20.5");
  assert.equal(viewQuery("?v1x=5&v1y=6&review", { x: 10, y: 20, z: 1 }), "?review&x=10&y=20&z=1");
});

test("a note's link opens its place, scale, hour and date, with the notes on", () => {
  assert.equal(noteLink("http://localhost:5176/", note), "http://localhost:5176/?x=61440&y=33651&z=3&hour=20.5&date=2026-06-24&review");
  assert.equal(noteLink("/", { ...note, date: null }), "/?x=61440&y=33651&z=3&hour=20.5&review");
});

test("the hour as a clock time", () => {
  assert.deepEqual([0, 13, 20.5, 23.99, 23.9999].map(clock), ["00:00", "13:00", "20:30", "23:59", "00:00"]);
});

test("the notes as text: numbered, each with what and where it is and its link", () => {
  assert.equal(notesText([note, { ...note, what: "", date: null, text: "no trees here" }], "/"),
    "1. the top edge is ragged\n   wall at x=61440 y=33651, 20:30 on 2026-06-24\n   /?x=61440&y=33651&z=3&hour=20.5&date=2026-06-24&review\n\n"
    + "2. no trees here\n   place at x=61440 y=33651, 20:30\n   /?x=61440&y=33651&z=3&hour=20.5&review");
  assert.equal(notesText([], "/"), "");
});

test("kept notes are read back, and what is not a note is left out", () => {
  assert.deepEqual(parseNotes(JSON.stringify([note])), [note]);
  assert.deepEqual(parseNotes(JSON.stringify([note, null, 5, { ...note, x: "a" }, { ...note, text: " " }, { ...note, z: 0 },
    { ...note, date: "today", what: 3 }])), [note, { ...note, date: null, what: "" }]);
  assert.deepEqual(parseNotes(null), []);
  assert.deepEqual(parseNotes("{"), []);
  assert.deepEqual(parseNotes("{\"x\":1}"), []);
});
