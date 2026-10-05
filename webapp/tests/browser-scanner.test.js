import test from "node:test";
import assert from "node:assert/strict";

import {
  buildGridSamplingGeometry,
  computeCoverSourceRect,
  medianRgb,
  rgbToBgr,
} from "../lib/browser-scanner.js";

test("median RGB and BGR conversion preserve channel meaning", () => {
  const pixels = Uint8ClampedArray.from([
    10, 90, 200, 255,
    20, 80, 180, 255,
    30, 70, 160, 255,
  ]);
  assert.deepEqual(medianRgb(pixels), [20, 80, 180]);
  assert.deepEqual(rgbToBgr([20, 80, 180]), [180, 80, 20]);
});

test("cover crop matches object-fit cover without mirroring", () => {
  assert.deepEqual(computeCoverSourceRect(1920, 1080, 800, 800), {
    x: 420,
    y: 0,
    width: 1080,
    height: 1080,
  });
  assert.deepEqual(computeCoverSourceRect(800, 1200, 800, 400), {
    x: 0,
    y: 400,
    width: 800,
    height: 400,
  });
});

test("grid sampling geometry stays centered and resolution independent", () => {
  const geometry = buildGridSamplingGeometry(1000, 600, 0.5);
  assert.equal(geometry.size, 300);
  assert.equal(geometry.left, 350);
  assert.equal(geometry.top, 150);
  assert.deepEqual(geometry.centers[1][1], { x: 500, y: 300 });
});
