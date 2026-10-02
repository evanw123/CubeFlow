import assert from "node:assert/strict";
import test from "node:test";

import { getViewerTurnSpec } from "../lib/viewer-turns.js";


test("clockwise face turns use the transform direction matching playback frames", () => {
  assert.deepEqual(getViewerTurnSpec("R"), { axis: "x", layer: 1, angle: 90 });
  assert.deepEqual(getViewerTurnSpec("L"), { axis: "x", layer: -1, angle: -90 });
  assert.deepEqual(getViewerTurnSpec("U"), { axis: "y", layer: 1, angle: -90 });
  assert.deepEqual(getViewerTurnSpec("D"), { axis: "y", layer: -1, angle: 90 });
  assert.deepEqual(getViewerTurnSpec("F"), { axis: "z", layer: 1, angle: 90 });
  assert.deepEqual(getViewerTurnSpec("B"), { axis: "z", layer: -1, angle: -90 });
});


test("prime, double, and reverse playback invert the base transform safely", () => {
  assert.equal(getViewerTurnSpec("R'").angle, -90);
  assert.equal(getViewerTurnSpec("U2").angle, -180);
  assert.equal(getViewerTurnSpec("F", true).angle, -90);
  assert.equal(getViewerTurnSpec("D'", true).angle, 90);
});


test("wide, slice, and cube rotations follow their corresponding face turns", () => {
  assert.equal(getViewerTurnSpec("r").angle, getViewerTurnSpec("R").angle);
  assert.equal(getViewerTurnSpec("u").angle, getViewerTurnSpec("U").angle);
  assert.equal(getViewerTurnSpec("M").angle, getViewerTurnSpec("L").angle);
  assert.equal(getViewerTurnSpec("E").angle, getViewerTurnSpec("D").angle);
  assert.equal(getViewerTurnSpec("S").angle, getViewerTurnSpec("F").angle);
  assert.equal(getViewerTurnSpec("x").angle, getViewerTurnSpec("R").angle);
  assert.equal(getViewerTurnSpec("y").angle, getViewerTurnSpec("U").angle);
  assert.equal(getViewerTurnSpec("z").angle, getViewerTurnSpec("F").angle);
});
