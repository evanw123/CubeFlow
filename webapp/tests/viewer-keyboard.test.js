import assert from "node:assert/strict";
import test from "node:test";

import {
  getViewerKeyboardAction,
  shouldIgnoreViewerKeyboardEvent,
} from "../lib/viewer-keyboard.js";

function keyEvent(key, overrides = {}) {
  return {
    key,
    defaultPrevented: false,
    metaKey: false,
    ctrlKey: false,
    altKey: false,
    target: { tagName: "BODY" },
    ...overrides,
  };
}

test("viewer keyboard shortcuts map common playback keys", () => {
  assert.equal(getViewerKeyboardAction(keyEvent("ArrowRight")), "next");
  assert.equal(getViewerKeyboardAction(keyEvent("ArrowLeft")), "prev");
  assert.equal(getViewerKeyboardAction(keyEvent("PageDown")), "next");
  assert.equal(getViewerKeyboardAction(keyEvent("PageUp")), "prev");
  assert.equal(getViewerKeyboardAction(keyEvent(" ")), "toggle-play");
  assert.equal(getViewerKeyboardAction(keyEvent("K")), "toggle-play");
  assert.equal(getViewerKeyboardAction(keyEvent("Home")), "reset-playback");
  assert.equal(getViewerKeyboardAction(keyEvent("End")), "finish-playback");
  assert.equal(getViewerKeyboardAction(keyEvent("R")), "reset-view");
  assert.equal(getViewerKeyboardAction(keyEvent("Escape")), "pause");
});

test("viewer keyboard shortcuts do not hijack editing or browser shortcuts", () => {
  assert.equal(shouldIgnoreViewerKeyboardEvent(keyEvent("ArrowRight", { target: { tagName: "INPUT" } })), true);
  assert.equal(shouldIgnoreViewerKeyboardEvent(keyEvent("ArrowRight", { target: { tagName: "TEXTAREA" } })), true);
  assert.equal(shouldIgnoreViewerKeyboardEvent(keyEvent("ArrowRight", { target: { tagName: "SELECT" } })), true);
  assert.equal(shouldIgnoreViewerKeyboardEvent(keyEvent("ArrowRight", { target: { isContentEditable: true } })), true);
  assert.equal(shouldIgnoreViewerKeyboardEvent(keyEvent("R", { ctrlKey: true })), true);
  assert.equal(getViewerKeyboardAction(keyEvent("R", { metaKey: true })), null);
});

test("unknown keys are ignored", () => {
  assert.equal(getViewerKeyboardAction(keyEvent("A")), null);
});
