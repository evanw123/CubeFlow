const TURN_BASE = {
  // CSS +Y points down, and the canonical snapshot grids define U/D rows
  // from back-to-front. These signs make the animation land on the next frame.
  R: { axis: "x", layer: 1, angle: 90 },
  L: { axis: "x", layer: -1, angle: -90 },
  U: { axis: "y", layer: 1, angle: -90 },
  D: { axis: "y", layer: -1, angle: 90 },
  F: { axis: "z", layer: 1, angle: 90 },
  B: { axis: "z", layer: -1, angle: -90 },
  M: { axis: "x", layer: 0, angle: -90 },
  E: { axis: "y", layer: 0, angle: 90 },
  S: { axis: "z", layer: 0, angle: 90 },
  r: { axis: "x", layer: [0, 1], angle: 90 },
  l: { axis: "x", layer: [-1, 0], angle: -90 },
  u: { axis: "y", layer: [0, 1], angle: -90 },
  d: { axis: "y", layer: [-1, 0], angle: 90 },
  f: { axis: "z", layer: [0, 1], angle: 90 },
  b: { axis: "z", layer: [-1, 0], angle: -90 },
  x: { axis: "x", layer: "all", angle: 90 },
  y: { axis: "y", layer: "all", angle: -90 },
  z: { axis: "z", layer: "all", angle: 90 },
};

export function getViewerTurnSpec(move, reverse = false) {
  if (!move || typeof move !== "string") return null;
  const token = move.trim();
  if (!token) return null;

  const baseFace = token[0];
  const face = "xyzrludfb".includes(baseFace) ? baseFace : baseFace.toUpperCase();
  const base = TURN_BASE[face];
  if (!base) return null;

  const suffix = token.slice(1);
  let angle = base.angle;
  if (suffix === "'") {
    angle *= -1;
  } else if (suffix === "2") {
    angle *= 2;
  }
  if (reverse) angle *= -1;

  return { axis: base.axis, layer: base.layer, angle };
}
